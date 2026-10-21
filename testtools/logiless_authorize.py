"""ロジレス初回認可。ブラウザの認可コードを受け取り、トークンを保存する。"""
from __future__ import annotations

import json
import secrets
import sys
import threading
import time
import webbrowser
from getpass import getpass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

AUTH_URL = "https://app2.logiless.com/oauth/v2/auth"
TOKEN_URL = "https://app2.logiless.com/oauth2/token"
REDIRECT_URI = "http://127.0.0.1:8765/callback"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8765
WAIT_SECONDS = 600
STORE_PATH = Path.home() / ".ec_inventory" / "logiless_oauth.json"


def load_store() -> dict:
    if not STORE_PATH.exists():
        return {}
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def save_store(data: dict) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def prompt_credentials(store: dict) -> tuple[str, str]:
    client_id = str(store.get("client_id") or "").strip()
    client_secret = str(store.get("client_secret") or "").strip()
    if client_id and client_secret:
        print(f"保存済みのクライアントIDを使います: {client_id}")
        reuse = input("このまま使いますか？ [Y/n]: ").strip().lower()
        if reuse in ("", "y", "yes"):
            return client_id, client_secret
    client_id = input("クライアントID: ").strip()
    client_secret = getpass("クライアントシークレット（入力は表示されません）: ").strip()
    if not client_id or not client_secret:
        raise SystemExit("クライアントIDとクライアントシークレットが必要です。")
    return client_id, client_secret


def exchange_token(client_id: str, client_secret: str, code: str) -> dict:
    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"トークン取得に失敗しました ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"ロジレスへ接続できません: {exc.reason}") from exc


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self._reply(404, "このURLは認可の受け取り口ではありません。")
            return
        query = parse_qs(parsed.query)
        self.server.result = {  # type: ignore[attr-defined]
            "code": (query.get("code") or [""])[0],
            "state": (query.get("state") or [""])[0],
            "error": (query.get("error") or [""])[0],
            "merchant_id": (query.get("merchant_id") or [""])[0],
            "store_id": (query.get("store_id") or [""])[0],
        }
        if self.server.result["error"]:
            self._reply(400, "認可がキャンセルされたか、エラーになりました。この画面を閉じてください。")
            return
        self._reply(200, "認可コードを受け取りました。この画面を閉じて、ターミナルに戻ってください。")

    def log_message(self, fmt: str, *args) -> None:
        return

    def _reply(self, status: int, message: str) -> None:
        body = (
            "<!doctype html><meta charset='utf-8'>"
            f"<title>ロジレス認可</title><p>{message}</p>"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def wait_for_callback(expected_state: str) -> dict:
    try:
        server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), CallbackHandler)
    except OSError as exc:
        raise SystemExit(
            f"{LISTEN_HOST}:{LISTEN_PORT} を開けません。ほかのプログラムが同じポートを使っていないか確認してください。 ({exc})"
        ) from exc
    server.result = None  # type: ignore[attr-defined]
    server.timeout = 1
    deadline = time.time() + WAIT_SECONDS
    try:
        while time.time() < deadline and server.result is None:  # type: ignore[attr-defined]
            server.handle_request()
    finally:
        server.server_close()
    result = server.result  # type: ignore[attr-defined]
    if not result:
        raise SystemExit("10分以内に認可が完了しませんでした。もう一度実行してください。")
    if result["error"]:
        raise SystemExit(f"認可エラー: {result['error']}")
    if not secrets.compare_digest(result["state"], expected_state):
        raise SystemExit("state が一致しません。認可を中断しました。もう一度実行してください。")
    if not result["code"]:
        raise SystemExit("認可コードがありません。")
    return result


def main() -> None:
    store = load_store()
    client_id, client_secret = prompt_credentials(store)
    state = secrets.token_urlsafe(32)
    auth_url = AUTH_URL + "?" + urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "state": state,
        }
    )
    print("ブラウザでロジレスの認可画面を開きます。")
    print("在庫を読むユーザーで許可してください。")
    print(REDIRECT_URI)
    threading.Timer(0.5, lambda: webbrowser.open(auth_url)).start()
    callback = wait_for_callback(state)
    token = exchange_token(client_id, client_secret, callback["code"])
    expires_in = int(token.get("expires_in") or 0)
    saved = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "merchant_id": callback.get("merchant_id") or store.get("merchant_id") or "4350",
        "store_id": callback.get("store_id") or "",
        "access_token": token.get("access_token") or "",
        "refresh_token": token.get("refresh_token") or "",
        "token_type": token.get("token_type") or "",
        "expires_at": int(time.time()) + expires_in,
    }
    if not saved["access_token"] or not saved["refresh_token"]:
        raise SystemExit("レスポンスにトークンがありません。")
    save_store(saved)
    print("認可が完了しました。")
    print(f"保存先: {STORE_PATH}")
    print(f"マーチャントID: {saved['merchant_id']}")
    print(f"アクセストークン有効秒数: {expires_in}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("中断しました。")
