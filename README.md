# iPad 用オフラインツール集

**一度ホーム画面に追加すれば、Wi-Fi が無くても起動できる**アプリを 2 つ収録。
どちらも端末内で完結し、外部への通信は一切しない。

| アプリ | URL | 内容 |
|---|---|---|
| **NAVLOG WORKSHEET** | `https://hiro-76.github.io/IpadAPP/` | フライトプラン PDF の `NAVIGATION LOG` を読み取り、ETO / ATO / ALT / RMG / SAT / SPOT WND を機内で記入 |
| **RWY Wind Limit Calculator** | `https://hiro-76.github.io/IpadAPP/wind/` | 滑走路方向と横風 / 追い風 / 向かい風の制限値から、風向ごとの許容風速を計算 |

2 つは独立した PWA なので、**それぞれ別のアイコンとしてホーム画面に追加**できる
（両方追加してもキャッシュや保存内容は干渉しない）。

---

## iPad での使い方

アプリごとに同じ手順を行う（NAVLOG は `…/IpadAPP/`、風計算は `…/IpadAPP/wind/`）。

1. **Safari**（Chrome ではなく Safari）で公開 URL を開く
2. ヘッダー右のバッジが `CACHE …` → **`OFFLINE OK`** に変わるまで数秒待つ
   （この間に本体・pdf.js・アイコンを端末に保存している）
3. 共有ボタン <kbd>⤴</kbd> → **「ホーム画面に追加」**
4. 機内モードにしてホーム画面のアイコンから起動 → そのまま使える

> バッジの意味
> | 表示 | 状態 |
> |---|---|
> | `CACHE …` | オフライン用キャッシュの準備中（もう少し待つ） |
> | `OFFLINE OK` | 準備完了。Wi-Fi 無しで起動できる |
> | `OFFLINE` | いま通信が無い状態で動作中 |
> | `LOCAL` | Service Worker が使えない（`file://` で開いた等） |

### NAVLOG の記入ルール

| 欄 | 入力のしかた |
|---|---|
| **ETO** | 自動計算。4 桁で手入力すると**その地点を基準に以降を引き直す**（枠がアンバーの実線になる）。**空にすれば自動計算に戻る**。確定は欄の外をタップするか Enter |
| **ATO** | 4 桁（`0930`）。`NOW` ボタンで現在 UTC |
| **SAT** | **数字だけ入れるとマイナスになる**（`45` → `-45`）。プラス値のときだけ `+15` と符号を付ける |
| **SPOT WND** | **数字だけ続けて入れる**。欄を離れた時に `/` が入る（`24030` → `240/30`、`040135` → `040/135`）。テンキーで入力できる |
| **RMG** | `284.1` / `2841` / `284100` どの書き方でも可。PLAN FUEL との差を自動表示 |

**ETP**（EQUAL TIME POINT）の地点名は紫で表示し、枠も紫にして見つけやすくしてある。

### 記入内容の自動保存

- **NAVLOG**: 入力した T/O・ATO・ALT・RMG・SAT・SPOT WND と読み込んだプランを
  端末内（localStorage）に自動保存。iOS がアプリを終了させても、次の起動時に
  「前回の作業を復元しました」と表示して続きから使える（不要なら `破棄`）。
  長期保存したい場合は従来どおり `JSON保存` を使う。
- **RWY Wind**: 滑走路・横風 / 向かい風 / 追い風の選択を保存し、次回起動時に
  そのまま復元して結果表を出し直す。

---

## 公開（GitHub Pages）

Service Worker は `https://` でのみ動くため、どこかに HTTPS で置く必要がある。
GitHub Pages が最も簡単:

1. このブランチを push（済）
2. GitHub の **Settings → Pages**
   - Source: `Deploy from a branch`
   - Branch: このブランチ / フォルダ `/ (root)`
3. 1〜2 分後に `https://<ユーザー名>.github.io/<リポジトリ名>/` で公開される
4. その URL を iPad の Safari で開く（上の「iPad での使い方」へ）

サブディレクトリ配信でも動くように、参照は全て相対パスにしてある。

### 検索避け

両方の `index.html` に `<meta name="robots" content="noindex, nofollow, …">` を入れてあるので、
Google などの検索結果には出ない（＝ URL を知っている人だけが辿り着く）。
`<meta name="referrer" content="no-referrer">` も入れてあり、リンクを踏んで他サイトへ
移動しても参照元として URL が漏れない。

**これは認証ではない**。GitHub Pages は Free / Pro / Team プランでは必ず全世界公開で、
アクセス制御は Enterprise Cloud 限定。リポジトリが public なのでプロフィールから
URL は推測できる。本当に人を限定したい場合は、リポジトリを private にする
（GitHub Pro 以上）か、Cloudflare Pages + Cloudflare Access のような認証付きホスティングへ移す。

なお `robots.txt` はクローラーが `https://<ユーザー名>.github.io/robots.txt`（ドメイン直下）
しか読まないため、プロジェクトページ配下に置いたものは無視される。実際に効いているのは
上の `meta` タグ。サイト全体で止めたい場合は `<ユーザー名>.github.io` リポジトリの直下に置く。

---

## ファイル構成

```
index.html                    NAVLOG 本体（1 ファイル完結、外部通信なし）
sw.js                         NAVLOG の Service Worker（オフライン用プリキャッシュ）
manifest.webmanifest          ホーム画面追加時の名前・アイコン・standalone 表示
icons/                        NAVLOG のアイコン（180 / 192 / 512 / maskable）
vendor/pdf.min.js             pdf.js 3.11.174 (legacy build) — CDN からローカル同梱に変更
vendor/pdf.worker.min.js      pdf.js worker — これも同梱（オフラインで PDF を解析するため）
wind/index.html               RWY Wind Limit Calculator 本体
wind/sw.js                    風計算アプリの Service Worker（scope は wind/ のみ）
wind/manifest.webmanifest     風計算アプリのホーム画面設定
wind/icons/                   風計算アプリのアイコン
```

2 つの Service Worker はそれぞれ自分の担当ファイルだけを扱い、キャッシュ名も
`navlog-…` / `rwywind-…` と分けてあるので、片方の更新でもう一方のオフライン
キャッシュが消えることはない。

## オフライン化のためにやったこと（NAVLOG）

- **pdf.js を CDN 参照からローカル同梱へ** — 以前は `cdnjs.cloudflare.com` から
  本体と worker を取得していたため、オフラインでは PDF 読込が失敗していた。
  互換性の高い legacy build を `vendor/` に同梱し、worker も相対パス指定に変更。
- **Service Worker (`sw.js`)** — `index.html` / `manifest` / `vendor/*` / `icons/*` を
  インストール時に一括キャッシュ。以後はキャッシュ優先で応答するので、
  機内でホーム画面から起動しても確実に開く。
- **PWA メタデータ** — `manifest.webmanifest`、`apple-mobile-web-app-capable`、
  `apple-touch-icon`、`apple-mobile-web-app-title` を追加。ホーム画面から
  Safari の UI 無し（standalone）で起動する。ステータスバーと重ならないよう
  ヘッダーに `env(safe-area-inset-*)` を反映。
- **記入内容の自動保存 / 復元** — 入力ごと（400ms デバウンス）と
  バックグラウンド移行時に localStorage へ保存し、起動時に復元。
- **通信 / キャッシュ状態バッジ**と**更新通知** — 新しいバージョンが公開されたら
  「更新」ボタンを表示し、押したときだけ差し替える（記入中に勝手にリロードしない）。
  テーマ（Day/Night）も端末に記憶する。
- ついでに、重複定義されていた `ensureWorker()` / `pdfToText()` を 1 つに整理し、
  CSV 出力の ETO 列が常に空になっていた参照ミス（`getElementById('eto…')`）を修正。

## 記入まわりの修正（v1.0.2）

- **ETO を BackSpace で消すと `0000` に張り付いて直せなくなる不具合を修正。**
  1 文字消すたびに途中の `123` を `01:23` と解釈して欄に書き戻していたのが原因。
  入力中は書き戻さず、欄を離れた時（または Enter）に確定する方式に変更した。
  ついでに **空欄にすれば自動計算に戻せる**ようにし、手入力した ETO は枠の色で
  分かるようにした。
- **ETP** の地点名を紫（`--etp`）にし、ストリップの枠も紫に。
- **SPOT WND** は数字だけ続けて入力すれば、欄を離れた時に `/` が入る（先頭 3 桁が風向）。
  入力中に値を書き換えると iOS が直前の文字を二重に挿入してしまい、`23023` が
  `230/223` になる不具合が出たため、整形は確定時のみにしてある。
  PLAN 側の `WIND` 表示も同じ書式（`285081` → `285/081`）に揃えた。
- **SAT** は数字だけ入力するとマイナス扱い（`45` → `-45`）。プラス値は `+15` と入力。
- **印刷（PDF保存）に ETO が出ていなかったのを修正。** 印刷用の値コピーが
  ATO / ALT / RMG / SAT / SPOT のみで ETO を含んでいなかった。ETO は記入欄では
  なく計算値なので白地・黒文字で印字し、手入力した ETO には `*` を付けている。

## オフライン化のためにやったこと（RWY Wind Limit Calculator）

- `wind/` に移し、**同じ方式で PWA 化**（`manifest.webmanifest` / `sw.js` /
  `apple-touch-icon` / safe-area 対応 / 通信・キャッシュ状態バッジ / 更新通知）。
  元々外部ファイルを読んでいないので、キャッシュ対象は本体とアイコンだけ。
- 滑走路・各制限値の選択を localStorage に保存し、起動時に復元して自動で再計算。
- **計算ロジック（sin / cos による横風・追い風成分の算出、最も厳しい制限の適用）は
  一切変更していない。**
- 2 つのアプリが同じサイトに同居するため、各 Service Worker が自分の担当 URL だけを
  処理するように整理（`wind/` へのアクセスがルート側の NAVLOG に乗っ取られない、
  片方の更新で他方のキャッシュを消さない）。

## 更新のしかた

`index.html` などを変更したら、**そのアプリの `sw.js` の `VERSION` を上げて** push する
（NAVLOG は `sw.js`、風計算は `wind/sw.js`）。次回オンラインで開いたときに
「新しいバージョンがあります → 更新」が出る。記入中に勝手にリロードはしない。

## 制限事項

- **初回だけはオンラインが必要**（キャッシュを作るため）。`OFFLINE OK` を確認してから機内へ。
- iOS は数週間使わないと保存データやキャッシュを破棄することがある。
  出発前に一度オンラインで起動しておくと確実。大事なログは `JSON保存` でファイルに残す。
- `PDF保存` は印刷ダイアログ経由。ホーム画面起動（standalone）では印刷が開かない場合があるため、
  紙／PDF が必要なときは Safari のタブで開いて実行するのが確実。
  印刷時は ETO（手入力したものは `*` 付き）と記入済みの ATO / ALT / RMG / SAT / SPOT WND が
  そのまま出て、未記入の欄は書き込み用の黒枠になる。
