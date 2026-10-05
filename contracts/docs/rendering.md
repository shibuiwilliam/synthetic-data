# rendering.md — レンダリングパイプラインと検証（yakkan 差分）

> `keiyaku/render/` / `layout/` / `verify/` / `numbering.py` / `styles/` を触る作業では、
> **着手前に必ず本ファイルと基底仕様を読む**こと。
>
> **基底仕様＝`../insurance-contracts/docs/rendering.md`**（技術選定・CSS 規約・番号付け・目次/ヘッダ/フッタ/
> 脚注・表・図(SVG)・bbox 抽出・verify・ページ数制御）。
> **WeasyPrint 70.0 の probe 実測 22 項目（`../insurance-contracts/docs/decisions.md` 付録）は本プロジェクトでも
> 前提**であり、再実測しない（WeasyPrint の版を上げるときだけ再 probe する）。
> 本ファイルは**差分だけ**を書く。

## 1. 継承する結論（要点の再掲。根拠は基底仕様と `../insurance-contracts/docs/gotchas.md`）

- Jinja2 → HTML → **WeasyPrint 70.0（版固定）** → PDF。検証は pdfplumber + pypdfium2。PyMuPDF 不使用（AGPL）。
- bbox は `doc.pages[i]._page_box`（**私的 API**）の walk。CSS px → pt（**×0.75**）、原点左上。
  `text_lines` は LineBox 単位。ヘッダ/フッタ判定は y 座標ではなく **MarginBox の `at_keyword`**。
- 見出しのラベルと文言の間隔は margin ではなく **U+3000 の文字**で空ける。`body { margin: 0 }` 必須。
- `<table>` 直接の `column-span` は効かない（wrapper で包む）。`float: footnote` は未対応。
- SVG `<text>` には `font-family` / `font-size` を**必ず明示**（無指定はシステムフォントが埋め込まれて
  再現性が壊れる）。SVG 内部は box ツリーに現れない——図の正解は `layout.figures[].nodes` が担う。
- **段またぎ要素があると以降の内容が黙って捨てられる。** render の内容欠落検出
  （全要素 ≥1 fragment、`_assert_nothing_dropped`）を常に有効に保つ。**「レンダリング成功≠内容が全部載った」。**
- ルビ（`<ruby>` / `display: ruby`）と縦組み見出し（`transform: rotate`）は**実測済みで不採用**
  （正解が作れない体裁は足さない）。`{ruby:}` トークンは残すが描画しない。
- PDF のメタデータ日時を固定しないとバイト差分が出る（**テキスト層一致を必須、バイナリ一致は目標**）。
- macOS：Homebrew の dylib は dyld の既定検索パスに無い。`make` 経由で
  `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が渡る。素の `uv run` では自分で付ける。

## 2. yakkan で実害から確定した描画規約（本プロジェクトでは最初から採用する）

**いずれも実際の欠陥から確定した規約であり、移植時に逆行させない。**

| 規約 | 理由（yakkan の実害） |
|---|---|
| フォントは **`.ttf`（TrueType 輪郭）**を同梱・埋め込み。`pdffonts` で `CID Type 0C` が無いことを検査 | `.otf`（CFF）埋め込みは macOS Preview / Quick Look で本文が空になる（41 文書中 26 文書）。pdfplumber・pdfium・poppler では読めるため**往復検証では検出できない** |
| 目次のリーダー罫は `leader(' ')` ＋ `text-decoration: underline dotted`。**`leader('.')` 禁止・`border-bottom` 禁止** | `leader('.')` は「.」がテキスト層に載り、完璧に読んだページの CER が 0.775 になった。`border-bottom` は行が 0.4pt 高くなりページ送りが崩れ、別ジャンルの脚注が消えた |
| 目次は**2 パス描画**（1 パス目で実ページを測り、2 パス目で番号を文字として埋める） | `target-counter` は長い目次で収束せず、印字と実ページが食い違う |
| 目次・長い段またぎ要素は段組コンテナの**外**に置く。章見出しは `column-span: none` | 段組内の 1 ページ超の span-all 要素は以降の内容を黙って捨てる。改ページ制御も効かない |
| 表題は `<figcaption>` ではなく **`<table>` の `<caption>`**（表の中） | 段・ページ境界で表題だけが取り残される（23/320 表 → 0） |
| ヘッダの章名は `string(chapter, first)`、経路は `data-headerpath` の**1 本の文字列**で渡す | `start` は章の開始ページで前章名/空になる（実測 first 87.6% vs start 53.7%） |
| フッタのページ番号は文書の `digit_style` に合わせる（`@counter-style` で全角数字） | 本文が全角なのにページ番号だけ半角になる |
| `page_break` は段組コンテナを閉じて開き直す | `break-before: page` は multicol 内で効かない（5 通り試して全滅） |
| 図の辺ラベルは `Svg.edge_label()`（衝突時に下へずらす・白下地・**最後に描く**） | ラベルの重なり・連結線の文字貫通は verify では検出できない（目視でのみ発覚） |
| ラベル欄の固定幅は使わない（`max-content` か「その style の最長ラベル」から決める） | 固定幅は両方向に壊れる（脚注マーカーが折れる／広げると別文書の脚注が消える） |
| `chars_per_page_estimate` は**実コーパスから較正**（新 style は 1 本描いて確かめる） | 合成較正は `break-inside: avoid` のせいで段落単位に量子化され、別版面が同値になる |
| `{ref:}` は地の文と同じ見た目（`a { color: inherit; text-decoration: none }`） | リンク体裁は文書らしさを壊す（PDF 内部リンクとしては生かす） |

## 3. テンプレートの構成

yakkan の単一テンプレート群から、保険固有の前付け（表紙・目的別もくじ・特約一覧・ペットネーム表）を外し、
契約書のブロックを足す。**ページ骨格（`page.html`）の構造は変えない**（bbox 抽出・verify の前提が壊れる）。

```
keiyaku/render/templates/
  page.html          # ページ骨格（@page・ヘッダ/フッタ・段組コンテナ）。構造は yakkan のまま
  body.html          # 本文の走査（Node の再帰）
  parts/preamble.html  parts/parties.html  parts/head_matter.html
  parts/signature.html parts/commentary.html  parts/revision_history.html   ← 新規
  parts/table.html   parts/figure.html  parts/footnotes.html  parts/toc.html   ← yakkan から
```

## 4. 契約書固有の描画仕様

### 4.1 parties（当事者表示）
- style の `parties_style` で `table`（「委託者／受託者」の 2 行表）か `lines`（段落の列）を選ぶ。
- 文字列は**すべて** `meta.parties` から build が導出した `derived.plain_text` を描画する。手書き文字列なし。

### 4.2 preamble（前文）
- 無番号の段落 1〜2 本。`{party:...|full}` が「株式会社◯◯（以下「甲」という。）」に解決される。
- **字下げは 1 字（`text-indent: 1em`）**。条文と同じ体裁にする（前文だけ別扱いにしない）。

### 4.3 head_matter（頭書）
- 大型の表（`semantic_type: head_matter`）を版面幅いっぱいに置く。**行数が多く 1 ページを超えやすい**ので
  `repeat_header: true` を既定にし、繰返し表頭は `repeated: true` で往復比較から除外する。
- 見出しは「頭書」の 1 語（`kind_label`）。`{ref:head}` の解決先になる（`docs/schema.md` §11.1）。
- **要probe**：版面幅を超える列数のとき WeasyPrint は黙ってはみ出す。verify のはみ出し検査で捕まえる。

### 4.4 signature（後文・契約日・記名押印欄・収入印紙欄）
- 構成：後文（段落）→ 契約日（右寄せまたは中央）→ 当事者ごとの記名ブロック（住所／名称／代表者＋「印」）
  →（`stamp_duty` が true なら）収入印紙欄。
- 「印」は**文字として描画**し、丸枠は CSS の border（円）。画像・擬似印影は使わない。
- 収入印紙欄は枠と「収入印紙」の文字のみ。
- 記名ブロックは `break-inside: avoid`。**後文と契約日は同一 wrapper に入れて分離を禁じる**
  （ページ末尾で記名欄だけが次ページに送られるのは実物でも起きるので**許容**）。
- style の `signature_layout` で縦並び（`vertical`。2 者を上下に）と横並び（`horizontal`。2 者を左右に）を選ぶ。
- 各記名行に id を振り、bbox を `layout.elements` に載せる（**読み取り正解に含める**）。

### 4.5 form_fields（様式型の記入欄）
- 罫線の太い表。**行見出し（項目名）列は `role: stub`**、`header_cols` を必ず宣言する（L17）。
- 選択欄は `☑` / `□` をセルのテキストとして持つ（`docs/schema.md` §11.2）。
  **L07 のフォント被覆検査を render 前に必ず走らせる**（被覆が無ければ代替記号に落として decisions に記録）。
- セル内で改行を伴う長文が入るので `break-inside: avoid` を行単位で付け、ページ境界での分断を許容する。

### 4.6 commentary（逐条解説。P5）
- 対象条の直後に枠つき（`box` と同系の CSS）で置く。`region: "commentary"` として `layout.text_lines` に載る。
- **本文とフォントサイズ・地色を変える**（実物の解説枠は 1〜1.5pt 小さく、薄い地色か罫線囲み）。
- `answer.pages[].text` には**含める**（紙面にあるものは正解テキストに入れる）。

### 4.7 schedule（別紙・別表・様式）
- `kind_label` ごとに改ページして始める（`page_break`）。見出しは「別紙1　業務内容」の 1 行。
- 別紙の中は独立した番号体系（`numbering` の `schedule` レベル）。本文の条番号に影響しない。

## 5. doctype 別の既定 @page

| doctype 群 | 判型・段組 | ヘッダ | フッタ | 目次 |
|---|---|---|---|---|
| 条文型（nda / outsourcing / delegation / consulting） | A4 1 段 | なし（variant で右上に契約書番号） | 中央に `- 1 -` | なし |
| 頭書型（lease） | A4 1 段 | なし | 中央に `- 1 -` | なし |
| 目録型（purchase / license） | A4 1 段 | なし | プレーン数字 | なし（license の章あり variant のみ） |
| 様式型（employment） | A4 1 段（P8 で A3 縦） | 様式番号（右上） | プレーン数字 | なし |
| 長文型（contracting / sysdev） | A4 1 段 | 題名＋章名（`string(chapter, first)`） | プレーン数字 | **あり**（2 パス描画） |

ヘッダ・フッタは基底仕様どおり `layout.pages[].header/footer` にのみ入れ、
`reading_order` と `answer.pages[].text` に**含めない**（`text_with_furniture` にのみ含める）。

## 6. verify の差分

基底仕様の検査（ページ数・フォント被覆・テキスト往復一致・目次一致・fragment 存在・はみ出し/重なり・決定論）に
追加する：

| # | 検査 | 内容 |
|---|---|---|
| V-P1 | 記名押印欄の整合 | `signature` の記名文字列（名称・住所・代表者）が `meta.parties` と一致（往復比較に含める） |
| V-P2 | ページ上限 | blueprint の `page_limit`（無指定なら 12、絶対上限 20）を読む |
| V-P3 | 目次なし文書 | 目次を持たない文書では目次検査をスキップし、**その旨をレポートに明記**（黙って通さない） |
| V-P4 | CFF 埋め込み無し | PDF の埋め込みフォントに `CID Type 0C` が無い（§2 の `.ttf` 規約の検査） |
| V-P5 | 当事者呼称の紙面一致 | `derived.party_uses[]` の `rendered` が PDF のテキスト層に出現する（`{party:}` の解決漏れ検出） |

## 7. 要probe（本プロジェクトで新たに確認が必要なもの。憶測で実装しない）

| 項目 | 何を確かめる | いつ |
|---|---|---|
| ~~記名押印欄の「印」丸枠~~ | **済（2026-09-26）**：`inline-block`＋`border-radius: 50%` で 1 断片・34.8×34.8pt・行の内側・文字はテキスト層に載る（decisions 41） | — |
| ~~`signature_layout: horizontal`~~ | **済（2026-09-26）**：`flex`＋`flex: 1 1 0` で左右に並び、**読み順は DOM 順と一致**（decisions 42） | — |
| ~~`- 1 -` 型フッタ~~ | **済（2026-09-26）**：`@bottom-center` の MarginBox として判定でき、テキスト層に載る（decisions 43） | — |
| 頭書の大型表 | 10 行以上・5 列の表がページをまたぐとき、繰返し表頭と rowspan の継続が崩れないか | P4 冒頭 |
| ☑ □ のフォント被覆 | 同梱 `.ttf` が `U+2611` / `U+25A1` を持つか。持たなければ代替記号を決める | P5 冒頭 |
| `commentary` 枠 | 枠つきブロックが段／ページ境界で割れたとき、続きが版面の外に出ないか（yakkan で実害あり） | P5 冒頭 |

probe は `scripts/probe_*.py` に書き、結果を `docs/decisions.md` と `docs/gotchas.md` に**記録してから**
設計を確定する。
