# rendering.md — レンダリングパイプライン（yakkan-synth 差分）

> `docsynth/render/` / `layout/` / `verify/` / `numbering.py` / 各ファミリーの styles を触る作業では、
> **着手前に必ず本ファイルと基底仕様を読む**こと。
>
> 基底仕様：`../insurance-contracts/docs/rendering.md`（技術選定・CSS 規約・番号付け・
> 目次/ヘッダ/フッタ/脚注・表・図(SVG)・bbox 抽出・verify・ページ数制御）。
> **WeasyPrint 70.0 の probe 実測 22 項目（`../insurance-contracts/docs/decisions.md` 付録）は
> 本プロジェクトでも前提**であり、再実測しない。WeasyPrint の版を上げるときだけ再 probe する。
> 本ファイルは汎用化に伴う**差分だけ**を書く。

## 1. 継承する結論（要点の再掲。根拠は基底仕様）

- Jinja2 → HTML → WeasyPrint 70.0（版固定）→ PDF。検証は pdfplumber + pypdfium2。PyMuPDF 不使用。
- bbox は `doc.pages[i]._page_box`（私的API）の walk。CSS px→pt（×0.75）、原点左上。
  text_lines は LineBox 単位。ヘッダ/フッタ判定は MarginBox の `at_keyword`。
- 見出しのラベルと文言の間隔は margin ではなく U+3000 の文字で空ける。`body { margin: 0 }` 必須。
- `<table>` 直接の `column-span` は効かない（wrapper で包む）。`float: footnote` は未対応。
- SVG `<text>` は `font-family`/`font-size` を必ず明示。SVG 内部は box ツリーに現れない
  （図の正解は `layout.figures[].nodes` が担う）。
- **段またぎ要素があると以降の内容が黙って捨てられることがある**。render の内容欠落検出
  （全要素 ≥1 fragment）を常に有効に保つ。「レンダリング成功≠内容が全部載った」。

## 2. テンプレートの構成（変更点）

yakkan の単一テンプレート群を「コア基盤＋ファミリー上書き」に分ける。

```
docsynth/render/templates/base/     # 機構：ページ骨格・見出し・段落・リスト・表・図・脚注・目次
families/<f>/styles/templates/      # MAY：ファミリー固有ブロックの部分テンプレート上書き
```

- 解決順：ファミリー → base（Jinja2 の ChoiceLoader）。上書きは**部分テンプレート単位**
  （`parties.html` など）に限り、ページ骨格（`page.html`）の上書きは禁止
  （bbox 抽出・verify の前提が壊れるため）。
- style YAML の形は yakkan と同じ（判型・段組・フォント・罫線・palette・chars_per_page_estimate）。
  `chars_per_page_estimate` は style 新設時に `scripts/calibrate_styles.py`（yakkan から移植）で実測する。

## 3. 新ブロックの描画仕様

### 3.1 parties（当事者表示）
- style の `parties_style: table | lines` で表形式（「委託者／受託者」2 行）か行形式
  （「株式会社〇〇（以下「甲」という。）」の段落列）を選ぶ。
- 文字列はすべて `meta.parties` から build が導出した `derived.plain_text` を描画する。手書き文字列なし。

### 3.2 signature（後文・記名押印欄）
- 後文（本文段落）＋日付行＋当事者ごとの記名ブロック（住所／名称／代表者＋「印」）。
- 「印」は文字として描画し、丸枠は CSS の border（円）。画像・擬似印影は使わない。
- 記名ブロックは `break-inside: avoid`。ページ末尾で欄だけ次ページに送られるのは**許容**
  （実在文書でも起きる）が、後文と日付が分離してはならない（同一 wrapper に入れる）。
- 各記名行にも id を振り、bbox を `layout.elements` に載せる（読み取り正解）。

### 3.3 revision_history（改定履歴）
- semantic_type `history` の表として描画（制定・改定日 × 内容）。文書末尾または冒頭
  （blueprint の `revision_history.position`）。

### 3.4 深い入れ子リスト（terms で多用）
- 基底仕様どおり CSS grid のぶら下げインデントで組む。3 階層（(1) → ア → (ｱ)）までを
  サポートし、それ以上は lint L04 で構成の見直しを要求する（自動縮小しない）。

## 4. ファミリー別の既定 @page

| family | 判型 | ヘッダ | フッタ | 備考 |
|---|---|---|---|---|
| contract | A4 1段 | なし（実物は無ヘッダが多い） | 中央ページ番号（`- 1 -` 型） | 契約書番号を右上に置く variant あり |
| terms | A4 1段 | 文書題名（小） | ページ番号 | Web 印刷風 style ではフッタに URL（example.jp）と日付 |
| regulations | A4/B5 1段 | 規程名＋章名（string-set） | ページ番号＋規程番号 | 約款に近い |
| insurance | yakkan の style をそのまま移植 | | | |

ヘッダ・フッタは基底仕様どおり `layout.pages[].header/footer` にのみ入れ、
reading_order・`answer.pages[].text` に含めない。

## 5. verify の差分

基底仕様の検査（ページ数・フォント被覆・テキスト往復・目次一致・fragment 存在・はみ出し/重なり・決定論）
に追加：

- V-P1：`signature` の記名文字列が `meta.parties` と一致（往復比較に含める）。
- V-P2：ページ上限は blueprint の `page_limit` を読む（既定 20）。
- V-P3：目次を持たない文書（契約書）では目次検査をスキップし、その旨を verify レポートに明記する
  （黙って通さない）。

## 6. 要probe（本プロジェクトで新たに確認が必要なもの）

| 項目 | 何を確かめる | いつ |
|---|---|---|
| 記名押印欄の「印」丸枠 | border-radius 円と文字の重ね（inline-block 積み）が bbox 抽出で 1 要素に収まるか | P3 冒頭 |
| フッタ `- 1 -` 型ページ番号 | `content: "- " counter(page) " -"` の文字列が layout.pages[].footer に正しく載るか | P3 冒頭 |
| 3 階層入れ子リストの grid | 深い grid 入れ子で LineBox の element_id 対応が崩れないか | P4 冒頭 |

probe は `scripts/probe_*.py` に書き、結果を `docs/decisions.md` と `docs/gotchas.md` に記録してから
設計を確定する。憶測で実装しない。
