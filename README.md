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
