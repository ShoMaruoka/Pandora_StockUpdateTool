"""Yahoo!ショッピングの初回認可。認可コードを受け取り、トークンを保存する。"""
from __future__ import annotations

import base64
import json
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

AUTH_URL = "https://auth.login.yahoo.co.jp/yconnect/v2/authorization"
TOKEN_URL = "https://auth.login.yahoo.co.jp/yconnect/v2/token"
REDIRECT_URI = "http://127.0.0.1:8766/callback"
LISTEN_HOST = "127.0.0.1"
LISTEN_PORT = 8766
WAIT_SECONDS = 600
STORE_PATH = Path.home() / ".ec_inventory" / "yahoo_shopping.json"


def load_store() -> dict:
    if not STORE_PATH.exists():
        raise SystemExit(f"認証ファイルがありません: {STORE_PATH}")
    return json.loads(STORE_PATH.read_text(encoding="utf-8"))


def save_store(data: dict) -> None:
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def exchange_token(client_id: str, client_secret: str, code: str) -> dict:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    body = urlencode(
        {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        }
    ).encode("utf-8")
    request = Request(
        TOKEN_URL,
        data=body,
        headers={
            "Authorization": "Basic " + basic,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        detail = detail.replace(client_id, "***").replace(client_secret, "***").replace(code, "***")
        raise SystemExit(f"トークン取得に失敗しました ({exc.code}): {detail}") from exc
    except URLError as exc:
        raise SystemExit(f"Yahoo! へ接続できません: {exc.reason}") from exc


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
            f"<title>Yahoo!認可</title><p>{message}</p>"
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
    client_id = str(store.get("client_id") or "").strip()
    client_secret = str(store.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise SystemExit("yahoo_shopping.json に client_id と client_secret が必要です。")
    state = secrets.token_urlsafe(32)
    auth_url = AUTH_URL + "?" + urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid profile",
            "state": state,
            "bail": "1",
        }
    )
    print("ブラウザで Yahoo! の認可画面を開きます。")
    print("ストアのビジネスIDと紐づいた Yahoo! JAPAN ID で許可してください。")
    print(REDIRECT_URI)
    threading.Timer(0.5, lambda: webbrowser.open(auth_url)).start()
    callback = wait_for_callback(state)
    token = exchange_token(client_id, client_secret, callback["code"])
    expires_in = int(token.get("expires_in") or 0)
    store["redirect_uri"] = REDIRECT_URI
    store["access_token"] = token.get("access_token") or ""
    store["refresh_token"] = token.get("refresh_token") or store.get("refresh_token") or ""
    store["token_type"] = token.get("token_type") or ""
    store["expires_at"] = int(time.time()) + expires_in
    if not store["access_token"] or not store["refresh_token"]:
        raise SystemExit("レスポンスにトークンがありません。")
    save_store(store)
    print("認可が完了しました。")
    print(f"保存先: {STORE_PATH}")
    print(f"アクセストークン有効秒数: {expires_in}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("中断しました。")
