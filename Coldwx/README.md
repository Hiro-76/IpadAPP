# Cold Wx 離陸適用性能

`Cold Wx TYPE Ⅳ 2026.02 REV4` の **離陸適用性能** シートを、iPad で動くオフライン
アプリにしたもの。滑走路 3 区分の雪質・積雪深と RWYCC を選ぶと、適用性能が出る。

公開 URL: `https://hiro-76.github.io/IpadAPP/Coldwx/`

端末内で完結し、外部への通信は一切しない。NAVLOG（`…/IpadAPP/`）や風計算
（`…/IpadAPP/wind/`）とは独立した PWA なので、別アイコンとしてホーム画面に追加できる。

---

## iPad での使い方

1. **Safari** で公開 URL を開く
2. ヘッダー右のバッジが `CACHE …` → **`OFFLINE OK`** に変わるまで数秒待つ
3. 共有ボタン <kbd>⤴</kbd> → **「ホーム画面に追加」**
4. 機内モードにしてアイコンから起動 → そのまま使える

選んだ内容は端末内に残るので、次に開いたときも前回のままになる。`リセット` で初期状態へ。

---

## 画面

| 欄 | 入れるもの |
|---|---|
| **型式** | `200＆300` か `300ER＆F` |
| **滑走路 3 区分 A / B / C** | 区分ごとの雪質（DRY SNOW / WET SNOW / SLUSH / ICE or COMPACTED SNOW）と積雪深 |
| **RWYCC** | 前方（向こう側）2 区分のうち最も滑り易い RUNWAY CONDITION CODE または BRAKING ACTION REPORT |

結果は 2 つ出る。

- **適用性能** — 例 `35/25mm・MP`。離陸不可・離着陸不可のときは赤。
  数値の下に、元表のどの行で判定したか（例 `該当: SLUSH 4～6（元表 18 行）`）を出すので、
  元表と突き合わせて確認できる。
- **INCH → mm** — 整数部（`0+`〜`3+`）と小数部を選ぶと mm が出る。元表の換算表そのまま。

`A と同じ内容を B・C にも入れる` にチェックすると、A の雪質と積雪深が 3 区分すべてに入る。

### 注記（元表の記載）

- ICE or COMPACTED SNOW 選択時の積雪深は適用されない
- RWYCC 6 は RWYCC 5 として扱う
- 積雪等割合 10％未満の場合は DRY、RWYCC 6
- 積雪深 NR は 0ｍｍ を入力

---

## 元表との対応

数値と判定条件は `Cold Wx TYPE Ⅳ 2026.02 REV4.xlsx` から写したもので、アプリ側で
独自に足した判断は無い。

| アプリ | 元表 |
|---|---|
| 適用性能の表（18 行 × RWYCC 6 列） | `DATA ` シート `F4:K25` |
| どの行を使うかの判定 | `DATA ` シート `L4:L25` の各 IFS |
| 積雪深の選択肢と判定に使う値 | `DATA ` シート `H30:I40` |
| INCH → mm | `DATA ` シート `B29:F53` |
| 入力欄・型式・RWYCC の選択肢 | `離陸適用性能 ` シートの入力規則 |

元表の `L` 列は「より厳しい行が YES なら自分は NO」という作りで、最後に
`MATCH("YES", L4:L25, 0)` が **上から最初の YES** を採る。アプリも同じ順で探す。

---

## 2026-11-22 に元表側で直した 3 点

写すときに見つかった不整合。**いずれも元表側で修正済みで、アプリはその修正後に
合わせてある。** 古い版の表（`Cold Wx TYPEⅣ 2026.02 REV4.xlsx` の 11/22 07:45 以前の
コピーなど）と見比べると、下の 2 と 3 で答えが変わるので注意。

### 1. 型式の `＆` が全角と半角で食い違っていた

入力規則のドロップダウンは `200＆300` / `300ER＆F`（全角 ＆）なのに、`DATA ` シートの
判定式は `="200&300"` / `="300ER&F"`（半角 &）で比べていた。別の文字なので型式の条件が
常に不成立になり、DRY 0〜15 / WET 0〜11 / SLUSH 0〜3 という浅い積雪で適用性能が
`#N/A` になっていた。

元表は判定式側を全角 `＆` に統一して解決。アプリは当初から同じ文字として照合して
いたので、挙動に変更は無い。

### 2. WET SNOW 7〜11ｍｍ × 300ER＆F に該当する行が無かった

ER 用の 12 行が `積雪深 < 11` で、選択肢「7～11ｍｍ」の判定値は 11。どちらの行にも
入らず `#N/A` になっていた（非 ER の 11 行は `< 12`）。

元表は 12 行を `< 12` に修正。アプリも `ROWS` の id 12 を `mm < 12` に合わせた。
RWYCC 2 なら `15/11mm・MP` が出る。

### 3. SLUSH 全区分の行の選ばれ方

23 行（`12mm・SLUSH`）の条件が成立しても、22 行（`6mm・SLUSH`）の抑止条件に 23 行が
入っておらず、上から探す仕組みの都合で 22 行が先に選ばれていた。性能上きつい側に振れる。

元表は 2 箇所直した。22 行の抑止条件に 23 行を追加し、あわせて **L23 の条件を
`OR(M30>=12,…)` から `OR(M30>=11,…)`** に変更（行の名前どおり「7～11ｍｍ」と「12ｍｍ」の
両方を拾う）。アプリも `ROWS` の id 22 の `sup` に `23` を足し、id 23 の条件を
`mm >= 11` に合わせた。

全区分 SLUSH のときの結果は次のようになる。

| 積雪深 | 該当行 | 適用性能（RWYCC 5） |
|---|---|---|
| 0～3ｍｍ | 21 行 SLUSH ALL 0～3 | `3mm・SLUSH M` |
| 4～6ｍｍ | 22 行 SLUSH ALL 4～6 | `6mm・SLUSH` |
| 7～11ｍｍ | 23 行 SLUSH ALL 7～12 | `12mm・SLUSH` |
| 12ｍｍ | 23 行 SLUSH ALL 7～12 | `12mm・SLUSH` |
| 13ｍｍ 以上 | 24 行 | `離着陸不可` |

> 途中、L23 が `OR(M30=11,…)`（11 ちょうど）だった時期がある。それだと 12ｍｍ のとき
> 23 行が NO になり、23 行に抑えられていた 19 行（`SLUSH 7～12`、全区分でないときの行）が
> 先に成立して `70/50mm・MP` が出ていた。`>=11` で解消済み。

---

## HOLD OVER TIME タブ

ヘッダーのタブで **離陸適用性能** と **HOLD OVER TIME** を切り替える。最後に見ていた
タブは次回も開く。

出典は離陸適用性能とは別で、**B777-26-09 AIRPLANE OPERATIONS MANUAL Bulletin
（Effect. NOV 06, 2026）**。スプレッドシートではなく、この Bulletin の表をそのまま写した。

> スプレッドシート（`Cold Wx TYPEⅣ 2026.02 REV4`）の HOT 値は Bulletin と違っていた
> （例: GENERIC -3 and above 100/0 の Snow Light が 1:00 / Bulletin は 0:55）。
> さらにスプレッドシートはレンジの**上限しか持っていない**（`1:15 – 2:15` が `2:15` だけ）。
> HOT はレンジで示されるものなので、Bulletin を正とした。

### 入れるもの

| 欄 | 内容 |
|---|---|
| 液種 | 9 種（GENERIC / KILFROST ABC-S PLUS / CLARIANT SAFEWING MP IV LAUNCH・LAUNCH PLUS / ABAX ECOWING AD-49 / DOW UCAR ENDURANCE EG106・FLIGHTGUARD AD-49 / CRYOTECH POLAR GUARD ADVANCE・XTEND） |
| 混合比 | 100/0 / 75/25 / 50/50 |
| OAT | 数値入力。入れると該当の OAT 帯を表示し、LOUT 未満なら「範囲外」と出す |
| 降水現象 | FZFG・Freezing Mist・IC / SN with FZFG / SN/SG/GS（SNOW PELLET，Blowing・Drifting Snow を伴う場合を含む） / FZDZ / -FZRA / SNRA・RASN / Rain on Cold Soaked Wing |
| 降雪強度 | Heavy / Moderate / Light / Very Light（SN を選んだときだけ出る） |

### 出るもの

- **適用 HOT** — レンジはそのままレンジで出る（`1:15 – 2:15`）。Guideline が無い欄は
  「Guideline なし（離陸に先立ち翼上面点検）」、混合比の設定が無い欄は「設定なし」。
  下に液種・OAT 帯・混合比・降水現象を出すので、Bulletin と突き合わせられる
- **Active Frost** — OAT と混合比から Type IV を出す（Type II と Type I 0:45 も併記）
- **Ice Pellet / Small Hail** — 液種の EG/PG に応じた Allowance Times。
  VR 115kt の CAUTION が付く欄ではその注意も出す
- **視程からの降雪強度判定** — Snowfall Intensity Conversion Table。視程と昼夜を選ぶと
  OAT から -1℃ の境を見て強度を判定し、**降雪強度へ自動で入る**。
  METAR の通報強度ではなくこの表の判定を使う決まりのため、既定で反映する。
  判定が入ったボタンには `◂視程` が付く

  手で別の強度を選ぶこともできる。手動の選択は、視程・昼夜・OAT を変えて判定が
  変わるまで残る（変わったらまた自動で入り直す）。

  この表で判定する現象は SN / SG / Snow Pellets、Blowing・Drifting Snow を伴うもの、
  それらと Ice Crystal (IC) の Mixed Condition、SN FZFG、SN RA・SN DZ。
  そのため視程の欄は SN / SN FZFG / SNRA の 3 つで出る（強度で列が分かれるのは SN だけ
  なので、SN FZFG と SNRA では判定の表示だけ）

### NOTES 欄

画面いちばん下の NOTES は、元表 Hold Over Time シートの B12・B13・B14 の 3 項目だけ。

- ① FZDZ、-FZRA 区別がつかない場合は -FZRA
- ② SN と IC の MIX Condition は SN
- ③ Small Hail が通報された場合は同等強度の Ice Pellets を適用

Bulletin の他の NOTE は、まとめて並べるのではなく**関係する場面で出す**（下の
「降水現象ごとの適用条件」、Heavy のときの表示、範囲外のときの表示）。

### 降水現象ごとの適用条件

降水現象を選ぶと、その欄に付いている Bulletin の NOTE を下に出す。

| 降水現象 | 出る NOTE |
|---|---|
| FZFG / Freezing Mist / IC | 注 1（Mist が単独で発生している場合のみ Freezing Mist と判断）、注 2（IC との Mixed は FZFG の表） |
| SN with FZFG | 注 3（Heavy は含まれない） |
| SN/SG/GS（SNOW PELLET） | 注 3、注 4（IC との Mixed は SN の表）、注 5（GS は Snow Pellets と確認できる場合のみ） |
| FZDZ | 注 6（Light/Moderate/Heavy FZDZ を含む。-FZRA と判別がつかない場合は -FZRA の表） |
| -FZRA | 注 6（判別がつかない場合はこちら）、Moderate / Heavy FZRA は Other で離陸不可 |
| SNRA / RASN | 注 7（Moderate Snow のときのみ）、注 8（OAT 0℃ 超のときのみ） |
| Rain on Cold Soaked Wing | 注 8（OAT 0℃ 超のときのみ） |

**注 8 は計算にも効く。** 列見出しの `Moderate Snow mixed with Rain⁷⁾⁸⁾` と
`Rain on Cold Soaked Wing⁸⁾` に付いている注 8 は「OAT が 0℃ を超える場合にのみ適用する。
0℃ 以下の場合は Holdover Time の Guideline は設定されていない」。

表の `-3 and above` の帯に値があっても、OAT が 0℃ 以下ならこの 2 欄は引けない。
アプリはその場合 **「適用外（OAT 0℃ 以下）」** と出し、注 8 と、0℃ 超なら引ける値を
添える。「Guideline なし」（表に値が無い）とは別物なので文言を分けてある。

> Rain on Cold Soaked Wing が氷点下でいつも適用外になるのは表どおり。
> 冷え切った主翼に「凍らない雨」が当たる条件なので、OAT 0℃ 超でしか成立しない。

### 降雪強度が効く 3 つの欄

降雪強度の判定（視程からの自動反映、手動変更）と、その強度に応じた Holdover Time は
次の 3 欄で働く。

| 欄 | 強度の効き方 |
|---|---|
| SN/SG/GS | 表が Moderate / Light / Very Light の 3 列に分かれているので、その列を引く |
| SN with FZFG | 1 列だがレンジなので、**短い方が Moderate、長い方が Light**（注 3 で Heavy は除外） |
| SNRA / RASN | **Moderate のときだけこの欄**。Light / Very Light は注 7 により **-FZRA の欄**を引く |

**レンジの読み方。** `0:20 – 0:40` のように幅がある欄は、短い方が Moderate、長い方が
Light。アプリは選んだ強度に応じてどちらかを出し、下に元のレンジと根拠を添える。
Very Light は長い方を当てる（表のレンジは Moderate–Light のため）。

### Heavy のとき

Heavy Snow には Holdover Time の Guideline が無い。適用 HOT の欄は
**翼上面点検（5 min）** と赤で出し、「離陸前 5 分以内に翼上面点検を実施する
（Operations in Heavy Snow）」を添える。降雪強度のボタンにも Heavy があるので、
視程から Heavy が出たときも手で選んだときも同じ表示になる。

SNRA / RASN は Moderate Snow のときだけの欄なので、判定が Moderate でないときは
「-FZRA の表を使う」と出す。

### データの場所

`index.html` の `HOT_FLUIDS`（9 液種 × 10 行 × 9 列）、`CONV_ROWS`、`FROST_ROWS`、
`PL_TABLE`。Bulletin が改訂されたらここを差し替える。

---

## ファイル

| ファイル | 内容 |
|---|---|
| `index.html` | アプリ本体。表・判定・画面すべてを含む 1 ファイル |
| `sw.js` | オフライン用 Service Worker。scope は `Coldwx/` のみ |
| `manifest.webmanifest` | ホーム画面追加用 |
| `icons/` | アイコン 6 サイズ |

**更新したとき**は `sw.js` の `VERSION`（現在 `coldwx-v1.1.4`）を上げる。上げないと、
ホーム画面から起動した iPad が古いキャッシュのまま開く。上げておけば、起動時に
「新しいバージョンがあります」が出て `更新` で入れ替わる。

判定のデータは `index.html` の `ROWS` / `DEPTHS` / `INCH` にまとまっている。
元表が改訂されたらここを差し替える。各行の `id` は元表の行番号と同じにしてある。

---

## 動作確認

ヘッドレスブラウザで実際に動かし、元表の各行・境界・INCH 換算の 25 ケース、HOLD OVER TIME は 59 ケースが
元表と一致することを確認済み。元表自身が計算している例
（全区分 ICE・RWYCC 1・ER → `15/11mm・P`、INCH `3+` と `0.25` → `83mm`）も一致する。

---

> このアプリは手順書の代わりではない。**正式な手順書が優先する。**
> 値が合わないと感じたら元表で確認すること。
