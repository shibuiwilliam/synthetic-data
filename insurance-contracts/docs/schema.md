# schema.md — データモデル（正解JSON）

> CLAUDE.md §1.1（背景と目的・検証対象の一覧表）と §5（データモデル）の全文を
> 2026-09-21 にそのまま移設したもの（一字一句の変更なし）。
> `yakkan/models.py` / `build.py` / `richtext.py` / `schema/` / `content/` / `dataset/` の
> いずれかを触る作業では、**着手前に必ず本ファイルを読む**こと。
> 仕様変更は実装より先に本ファイルを直し、`docs/decisions.md` に「日付／変更／理由／影響／状態」を追記する。
>
> **2026-09-21（P1）**：`yakkan/models.py` の実装にあたって見つかった仕様の欠落を §5.2 / §5.3 / §5.4 /
> §5.11 に追記した。追記の理由は `docs/decisions.md` の同日の行を見ること。
> 型の正本は `yakkan/models.py`、機械可読版は `schema/*.schema.json`（`uv run yakkan schema export` で再生成）。

### 1.1 背景と目的
ドキュメント読み取りシステム（OCR/レイアウト解析/VLM/構造化抽出）の開発において、実在の約款は著作権・正解データ不在・ページ数過多の問題がある。そこで、実在約款の **構造的特徴を忠実に再現した合成文書** と、その **完全な正解データ** を対で生成し、以下を検証可能にする。

| 検証対象 | 正解データで表現するもの |
|---|---|
| テキスト | ページごとの読み順テキスト、行・ブロック単位の bbox、ヘッダ／フッタ（本文と区別） |
| 章節項構造 | 部／章／節／条／項／号／細目のツリー、見出しラベル（第１条 等）と見出し文言の分離、目次との対応 |
| 表 | 論理グリッド（結合セル含む）、セル bbox、ヘッダ経路（各セルが「どの行見出し×どの列見出し」に属するか）、正規化レコード、表の意味種別 |
| 図 | 図種別（フロー／階層／時系列／ステップ／注釈付き模式図／マトリクス）、ノード・エッジ・ラベル、ノード bbox、図から読み取れるべき命題（facts） |
| 参照関係 | 条項間参照（「第２条（通知義務）」）、脚注 (*1)、用語定義の使用箇所、別表参照 |
| 質問応答 | 上記に基づく問答（locate / extract / table_lookup / figure_path など） |

---

## 5. データモデル（正解JSON）

型は TypeScript 風に記す。実装は `yakkan/models.py`（pydantic v2）とし、`schema/*.schema.json`（JSON Schema 2020-12）を `yakkan schema export` で書き出す。すべて UTF-8、`ensure_ascii=False`、インデント2、キー順は定義順（ソートしない）。

### 5.1 3層＋QA
- `source.json`：執筆者が書く内容（parts）＋ build が付与する派生値（`derived`）。スタイル非依存。
- `layout.json`：描画結果。ページ・bbox・読み順。スタイル依存。
- `answer.json`：`source` + `layout` + `derived_pages`（ページ別期待テキスト等）。評価に渡すのはこれ。
- `qa.json`：問答。

### 5.2 source.json
```ts
type Source = {
  schema_version: "1.0";
  content_id: string;        // 例 "auto-0001"
  genre: "auto"|"oneday"|"quake"|"health"|"life"|"teikan"|"travel";
  seed: number;
  meta: {
    title: string;             // 「青葉みなと総合自動車保険 普通保険約款」
    subtitle?: string;         // 「2026年10月1日以降始期契約用」
    issuer: { name: string; kind: "stock"|"mutual"; short_name: string; };  // 架空
    product_name: string; pet_name?: string;
    edition_date: string;      // "2026-10-01"
    form_code: string;         // 「Ｄ２６１００１」等（架空）
    numbering_scheme: "nonlife"|"life"|"teikan";
    digit_style: "fullwidth"|"halfwidth";
    disclaimer: string;        // 奥付に必ず入れる定型文（§7.5）
    constants?: { [key: string]: string };  // 文書内で一貫させる値。本文からは {const:key} で参照（§8 L11）
  };
  front_matter: { cover: Cover; preface?: Block[]; purpose_index?: Table; toc: { enabled: true; with_summaries: boolean; depth: 1|2|3 }; rider_index?: Table; petname_table?: Table; };
  defined_terms: TermDef[];    // 用語の定義（本文の定義表からも参照される）
  body: Node[];                // 本体（部/章/節/条…）
  appendices: Node[];          // 別紙・別表・付表（kind: "appendix"）
  back_matter: { colophon: Block[]; contact?: Block[] };
  derived?: Derived;           // build が付与（§5.8）。執筆時は書かない
};

type Cover = {                 // 表紙（§3.1 A1）。PDF に出る文字列はすべてここから導出する
  title: string; subtitle?: string; product_name?: string; pet_name?: string;
  issuer_name: string; form_code: string; notes?: RichText[];
};

type TermDef = { id: string; term: string; definition: RichText; index_kana: "ア"|"カ"|"サ"|"タ"|"ナ"|"ハ"|"マ"|"ヤ"|"ラ"|"ワ"; notes?: RichText[] };
// TermDef.id は接頭辞を課さない短い slug（"policyholder" など）。{term:policyholder} で参照する。

type Node = {
  id: string;                  // 安定ID。scaffold が付与（例 "ch1", "ch4_s3", "ch4_s3_a1", "..._p2", "..._i3"）
  kind: "part"|"chapter"|"rider"|"section"|"article"|"paragraph"|"item"|"subitem"|"subsubitem"|"appendix"|"appendix_section";
  // "rider"（特約）は番号を持たない。中の条は特約ごとに第１条から始まり、普通保険約款の
  // 章の続き番号にならない。`{ref:}` は特約の題名で指す（「携行品損害補償特約第１条」）。
  title?: string;              // 見出し文言のみ（「告知義務」）。番号ラベルは書かない
  text?: RichText;             // paragraph/item 等の本文
  summary?: string;            // もくじ用の要約（auto の章）
  blocks?: Block[];            // このノードに付随するブロック（表・図・脚注・囲み）
  children?: Node[];
  number_override?: string;           // 例外（「第１の２」など）
  number_override_reason?: string;    // その理由。number_override があるとき lint L03 が必須にする
};

type Block =
  | { type: "paragraph"; id: string; text: RichText }                     // 見出しに属さない地の文（前付け・しおり）
  | { type: "list"; id: string; style: ListStyle; items: { id: string; text: RichText; children?: ... }[] }
  | Table | Figure | Formula
  | { type: "box"; id: string; style: "note"|"caution"|"example"|"margin_note"; title?: string; anchor?: string /* 対象ノードid */; blocks: Block[] }
  | { type: "footnotes"; id: string; notes: { n: number; text: RichText }[] }   // 条末の（*n）群。条ノード直下に1つ
  | { type: "qa_heading"; id: string; question: string }                  // しおりの Q 見出し
  | { type: "page_break" };
type ListStyle = "paren_number"|"circled"|"katakana"|"paren_katakana"|"roman"|"bullet"|"none";
```

### 5.3 インラインマークアップ（RichText）
RichText は文字列。以下のトークンのみ許可（`yakkan/richtext.py` でパース。未知トークンは lint エラー）。

| トークン | 描画 | 正解での扱い |
|---|---|---|
| `{ref:<node_id>}` | 参照ラベル。同一条内の項→「（１）」、他条→「第４条（お支払いする保険金）（１）」、別表→「別表１」。`{ref:ID|short}` で「第４条」のみ | `refs[]` に target と解決文字列を記録 |
| `{fn:<n>}` | 「（*n）」 | 同一条の `footnotes` に n が存在することを lint |
| `{term:<term_id>}` | 定義語（スタイルにより太字・下線） | `term_uses[]` に記録。plain text では語のみ |
| `{b:…}` `{u:…}` | 太字／下線 | plain では除去 |
| `{ruby:漢字|よみ}` | ルビ（`<ruby>` 要probe、代替は inline-block 積み） | 期待テキストは基底文字のみ。`ruby[]` に読みを記録 |
| `{br}` | 改行 | 改行として保持 |
| `{const:<key>}` | `meta.constants[key]` の値 | `const_uses[]` に記録。数値整合（§8 L11）の土台 |
| `{auto_label}` | 列挙表の自動採番ラベル（①②…） | 列挙表（`semantic_type: "enumeration"`）のセルでのみ使える |

エスケープは `{{` `}}`。ただし `}}` が文字としての `}` になるのは最上位だけで、
`{b:…}` `{u:…}` の内側では `}` は常に閉じ括弧として扱う（`{b:重要{u:な}}` の入れ子を優先するため）。
`{ref:}` の修飾子は `|short`（条までで打ち切り・見出し文言なし）と `|full`（根からの絶対表記）の 2 つ。`第１条` のような番号ラベルを直書きしたら lint エラー（正規表現 `第[0-9０-９]+条` 等。ただし `{ref:}` 解決後の文字列は対象外）。

### 5.4 表（Table）
```ts
type Table = {
  type: "table"; id: string;
  caption?: string;            // 「別表１ 後遺障害等級表」などの表題（番号は build が付与）
  semantic_type: "definitions"|"benefit_schedule"|"enumeration"|"exclusions"|"rider_index"|"purpose_index"
                |"rate"|"coefficient"|"grade_schedule"|"surgery_schedule"|"plan_matrix"|"procedure"|"mapping"|"history"|"generic";
  layout: { header_rows: number; header_cols: number; col_widths?: number[] /* 比率 */; repeat_header: boolean;
            style?: "grid"|"horizontal"|"minimal"; span_columns?: boolean /* 2段組で段またぎ */;
            blocks_side_by_side?: number /* 横長表を n ブロック並置で描く。正解は1表のまま */ };
  grid: Cell[][];              // 行×列の論理グリッド。結合の先頭セルのみ内容を持ち、被結合位置は {merged_into: cell_id}
  records?: Record<string, string|number>[];  // 意味読み取り用の正規化レコード（列キーは header の短縮名）
  notes?: RichText[];          // 表下の注記（※、＊1）
};
type Cell = { id: string /* "<table_id>__r{r}c{c}" */; text: RichText; rowspan?: number; colspan?: number;
              role: "header"|"stub"|"body"|"note"; align?: "left"|"center"|"right"; vertical_text?: boolean };
type MergedInto = { merged_into: string };   // 結合に飲み込まれた格子位置。grid の要素は Cell | MergedInto
```
- `header_path`（build が付与）：各 body セルについて `{row_headers: string[], col_headers: string[]}`。列見出しは `header_rows` 内の同列（結合を考慮）を上から、行見出しは `header_cols` 内の同行を左から辿る。
- 列挙表（B3）は `semantic_type: "enumeration"` で、第1列に①②… の stub、第2列に本文。番号は build が付与する（`grid` には `{auto_label}` を置く）。
- 数値表（C4）で「2ブロック並置」は 1 つの Table として `grid` に表現し、`layout.blocks_side_by_side = 2` で描画側が分割する（正解は1表・列位置で区別）。

### 5.5 図（Figure）
```ts
type Figure = { type: "figure"; id: string; caption?: string; alt: string; facts: string[]; diagram: Diagram; size?: "column"|"full" };
type Diagram =
  | { kind: "flowchart"; direction: "TB"|"LR"; nodes: { id: string; label: string; shape: "start"|"process"|"decision"|"end"|"document"|"note"; col: number; row: number }[];
      edges: { from: string; to: string; label?: string; style?: "solid"|"dashed" }[] }
  | { kind: "tree"; style: "lines"|"bracket"|"nested"; root: TreeNode }               // TreeNode = { id; label; note?; children? }
  | { kind: "steps"; direction: "LR"|"TB"; steps: { id: string; title: string; detail?: string[]; asks?: string[]; docs?: string[] }[] }
  | { kind: "timeline"; unit: "day"|"month"|"year"|"label"; axis: { start: string; end: string; ticks?: string[] };
      spans: { id: string; from: number|string; to: number|string; label: string; lane?: number }[]; events: { id: string; at: number|string; label: string }[] }
  | { kind: "annotated_mock"; subject: "policy_certificate"|"claim_form"|"app_screen"; fields: { id: string; badge: number; label: string; value?: string; x: number; y: number; w: number; h: number }[]; legend: { badge: number; title: string; text: RichText }[] }
  | { kind: "matrix"; rows: string[]; cols: string[]; marks: ("○"|"×"|"△"|"－"|string)[][]; legend?: { mark: string; meaning: string }[] };
```
- `alt` は図の内容の散文説明（正解として保持）。`facts` は図から読めるべき命題（例「『警察へ連絡』の次のステップは『相手方の確認』である」）。QA の種になる。
- 最小複雑度（lint）：flowchart 5ノード以上・分岐1以上、tree 3階層、steps 4以上、timeline 4要素以上、matrix 4×3 以上。
- build が `derived.paths`（flowchart の start→end 経路のラベル列）と `derived.node_order` を付与。

### 5.6 算式・囲み・脚注
```ts
type Formula = { type: "formula"; id: string; alt: string;
  layout: "inline_boxes"|"fraction";
  terms: ({ box: string } | { op: "＋"|"－"|"×"|"÷"|"＝" } | { fraction: { num: string; den: string } })[] };
```
- 囲み `box.style = "margin_note"` は B6 の欄外解説。`anchor` に対象ノード id を必ず持つ。描画位置はスタイルで「条末」または「ページ下部（CSS footnote 領域、要probe）」。
- 条末脚注 `footnotes` は条ノード直下に 1 ブロック。番号は条ごとに 1 から振り直す（実物と同じ）。

### 5.7 layout.json
```ts
type Layout = {
  doc_id: string; content_id: string; style_id: string;
  renderer: { name: "weasyprint"; version: string; fonts: string[] };
  page_size_pt: [number, number]; page_count: number; dpi_png: 150;
  pages: { number: number; columns: number;
           header: { text: string; bbox: BBox }|null; footer: { text: string; bbox: BBox }|null;
           reading_order: string[];         // このページに現れる要素id（本文→欄外注の順、ヘッダ/フッタは除く）
           text_lines: { bbox: BBox; text: string; element_id: string; region: "body"|"margin_note"|"header"|"footer"|"figure"|"table" }[] }[];
  elements: { [id: string]: { kind: string; fragments: { page: number; bbox: BBox; repeated?: boolean /* 繰り返し表頭 */ }[];
                              label?: string; heading_text?: string } };
  figures: { [fig_id: string]: { page: number; bbox: BBox; scale: number; nodes: { [node_id: string]: BBox } } };
};
type BBox = [x0: number, y0: number, x1: number, y1: number];   // PDFポイント、原点左上、y下向き。PNG座標は dpi/72 倍
```
- 同一要素が段またぎ・改ページで分割される場合は `fragments` が複数になる。繰り返し表頭は `repeated: true` で区別し、テキスト評価では二重計上しない。
- ヘッダ・フッタ・ページ番号は `pages[].header/footer` にのみ入れ、`reading_order` に含めない。

### 5.8 derived（build が source に付与）と answer.json

**執筆物（`SourceDraft`）は `derived` を持たない。** 型で分けてあり、執筆物に `derived` を書くと
スキーマ検証で落ちる（lint L00）。`build` の出力だけが `derived` を持つ（`Source`）。

- `derived.labels[node_id]`：`{ label, title, heading_text, path: string[] /* 祖先の heading_text */, depth }`
- `derived.refs[]`：`{ from_id, to_id, rendered }`；`derived.term_uses[]`；`derived.footnote_index[]`
- `derived.plain_text[block_or_node_id]`：マークアップ除去・参照解決後の期待テキスト（ラベル含む版 `with_label` と含まない版）
- `derived.tables[table_id].header_path`, `derived.figures[fig_id].paths`
- `answer.json` = `{ source, layout, pages: [{ number, text: string /* 読み順・本文＋欄外注、ヘッダ/フッタ除く */, text_with_furniture: string }], outline: [{ id, depth, label, title, heading_text, page }] }`

### 5.9 qa.json
```ts
type QA = { id: string; type: "locate"|"extract"|"definition"|"table_lookup"|"table_reason"|"figure_path"|"figure_fact"|"crossref"|"count"|"negative"|"apply";
            question: string; answer: string|number|string[]; answer_type: "string"|"number"|"list"|"boolean";
            evidence: string[] /* 要素id */; page_hint?: number[]; source: "auto"|"authored" };
```
- 自動生成（`yakkan qa`）：見出し→ページ、条の見出し文言、表の (行見出し, 列見出し)→値、figure の次ノード、別表参照、定義語→定義、章内の条数、存在しない条（negative）。
- 執筆（Claude）：1文書 10〜20 問。自然な日本語で、答えが本文・表・図から一意に決まるもの。
- lint：`evidence` が存在し、`extract/table_lookup/definition` の answer 文字列が evidence の plain_text に含まれること。
- `apply`（場面適用）：**与えられた場面に規定を当てはめて、文書に直接書かれていない値や結論を導く**問い。
  例「入院保険金日額が５，０００円のご契約で胃の切除の手術を受けたとき、手術保険金の額は何円か」
  → 別表の給付倍率を引いて掛け算する。答えが本文の文字列にならないので**包含検査の対象外**。
  `table_lookup`（表から直接引く）や `table_reason`（表の中で比較する）と区別する。
  自動生成はしない（場面の妥当性を機械で保証できないため）。**執筆 QA 専用の型。**

### 5.10 サンプル（抜粋・記法確認用）
```json
{
  "id": "ch4_s1_a2", "kind": "article", "title": "通知義務",
  "children": [
    { "id": "ch4_s1_a2_p1", "kind": "paragraph",
      "text": "保険契約を締結した後に、下表に掲げる事実のいずれかが生じたときは、{term:policyholder}または{term:insured}は、遅滞なく、書面等により当会社にその旨を知らせなければなりません。ただし、当会社が知らせを受ける前にその事実が消滅したときを除きます。",
      "blocks": [ { "type": "table", "id": "tbl_notify_facts", "semantic_type": "enumeration",
                    "layout": { "header_rows": 0, "header_cols": 1, "repeat_header": false, "style": "grid" },
                    "grid": [ [ { "id": "tbl_notify_facts__r0c0", "text": "{auto_label}", "role": "stub" },
                                { "id": "tbl_notify_facts__r0c1", "text": "被保険自動車の主な使用地域が、保険証券に記載された都道府県以外に移ったこと。", "role": "body" } ],
                              [ { "id": "tbl_notify_facts__r1c0", "text": "{auto_label}", "role": "stub" },
                                { "id": "tbl_notify_facts__r1c1", "text": "被保険自動車に自動運行装置{fn:1}を後から取り付けたこと、または取り外したこと。", "role": "body" } ] ] } ] },
    { "id": "ch4_s1_a2_p2", "kind": "paragraph",
      "text": "当会社は、{ref:ch4_s1_a2_p1}の知らせを受けたときは、その内容を記載した書類の提出を求めることがあります。" }
  ],
  "blocks": [ { "type": "footnotes", "id": "fn_ch4_s1_a2", "notes": [ { "n": 1, "text": "運転操作の全部または一部を自動的に行う装置で、当会社所定の基準に該当するものをいいます。" } ] } ]
}
```
（上記の文は本プロジェクトのオリジナル例文。実在約款の文言を写したものではない。）

---

### 5.11 content ディレクトリの形式（parts）

執筆は 1 文書を複数ファイルに割って進める（CLAUDE.md §7.2）。`yakkan lint` / `build` はこの形を読む。

```
content/<content_id>/
  doc.json              # meta・front_matter・back_matter と、読み込む part の並び
  parts/00_front.json   # 断片。target ごとに doc へ連結される
  parts/10_terms.json
  source.json           # build の出力（執筆者は触らない）
```

```ts
type Doc = Omit<SourceDraft, "body"|"appendices"|"defined_terms"> & {
  parts: string[];      // parts/ 配下のファイル名。この順で読む
};
type Part = {
  target: "body" | "appendices" | "defined_terms" | "preface" | "colophon" | "contact";
  items: unknown[];     // target に応じて Node[] / TermDef[] / Block[]
};
```

- `body` と `appendices` は part をまたいで **並び順に連結** される。章の順序は part の順序で決まる。
- `preface` / `colophon` / `contact` は `front_matter` / `back_matter` の配列に足される。
- `doc.json` に `derived` を書くと lint L00（スキーマ検証）で落ちる。
- 最小の実例は `tests/golden/sample_min/`。
