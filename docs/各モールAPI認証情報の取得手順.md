# 各モール API 認証情報の取得手順

在庫更新に使う認証情報の取り方です。取得した値は、この文書やチャットには書かず、利用者の PC 内だけに保存します。

| モール | 控えるもの |
|--------|------------|
| 楽天市場 | serviceSecret、licenseKey |
| Yahoo!ショッピング | Client ID、シークレット、アクセストークン、リフレッシュトークン |
| Amazon | LWA クライアントID、クライアントシークレット、リフレッシュトークン |
| メルカリShops | API アクセストークン |

記録日: 2026-09-28

---

## 楽天市場

RMS の serviceSecret と licenseKey を取る。

1. [RMS](https://mainmenu.rms.rakuten.co.jp/) にログインする。
2. 「店舗様向け 情報・サービス」から「WEB APIサービス」を開く。
3. 「2-1 アプリ一覧」で、アプリ登録者が「店舗様」のアプリを開く。無い場合は、先にその店舗用アプリを登録する。
4. 「利用機能編集」で在庫API 2.0 の在庫更新（`inventories.bulk.upsert` など）を「利用する」にして登録する。
5. セキュリティチェックのあと、「利用情報」に表示される serviceSecret と licenseKey を控える。licenseKey は下数桁しか見えないので、「ライセンスキーの確認・変更」から全文を表示する。

licenseKey には期限がある。案内では約3か月で、期限前に楽天からメールが来る。期限切れの前に再発行し、保存先のキーを差し替える。機能を追加したあとは、新しい licenseKey を発行し直す場合がある。

## Yahoo!ショッピング

在庫APIだけなら、注文API用の別申請は不要である。Client ID の発行後、Yahoo! ID連携でアクセストークンを取る。

公式の導入手順: https://developer.yahoo.co.jp/webapi/shopping/introduction.html

1. ストアに従業員登録されているビジネスIDと紐づく Yahoo! JAPAN ID を用意する。
2. Yahoo!デベロッパーネットワークで、「Yahoo!ショッピング ストア運営をサポートするAPI」のアプリケーションを本番環境用で登録する。Client ID とシークレットが発行される。
3. その Yahoo! JAPAN ID に、ストアクリエイターPro のビジネスIDが紐づいていることを確認する。
4. 登録したコールバックURLへ戻る Yahoo! ID連携（認可コード）で、アクセストークンとリフレッシュトークンを取得する。

リフレッシュトークンの有効期限を長く保つ場合だけ、公開鍵の発行が別途ある。注文APIを使う場合は、Client ID とストアアカウントを指定した利用申請が追加で必要で、完了まで約1週間から10日かかる。在庫更新だけではこの申請は入らない。

在庫APIの申請範囲の説明: https://developer.yahoo.co.jp/webapi/shopping/help/application.html

## Amazon

自社の出品アカウントだけを更新するプライベート開発者として登録する。

1. セラーセントラルにプライマリユーザーでログインする。
2. 「アプリとサービス」から「アプリを開発」を開く。Solution Provider Portal に移行済みの場合は、そちらの Developer Profile から登録する。
3. 開発者プロフィールで Private Developer（自社専用）を選び、在庫数量の更新に必要なロール、用途、セキュリティ対策を入力して登録する。
4. Amazon の審査を待つ。追加確認が来た場合は5日以内に返信する。
5. 審査後にアプリを作成し、LWA のクライアントIDとクライアントシークレットを控える。
6. 同じ画面で自社アカウントを認可し、表示されたリフレッシュトークンを控える。API 呼び出し時は、このトークンをアクセストークンに交換する。

- プライベート開発者の登録: https://developer-docs.amazon.com/sp-api/lang-ja_JP/docs/register-as-a-private-developer
- 自己認可: https://developer-docs.amazon.com/sp-api/lang-ja_JP/docs/self-authorization

## メルカリShops

ライセンスキーはない。ショップ管理画面のアクセストークンを発行する。

公式ガイド: https://support.mercari-shops.com/hc/ja/articles/12290169038617

1. ショップ管理画面を、ショップオーナーまたは管理者で開く。
2. 「設定」の「拡張機能」から「アクセストークンの発行」を開く。
3. トークン名（半角英数字20文字以内）を入れて発行する。
4. 表示されたトークンをその場でコピーする。再表示はできず、一部がマスクされる。コピーし損ねた場合は再発行する。

トークンは1ショップあたり10個までである。公式APIドキュメントでは有効期限はない。この画面の発行は、すでにAPI接続している一元管理システム向けである。自社バッチから直接呼ぶ場合は、それに加えてソウゾウとの利用契約と、契約時に案内されるクライアント名が必要である。

API ドキュメント: https://api.mercari-shops.com/docs/index.html
