# rendering.md — レンダリングパイプライン

> CLAUDE.md §6 の全文を 2026-09-21 にそのまま移設したもの（一字一句の変更なし）。
> `yakkan/render/` / `yakkan/layout/` / `yakkan/verify/` / `yakkan/numbering.py` / `styles/` を
> 触る作業では、**着手前に必ず本ファイルを読む**こと。
> 「要probe」項目は `scripts/probe_*.py` で実測してから設計を確定し、結果を `docs/decisions.md` と
> `docs/gotchas.md` に記録する。憶測で実装しない。
>
> **2026-09-21（P2）**：`make probe`（`scripts/probe_weasy.py`）で 22 項目を実測し、
> 結果に合わせて §6.3 / §6.5 / §6.6 / §6.7 / §6.8 を書き換えた。実測表は
> `docs/decisions.md` の付録「WeasyPrint 70.0 の probe 結果」にある。**renderer は WeasyPrint 70.0 で確定。**

## 6. レンダリングパイプライン

### 6.1 技術選定
| 役割 | 採用 | 理由 / 備考 |
|---|---|---|
| HTML 生成 | Jinja2 テンプレート（`yakkan/render/templates/`） | JSON→HTML を宣言的に |
| HTML→PDF | **WeasyPrint**（バージョン固定、`>=62`） | CSS Paged Media（`@page`、ヘッダ/フッタ、`target-counter` による目次ページ番号、多段組、表頭繰り返し）、日本語禁則を Pango が処理、SVG インライン描画 |
| 図 | 自前 Python → インライン SVG | 座標を自前で決めるので正解が自明。外部レイアウトエンジン不使用 |
| PDF 検証・抽出 | pdfplumber（テキスト/文字 bbox）＋ pypdfium2（ラスタライズ） | ライセンスが緩い（MIT / Apache-BSD）。PyMuPDF（AGPL）は使わない |
| フォント検査 | fontTools | 使用文字がフォントの cmap にあるか事前検査（豆腐防止） |
| モデル/CLI | pydantic v2 / typer / PyYAML | |
| パッケージ | uv（`pyproject.toml`、Python 3.12） | |

代替案：ReportLab（座標完全制御だが日本語組版・複雑表が弱い）。WeasyPrint の bbox 抽出（§6.8）が不安定なら `Renderer` 抽象の背後で差し替える。**判断は P2 の probe 結果で確定し `docs/decisions.md` に記録。**

### 6.2 環境・依存・フォント
- OS 依存：Ubuntu `apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev`、macOS `brew install pango`。`yakkan doctor` で検出。
- フォントは `assets/fonts/` に同梱（すべて OFL / IPA ライセンス）：Noto Serif CJK JP（Regular/Bold）、Noto Sans CJK JP（Regular/Bold）、IPAex明朝・IPAexゴシック、BIZ UDP明朝/ゴシック（バリエーション用）。記号（❶ ☞ ◆ ⅰ 等）の被覆は Noto Sans Symbols / Symbols 2 でフォールバック。`@font-face` で `file://` 参照し、`FontConfiguration` を使う。
- 取得元と版は `assets/fonts/SOURCES.md` に記録。

### 6.3 HTML/CSS 規約
- 1文書＝1 HTML（CSS・SVG インライン、外部参照はフォントのみ）。
- **`body { margin: 0 }` を必ず入れる**。既定の 8px が本文幅を左右 6pt ずつ削る（実測、docs/gotchas.md）。
- **見出しのラベルと文言の間隔は CSS の margin ではなく U+3000 の「文字」で空ける。**
  マージンで空けると PDF のテキスト層に文字が入らず、`derived.labels[].heading_text` と食い違う
  （ヘッダの `string-set` にも効く）。条だけは「第１条（告知義務）」なので区切り文字を入れない。
- **すべての正解要素に `id` と `data-kind` を付ける**（node, block, cell, figure node, header/footer 領域、ラベル span）。`layout.json` はこれらを拾う。
- 見出しは `<h1..h4 id=…><span class="label" id="…_label">第１条</span><span class="title" id="…_title">（告知義務）</span></h1>` のようにラベルと文言を別 span に。
- 項・号は CSS grid（`grid-template-columns: <label幅> 1fr`）でぶら下げインデント。ラベル span と本文 span を分離（正解でも分離、結合版も持つ）。float は使わない。
- 2段組は `column-count: 2; column-gap: 8mm; column-fill: auto`。段またぎ要素は `column-span: all`
  （**実測：ブロック要素では動く**）。ただし **`<table>` に直接指定しても効かない**ので、
  `<figure>`/`<div>` でくるんでそちらに指定する。
- `@page { size: A4; margin: 16mm 14mm 18mm 14mm; @top-left { content: string(chapter) } @bottom-center { content: counter(page) } @bottom-right { content: "<form_code>" } }`、`h2 { string-set: chapter content() }`。左右ページでヘッダを変える場合は `@page:left/:right`。
- 改ページ制御：`h1,h2,h3 { break-after: avoid }`、`tr, figure, .formula, .box { break-inside: avoid }`、表全体は `break-inside: auto`。`thead { display: table-header-group }` で表頭繰り返し。
- 日本語：`line-break: strict; word-break: normal; overflow-wrap: break-word（URL 等の長い欧文のみ）`。`text-indent` ではなく grid でインデント。禁則の見た目は Pango 任せ。
- 色は各 style の palette（本文黒＋強調色1色）。見出し帯・欄外注の背景は薄色。

### 6.4 番号付け（`yakkan/numbering.py`）
| scheme | chapter | section | article | paragraph | item | subitem | subsubitem | footnote | appendix |
|---|---|---|---|---|---|---|---|---|---|
| nonlife | 第１章 | 第１節 | 第１条（見出し） | （１）※単項なら無番号 | ①②… | ｱ.ｲ.… | (ｱ)(ｲ)… | （*1） | 別表１／付表１／別紙 |
| life | 第１章 | 第１節 | 第１条（見出し） | １．２．（単項なら無番号） | (1)(2) | ①② | ｱｲ | （注1） | 別表１ |
| teikan | 第１章 | — | 第１条（見出し） | ２３…（第１項は無番号、行頭全角） | (1)(2) | ①② | — | — | 附則 |
| group | 第１章 | 第１節 | 見出しを条の上に括弧書き＋「第１条」を本文に走り込み（`meta.article_heading: above`） | ②③…（第１項は無番号） | １．２． | (ｱ)(ｲ) | — | ❶❷（`footnote_style: remarks_box`） | 別表１ |
| jyusetsu | １（番号のみ） | （1） | **条を使わない。**丸数字の小見出し「①　主な特約の概要」（`article_heading: plain`） | 無番号 | ① | ｱ. | — | （*1） | 別表１ |

- 全角/半角は `meta.digit_style`。丸数字は ①〜⑳ まで、超過は (21) にフォールバックし lint 警告。
- `{ref:}` の解決は「参照元と参照先の最小共通祖先」に基づき相対表記（同条内の項は「（２）」、他条は「第２条（通知義務）（２）」、他章の節は「第４章第３節第１条」）。`|full` `|short` で上書き。
- 別紙内は独立体系（「第１」「１．」「①」「ｱ.」）。`appendix_section` で表現。
  定款の附則だけは項を「１」「２」、号を「（１）」にする（実物の体裁）。
- **特約は `kind: "rider"` で表す。番号を持たず、中の条は特約ごとに第１条から始まる。**
  普通保険約款の章の続き番号にしないため（`docs/shared_fixes.md` A4）。`{ref:}` は
  特約の題名で指す（「携行品損害補償特約第１条（補償内容）」）。特約の中から普通約款を
  指す参照は従来どおり「第２章第１条」。

### 6.5 目次・ヘッダ・フッタ・脚注・欄外注
- 目次は build 時に構造から生成し（`derived.toc`）、ページ番号は CSS `target-counter(attr(href), page)`
  で入れる（**実測：動く。印字された番号と実ページの一致を verify が検査する**）。
  リーダー罫は `leader('.')`（**実測：動く**）。ただし点はテキスト層に載るので往復比較では除外する。目次の各行に `id` を付け、`layout.json` に描画されたページ番号文字列を記録して実ページと突合する（§6.9）。
- ヘッダ・フッタは `@page` マージンボックス。文字列は `string-set` 由来なので JSON から導出可能。`layout.pages[].header/footer` に格納。
- 条末脚注は通常ブロックとして描画（実物と同じ）。**脚注と欄外注は、条の子ノード（項）をすべて描いた後**に置く
  （ブロックの並び順ではなく役割で決める：`yakkan/render/html.py` の `_is_trailing`）。
- 欄外注（B6）は **条末に小活字の囲み** で置く。`float: footnote` は **WeasyPrint 70.0 が未対応**で、
  指定しても本文内に残る（実測）。ページ下部配置は将来 WeasyPrint が対応したら再検討する。
- 目的別もくじ（A3）は普通の表（`semantic_type: purpose_index`）で、参照先ページ番号は `{ref:}` 相当のリンクで `target-counter` から取る。

### 6.6 表
- `<table>` + `colspan/rowspan`。`grid` の被結合セルは描画しない。各 `<td>/<th>` に cell id。
- 段またぎの表は `<figure class="table-wrap span-all">` でくるむ（`<table>` 直接の `column-span` は効かない）。
- 表頭の繰り返しは `thead { display: table-header-group }`（**実測：改ページでも段またぎでも繰り返される**）。
  繰り返されたセルは **同じ id** を持つので、`layout.json` では 2 つ目以降の fragment に `repeated: true` を立てる。
- 縦書き見出しセル（`vertical_text: true`）は `writing-mode` 非対応のため `transform: rotate(-90deg)` の内側ブロックで代替（要probe、P6）。
- 横長数値表（14列以上）は `font-size` を1段落として段またぎ（`span_columns`）。それでも溢れる場合は lint で「列数超過」として作り直しを要求（自動縮小はしない）。
- 表のセル内 RichText も §5.3 のトークンを許可。

### 6.7 図（SVG）
- `yakkan/render/diagrams/<kind>.py` が `Diagram` → SVG 文字列。viewBox は px、ノード座標はすべて Python で計算し `figure_layout`（ノード id → viewBox 内 bbox）を返す。テキスト幅は文字種別の概算（CJK 1.0em、ASCII 0.55em）で見積もり、`max_chars` で折返し。
- 文字は `<text>`。**`font-family` と `font-size` を属性で必ず明示する**：無指定だと同梱外のシステムフォント
  （実測では Arial Unicode MS）で描かれて PDF に埋め込まれ、字幅の見積りも再現性も壊れる。
  verify が「同梱フォント以外の埋め込み」を error にする。
- SVG の `<text>` は **PDF のテキスト層に載る**（実測）。往復比較では `region: "figure"` として本文から除外する。
  正解は SVG テキスト層に依存しない（`layout.figures[].nodes` に座標、`facts`/`alt` に意味）。
- flowchart：格子（`col,row`）配置、セルサイズ 150×64px、直交エッジ＋矢頭、decision は菱形、ラベル付きエッジ。
  **列が違う相手への分岐は、下辺ではなく横（左右の辺）から出して相手の上辺に入れる**（下辺から出すと本線と重なる）。
- tree：`lines`（罫線）／`bracket`（「｛」括弧）／`nested`（入れ子枠）。
- steps：横は矢羽根形（chevron）、縦は角丸枠＋下向き矢印。`detail/asks/docs` は小枠。
- timeline：横軸、レーン、区間バー、イベント旗。
- annotated_mock：模式的な証券（角丸矩形にフィールド枠、❶..⑳ バッジ）＋凡例表（凡例は Table として別ブロックにしてもよい）。
  **`fields[].x/y/w/h` は証券枠に対する 0〜1 の相対値**（px ではない）。lint L06 が範囲を検査する。
- matrix：格子＋記号、凡例。
- 配色は style palette、線幅 1px、角丸 4px。実物同様「地味で説明的」に。
  影・グラデーション・不透明度・アイコンは使わない（テストで検査している）。
- 矢頭マーカーの id は `<figure_id>__arrow` のように図ごとに分ける（1 つの HTML に複数の SVG が入るため）。
- **SVG の中身は box ツリーに現れない**（WeasyPrint は inline SVG を ReplacedBox として置く）。
  そのため `text_lines` に figure 領域の行は出ない。図の正解は `layout.figures[].nodes` の座標と
  `alt` / `facts` が担い、verify（V10）が「ノード座標が取れていること」と
  「ラベルが PDF のテキスト層から読めること」を検査する。
- 算式は SVG ではなく HTML/CSS で組む（`yakkan/render/formula.py`）。本文と同じフォント・
  同じテキスト層に載り、往復検証でそのまま比較できるため。分数は `num` を上、`den` を下に積む。

### 6.8 レイアウト抽出（bbox）
1. `doc = HTML(string=html, base_url=...).render(font_config=...)` の後、`doc.pages[i]._page_box` から box ツリーを走査（**私的API。バージョン固定と probe 必須**）。`box.element.get('id')` を持つ box の border box を CSS px→pt（×0.75）で `fragments` に追加。**座標は `border_box_x()/border_box_y()`、寸法は `border_width()/border_height()`**（`border_box_width()` は存在しない）。**box 種別で絞り込まない**（`display:grid` は GridContainerBox になるなど種類が多く、白リストにすると静かに取りこぼす）。`text_lines` は **`LineBox` 単位** で作る（`TextBox` は span ごとに割れるため細かすぎる）。
   ヘッダ・フッタの判定は y 座標ではなく **`MarginBox` の `at_keyword`**（`@top-left` 等）で行う：本文 1 行目は上マージンと同じ y から始まるため座標では区別できない。
2. 同じ id が複数ページ／段に現れたら fragments を追加（分割）。繰り返し表頭は元セル id を持つが `repeated: true`。
3. 図ノード：figure 要素の bbox と viewBox から scale を求め、`figure_layout` を変換。
4. フォールバック：pdfplumber の `chars` を読み順で並べ、期待テキストと系列整列（difflib）して要素 bbox を復元
   （`yakkan/layout/fallback_align.py`）。**突合は IoU ではなく「box ツリーの bbox が pdfplumber の文字群を
   内包するか（許容 1.5pt）」で判定する。** 実測で x は 0.00pt 一致するが y は行の余白ぶん 4〜5pt ずれるため、
   IoU 0.9 は原理的に達成できない（docs/decisions.md 2026-09-21）。段またぎで割れる要素があるので、
   判定はそのページの全 fragment の和に対して行う。
5. `doc.write_pdf()` はレイアウト後に行い、同じ `doc` オブジェクトから抽出する（再レイアウトしない）。

### 6.9 検証（`yakkan verify`）
- ページ数 ≤ 20（表紙含む）。
- 文字被覆：source の全文字がフォント cmap にある（fontTools、render 前）。render 後、pdfplumber 抽出に U+FFFD や `.notdef` 相当が無い。
- テキスト往復：answer の `pages[].text` と pdfplumber 抽出（同じ読み順規則で並べ替え）を正規化（空白・全角半角の区別は保持、行末改行は除去）して比較。**完全一致が原則**。Pango の合字・行分割による差分は正規化ルールを `yakkan/verify/normalize.py` に明文化して吸収する。
- 目次ページ番号 ＝ 各見出しの `fragments[0].page`。
- 全要素が ≥1 fragment を持つ（描画漏れ検出）。
- はみ出し：要素 bbox がページ内容域／段内に収まる（表の横溢れ検出）。
- 重なり：本文ブロック同士の bbox 重なりが無い。
- 決定論：2回レンダリングして `layout.json` が一致、PDF のテキスト層が一致（バイナリ一致は目標だが PDF 生成日時を固定してから比較）。

### 6.10 ページ数制御
- style ごとに `chars_per_page_estimate`（例：A4 2段 9.5pt ≈ 2,300字、A4 1段 10.5pt ≈ 1,600字、表は 0.6 倍、図は固定高）を持ち、`yakkan lint` が推定ページ数を出す。目標 = blueprint の `target_pages`、上限 20。推定が 19 を超えたら執筆段階で削る。
- render 後に超過したら失敗。対処は「内容を削る（執筆者）」か「style を変える（別 doc_id）」。フォント縮小で押し込む自動処理はしない（見た目の不自然さと正解の一貫性のため）。
- `yakkan render --report` が part（章）ごとの使用ページを出し、削る場所を示す。

