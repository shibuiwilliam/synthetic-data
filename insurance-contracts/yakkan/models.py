"""正解 JSON のデータモデル（docs/schema.md §5）。

**執筆物と生成物を型で分ける**

- `SourceDraft`：執筆者（Claude）が書く範囲。`derived` を **持たない**。
  `extra="forbid"` なので `derived` を書くと検証エラーになり、lint が L00 として報告する。
- `Source`：`build` が `derived` を付与したもの。`dataset/<doc_id>/source.json` の形。

JSON の書き出しは UTF-8・`ensure_ascii=False`・インデント 2・**キー順は定義順**（ソートしない）。
`dump_json()` を使うこと。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0"

Genre = Literal[
    "auto",
    "oneday",
    "quake",
    "health",
    "life",
    "teikan",
    "travel",
    # 2026-09-22 追加（docs/reference_structures.md #9〜#14）
    "golf",  # 賠償責任保険の約款集（ゴルファー保険）
    "group",  # 団体保険（法人向け）の普通保険約款＋特約条項
    "jyusetsu",  # 重要事項説明書。条を持たない説明書型の文書
]
NumberingScheme = Literal[
    "nonlife",
    "life",
    "teikan",
    # 団体保険：項＝丸数字（第1項は無番号）、号＝「１．」、細目＝(ｱ)。条見出しは条の上に括弧書き
    "group",
    # 重要事項説明書：条を持たない。章＝番号なし、節＝（N）、条の位置に丸数字の小見出し
    "jyusetsu",
]
DigitStyle = Literal["fullwidth", "halfwidth"]
NodeKind = Literal[
    "part",
    "chapter",
    # 特約。普通保険約款の章の続き番号にしないための独立した種別
    # （docs/shared_fixes.md A4）。番号を持たず、中の条は特約ごとに第１条から始まる。
    "rider",
    "section",
    "article",
    "paragraph",
    "item",
    "subitem",
    "subsubitem",
    "appendix",
    "appendix_section",
]
IndexKana = Literal["ア", "カ", "サ", "タ", "ナ", "ハ", "マ", "ヤ", "ラ", "ワ"]
ListStyle = Literal["paren_number", "circled", "katakana", "paren_katakana", "roman", "bullet", "none"]
CellRole = Literal["header", "stub", "body", "note"]
Align = Literal["left", "center", "right"]
SemanticType = Literal[
    "definitions",
    "benefit_schedule",
    "enumeration",
    "exclusions",
    "rider_index",
    "purpose_index",
    "rate",
    "coefficient",
    "grade_schedule",
    "surgery_schedule",
    "plan_matrix",
    "procedure",
    "mapping",
    "history",
    "generic",
]
BoxStyle = Literal["note", "caution", "example", "margin_note"]
QAType = Literal[
    "locate",
    "extract",
    "definition",
    "table_lookup",
    "table_reason",
    "figure_path",
    "figure_fact",
    "crossref",
    "count",
    "negative",
    #: 場面適用。与えられた場面に規定を当てはめて、**文書に直接書かれていない値や結論**を導く
    #: （「日額5,000円で胃の切除を受けたとき、手術保険金はいくらか」→ 別表の倍率を掛けて算出）。
    #: 答えが本文の文字列にならないので、L14 の包含検査の対象外にする。
    "apply",
]
AnswerType = Literal["string", "number", "list", "boolean"]

#: RichText は文字列。許可トークンは docs/schema.md §5.3（`yakkan/richtext.py` が検証する）。
RichText = str

#: bbox は [x0, y0, x1, y1]。PDF ポイント・原点左上（docs/schema.md §5.7）。
BBox = tuple[float, float, float, float]


class Model(BaseModel):
    """全モデル共通の設定。未知フィールドは許さない（仕様との乖離を早期に落とす）。"""

    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True)


# --- meta / front matter ----------------------------------------------------


class Issuer(Model):
    name: str
    kind: Literal["stock", "mutual"]
    short_name: str


class Meta(Model):
    title: str
    subtitle: str | None = None
    issuer: Issuer
    product_name: str
    pet_name: str | None = None
    edition_date: str  # "2026-10-01"
    form_code: str
    numbering_scheme: NumberingScheme
    digit_style: DigitStyle
    #: 条見出しの体裁。`inline` は「第１条（告知義務）」を 1 行の見出しに置く（既定）。
    #: `above` は見出し文言だけを括弧書きで条の上の行に置き、条ラベルを第1項の本文の
    #: 先頭に走り込ませる（団体保険の体裁。docs/reference_structures.md #12）。
    #: `plain` は「①　主な特約の概要」のように括弧を使わない（条を持たない説明書。#9）。
    article_heading: Literal["inline", "above", "plain"] = "inline"
    #: 表・図の番号の振り方。`flat` は文書内通し（「表1」）、
    #: `chapter` は章番号を含む（「表1-1」「表3-2」。docs/reference_structures.md #14）。
    caption_numbering: Literal["flat", "chapter"] = "flat"
    #: 条末脚注の体裁。`inline` は「（*1）」を条末に並べる（既定）。
    #: `remarks_box` は黒丸数字のマーカーと「第N条　備考」の枠で示す（#13）。
    footnote_style: Literal["inline", "remarks_box"] = "inline"
    disclaimer: str
    #: 文書内で一貫させたい定数（限度額・日数・等級）。本文からは `{const:key}` で参照する（§8 L11）。
    constants: dict[str, str] = Field(default_factory=dict)


class Cover(Model):
    """表紙（docs/schema.md §3.1 A1）。JSON から機械的に導出できる要素だけを持つ。"""

    title: str
    subtitle: str | None = None
    product_name: str | None = None
    pet_name: str | None = None
    issuer_name: str
    form_code: str
    notes: list[RichText] = Field(default_factory=list)


class Toc(Model):
    enabled: Literal[True] = True
    with_summaries: bool = False
    depth: Literal[1, 2, 3] = 3


# --- blocks -----------------------------------------------------------------


class ParagraphBlock(Model):
    type: Literal["paragraph"] = "paragraph"
    id: str
    text: RichText


class ListItem(Model):
    id: str
    text: RichText
    children: list[ListItem] = Field(default_factory=list)


class ListBlock(Model):
    type: Literal["list"] = "list"
    id: str
    style: ListStyle
    items: list[ListItem]


class Cell(Model):
    id: str  # "<table_id>__r{r}c{c}"
    text: RichText
    rowspan: int = 1
    colspan: int = 1
    role: CellRole = "body"
    align: Align | None = None
    vertical_text: bool = False


class MergedCell(Model):
    """結合に飲み込まれた格子位置（docs/schema.md §5.4）。内容は持たない。"""

    merged_into: str


GridCell = Cell | MergedCell


class TableLayout(Model):
    header_rows: int = 0
    header_cols: int = 0
    col_widths: list[float] | None = None
    repeat_header: bool = False
    style: Literal["grid", "horizontal", "minimal"] | None = None
    span_columns: bool = False
    #: 横長表を 2 ブロック並置で見せる場合の分割数（§5.4 の注記）。正解は 1 表のまま。
    blocks_side_by_side: int | None = None


class Table(Model):
    type: Literal["table"] = "table"
    id: str
    caption: str | None = None
    semantic_type: SemanticType
    layout: TableLayout = Field(default_factory=TableLayout)
    grid: list[list[GridCell]]
    records: list[dict[str, str | float]] | None = None
    notes: list[RichText] = Field(default_factory=list)


class FlowNode(Model):
    id: str
    label: str
    shape: Literal["start", "process", "decision", "end", "document", "note"]
    col: int
    row: int


class FlowEdge(Model):
    from_: str = Field(alias="from")
    to: str
    label: str | None = None
    style: Literal["solid", "dashed"] = "solid"


class Flowchart(Model):
    kind: Literal["flowchart"] = "flowchart"
    direction: Literal["TB", "LR"] = "TB"
    nodes: list[FlowNode]
    edges: list[FlowEdge]


class TreeNode(Model):
    id: str
    label: str
    note: str | None = None
    children: list[TreeNode] = Field(default_factory=list)


class Tree(Model):
    kind: Literal["tree"] = "tree"
    style: Literal["lines", "bracket", "nested"] = "lines"
    root: TreeNode


class Step(Model):
    id: str
    title: str
    detail: list[str] = Field(default_factory=list)
    asks: list[str] = Field(default_factory=list)
    docs: list[str] = Field(default_factory=list)


class Steps(Model):
    kind: Literal["steps"] = "steps"
    direction: Literal["LR", "TB"] = "LR"
    steps: list[Step]


class TimelineAxis(Model):
    start: str
    end: str
    ticks: list[str] = Field(default_factory=list)


class TimelineSpan(Model):
    id: str
    from_: int | str = Field(alias="from")
    to: int | str
    label: str
    lane: int = 0


class TimelineEvent(Model):
    id: str
    at: int | str
    label: str


class Timeline(Model):
    kind: Literal["timeline"] = "timeline"
    unit: Literal["day", "month", "year", "label"] = "label"
    axis: TimelineAxis
    spans: list[TimelineSpan] = Field(default_factory=list)
    events: list[TimelineEvent] = Field(default_factory=list)


class MockField(Model):
    id: str
    badge: int
    label: str
    value: str | None = None
    x: float
    y: float
    w: float
    h: float


class MockLegend(Model):
    badge: int
    title: str
    text: RichText


class AnnotatedMock(Model):
    kind: Literal["annotated_mock"] = "annotated_mock"
    subject: Literal["policy_certificate", "claim_form", "app_screen"]
    fields: list[MockField]
    legend: list[MockLegend]


class MatrixLegend(Model):
    mark: str
    meaning: str


class Matrix(Model):
    kind: Literal["matrix"] = "matrix"
    rows: list[str]
    cols: list[str]
    marks: list[list[str]]
    legend: list[MatrixLegend] = Field(default_factory=list)


Diagram = Annotated[
    Flowchart | Tree | Steps | Timeline | AnnotatedMock | Matrix,
    Field(discriminator="kind"),
]


class Figure(Model):
    type: Literal["figure"] = "figure"
    id: str
    caption: str | None = None
    alt: str
    facts: list[str]
    diagram: Diagram
    size: Literal["column", "full"] = "column"


class FormulaBox(Model):
    box: str


class FormulaOp(Model):
    op: Literal["＋", "－", "×", "÷", "＝"]


class FractionBody(Model):
    num: str
    den: str


class FormulaFraction(Model):
    fraction: FractionBody


FormulaTerm = FormulaBox | FormulaOp | FormulaFraction


class Formula(Model):
    type: Literal["formula"] = "formula"
    id: str
    alt: str
    layout: Literal["inline_boxes", "fraction"] = "inline_boxes"
    terms: list[FormulaTerm]


class BoxBlock(Model):
    type: Literal["box"] = "box"
    id: str
    style: BoxStyle
    title: str | None = None
    #: 対象ノード id。`margin_note` では必須（docs/schema.md §5.6）。
    anchor: str | None = None
    blocks: list[Block]


class Footnote(Model):
    n: int
    text: RichText


class FootnotesBlock(Model):
    type: Literal["footnotes"] = "footnotes"
    id: str
    notes: list[Footnote]


class QaHeadingBlock(Model):
    type: Literal["qa_heading"] = "qa_heading"
    id: str
    question: str


class PageBreakBlock(Model):
    """ここで改ページする。別表がページ境界で 1〜2 行だけ残るのを避けるために使う。

    描画結果に文字を持たないが、他のブロックと同じく `id` を持たせて
    `layout.elements` で位置を追えるようにする。
    """

    type: Literal["page_break"] = "page_break"
    id: str


Block = Annotated[
    ParagraphBlock
    | ListBlock
    | Table
    | Figure
    | Formula
    | BoxBlock
    | FootnotesBlock
    | QaHeadingBlock
    | PageBreakBlock,
    Field(discriminator="type"),
]


# --- nodes ------------------------------------------------------------------


class Node(Model):
    id: str
    kind: NodeKind
    title: str | None = None
    text: RichText | None = None
    summary: str | None = None
    blocks: list[Block] = Field(default_factory=list)
    children: list[Node] = Field(default_factory=list)
    #: 見出しの右に置く分類ラベル（「契約概要」「注意喚起情報」）。
    #: 重要事項説明書が見出しごとに持つ（docs/reference_structures.md #9・§3.1 E6）。
    #: 各バッジは `<node_id>__badge<i>` の id を持つ独立した要素として描かれ、
    #: `derived.plain_text` にも入る（読み取りの対象にするため）。
    badges: list[str] = Field(default_factory=list)
    #: 別表の呼び名（「別表」「付表」「別紙」）。`kind: "appendix"` のときだけ意味を持つ。
    #: blueprint の `kind_label` を scaffold が写す。**build は blueprint を見ない**ので、
    #: content 側に持たせないと「付表」と宣言しても「別表」と描かれる。
    kind_label: str | None = None
    #: 例外的な番号（「第１の２」など）。lint が理由コメントを要求する。
    number_override: str | None = None
    #: number_override を使う理由。lint L03 が必須にする。
    number_override_reason: str | None = None


class TermDef(Model):
    id: str
    term: str
    definition: RichText
    index_kana: IndexKana
    notes: list[RichText] = Field(default_factory=list)


class FrontMatter(Model):
    cover: Cover
    preface: list[Block] = Field(default_factory=list)
    purpose_index: Table | None = None
    toc: Toc = Field(default_factory=Toc)
    rider_index: Table | None = None
    petname_table: Table | None = None


class BackMatter(Model):
    colophon: list[Block] = Field(default_factory=list)
    contact: list[Block] = Field(default_factory=list)


# --- derived（build が付与）--------------------------------------------------


class LabelInfo(Model):
    label: str  # 「第１条」。番号を持たない要素は ""
    title: str  # 「告知義務」
    heading_text: str  # 「第１条（告知義務）」
    path: list[str]  # 祖先の heading_text
    #: 祖先の id（`path` と同じ並び）。木として復元するのに使う
    path_ids: list[str] = Field(default_factory=list)
    #: 親ノードの id（ルート直下は None）
    parent_id: str | None = None
    #: ノード種別（part/chapter/rider/section/article/paragraph/item/…）
    kind: NodeKind | None = None
    #: **構造内の位置づけ**を番号だけで連ねた文字列（「第2章 第1条 (1)」）。
    #: 読み取り側が出す位置づけと直接比較するための正規形（docs/eval_dataset_plan.md P2）。
    citation: str = ""
    depth: int
    #: この節点の本文の**先頭に走り込みで印字される**ラベル。
    #: `meta.article_heading == "above"`（条見出しを条の上に括弧書きで置く体裁。
    #: docs/reference_structures.md #12）のとき、条の第1項がここに条ラベルを持つ。
    #: 通常の体裁では None で、ラベルは見出し行に出る。
    run_in_label: str | None = None


class RefInfo(Model):
    from_id: str
    to_id: str
    mode: Literal["relative", "short", "full"]
    rendered: str


class TermUse(Model):
    term_id: str
    in_id: str


class FootnoteIndex(Model):
    article_id: str
    n: int
    marker: str
    text: str


class PlainText(Model):
    with_label: str
    without_label: str


class HeaderPath(Model):
    row_headers: list[str] = Field(default_factory=list)
    col_headers: list[str] = Field(default_factory=list)


class TableDerived(Model):
    caption_label: str | None = None  # 「表１」
    header_path: dict[str, HeaderPath] = Field(default_factory=dict)
    #: 列挙表の `{auto_label}` に割り当てた番号（cell_id → 「①」）
    auto_labels: dict[str, str] = Field(default_factory=dict)


class FigureNode(Model):
    """正規化した図のノード（docs/eval_dataset_plan.md P1）。"""

    id: str
    label: str
    #: 種別ごとの意味（start/process/decision/tree/step/tick/span/event/field/legend/row/col/cell ほか）
    role: str


class FigureEdge(Model):
    """正規化した図の辺。`relation` が `flow`/`child`/`next`/`cell` のものだけが経路に数えられる。"""

    from_: str = Field(alias="from")
    to: str
    relation: str
    label: str | None = None


class FigureGraph(Model):
    """6 種の図を 1 つの形に正規化したもの。読み取り側の予測と直接突き合わせる。"""

    nodes: list[FigureNode] = Field(default_factory=list)
    edges: list[FigureEdge] = Field(default_factory=list)


class FigureDerived(Model):
    caption_label: str | None = None
    node_order: list[str] = Field(default_factory=list)
    #: 入次数 0 → 出次数 0 の全経路（ラベルの列）。**6 種すべてで作る**
    paths: list[list[str]] = Field(default_factory=list)
    #: 6 種を共通化した有向グラフ（docs/eval_dataset_plan.md P1）
    graph: FigureGraph = Field(default_factory=FigureGraph)
    #: 図の中に書かれたトークンを含む文字列の解決結果（生文字列 → 解決後）。
    #: SVG は行内マークアップを持てないので、値を差し込む `{ref:}` `{term:}` `{const:}` だけを許す。
    #: 描画側は `resolve_strings()` でこの対応表を当ててから SVG を組む（docs/shared_fixes.md A2）。
    resolved_labels: dict[str, str] = Field(default_factory=dict)


class FormulaDerived(Model):
    """算式の箱に書かれたトークンの解決結果（`FigureDerived.resolved_labels` と同じ扱い）。"""

    resolved_labels: dict[str, str] = Field(default_factory=dict)


class EnumerationItem(Model):
    """列挙の 1 項目（docs/eval_dataset_plan.md P4）。"""

    id: str  # 要素 id（表のセル id / ノード id / リスト項目 id）
    index: int  # 1 始まりの順番
    label: str  # 「①」「(1)」など、紙面に出る記号
    text: str  # 解決後の平文


class Enumeration(Model):
    """「列挙された項目の一つ」を機械可読にするための、列挙のまとまり。

    表の列挙（`{auto_label}` を持つ表）・号のノード・箇条書きの 3 系統をまとめて扱う。
    """

    id: str  # 列挙そのものの id（表 id / 親ノード id / リスト id）
    source: Literal["table", "nodes", "list"]
    owner_id: str  # 導入文の要素 id（「下表のとおり」の項）
    citation: str  # 親の構造位置（「第2章 第3条 (1)」）
    items: list[EnumerationItem] = Field(default_factory=list)


class TocEntry(Model):
    """目次の 1 行。ページ番号は描画時に `target-counter` が入れる（docs/rendering.md §6.5）。"""

    id: str
    depth: int
    label: str
    title: str
    heading_text: str
    summary: str | None = None
    #: ノード種別。目次を木として復元し、見出しの粒度を評価するのに使う
    kind: NodeKind | None = None
    #: 親の見出しの id（目次に出ない親は飛ばさず、直近の祖先ノードの id を入れる）
    parent_id: str | None = None
    #: 祖先の id
    path_ids: list[str] = Field(default_factory=list)
    #: 「第2章 第1条」のような位置づけの正規形
    citation: str = ""


class Derived(Model):
    labels: dict[str, LabelInfo] = Field(default_factory=dict)
    refs: list[RefInfo] = Field(default_factory=list)
    term_uses: list[TermUse] = Field(default_factory=list)
    footnote_index: list[FootnoteIndex] = Field(default_factory=list)
    plain_text: dict[str, PlainText] = Field(default_factory=dict)
    tables: dict[str, TableDerived] = Field(default_factory=dict)
    figures: dict[str, FigureDerived] = Field(default_factory=dict)
    formulas: dict[str, FormulaDerived] = Field(default_factory=dict)
    #: 列挙のまとまり（docs/eval_dataset_plan.md P4）
    enumerations: list[Enumeration] = Field(default_factory=list)
    toc: list[TocEntry] = Field(default_factory=list)


# --- source -----------------------------------------------------------------


class SourceDraft(Model):
    """執筆物。`derived` を持たない（書くと extra=forbid で弾かれる）。"""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    content_id: str
    genre: Genre
    seed: int
    meta: Meta
    front_matter: FrontMatter
    defined_terms: list[TermDef] = Field(default_factory=list)
    body: list[Node] = Field(default_factory=list)
    appendices: list[Node] = Field(default_factory=list)
    back_matter: BackMatter = Field(default_factory=BackMatter)


class Source(SourceDraft):
    """build 後。`derived` が必ず付く。"""

    derived: Derived


# --- layout / qa -------------------------------------------------------------


class Renderer(Model):
    name: Literal["weasyprint"] = "weasyprint"
    version: str
    fonts: list[str] = Field(default_factory=list)


class Furniture(Model):
    text: str
    bbox: BBox


class TextLine(Model):
    bbox: BBox
    text: str
    element_id: str
    region: Literal["body", "margin_note", "header", "footer", "figure", "table"]


class PageLayout(Model):
    number: int
    columns: int
    header: Furniture | None = None
    footer: Furniture | None = None
    reading_order: list[str] = Field(default_factory=list)
    text_lines: list[TextLine] = Field(default_factory=list)


class ElementFragment(Model):
    page: int
    bbox: BBox
    repeated: bool = False


class ElementLayout(Model):
    kind: str
    fragments: list[ElementFragment]
    label: str | None = None
    heading_text: str | None = None


class FigureLayout(Model):
    page: int
    bbox: BBox
    scale: float
    nodes: dict[str, BBox] = Field(default_factory=dict)


class Layout(Model):
    doc_id: str
    content_id: str
    style_id: str
    renderer: Renderer
    page_size_pt: tuple[float, float]
    page_count: int
    dpi_png: Literal[150] = 150
    pages: list[PageLayout] = Field(default_factory=list)
    elements: dict[str, ElementLayout] = Field(default_factory=dict)
    figures: dict[str, FigureLayout] = Field(default_factory=dict)


class AnswerPage(Model):
    """1 ページぶんの期待テキスト（docs/schema.md §5.8）。"""

    number: int
    #: 読み順の本文（欄外注・表を含み、ヘッダ／フッタとページ番号は含まない）
    text: str
    #: ヘッダ／フッタも含めた、そのページに実際に出る全文字列
    text_with_furniture: str
    #: 繰り返し表頭を除いた文字数（テキスト評価で二重計上しないための目安）
    chars: int


class OutlineEntry(Model):
    """見出しツリー 1 行（評価の outline F1 用）。"""

    id: str
    depth: int
    label: str
    title: str
    heading_text: str
    page: int
    #: ノード種別（章か条か項か）。読み取りの粒度を評価するのに要る
    kind: NodeKind | None = None
    #: 親の id。木として復元できるようにする（id の命名規則に頼らない）
    parent_id: str | None = None
    #: 祖先の id
    path_ids: list[str] = Field(default_factory=list)
    #: 「第2章 第1条」のような位置づけの正規形
    citation: str = ""


class Answer(Model):
    """source ＋ layout ＋ 派生（ページ別テキスト・アウトライン）。

    **`answer.json` には `source` と `layout` を書かない**（同じディレクトリに実体があり、
    内包すると同じ正解が 3 か所に並ぶ。docs/remaining_issues.md R3）。
    読み書きは `yakkan.answer.dump_answer()` / `load_answer()` を使う。
    メモリ上ではこれまでどおり 3 つを 1 つに持つ。
    """

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    doc_id: str
    source: Source
    layout: Layout
    pages: list[AnswerPage] = Field(default_factory=list)
    outline: list[OutlineEntry] = Field(default_factory=list)


class QA(Model):
    id: str
    type: QAType
    question: str
    answer: str | float | list[str]
    answer_type: AnswerType
    evidence: list[str]
    page_hint: list[int] = Field(default_factory=list)
    source: Literal["auto", "authored"]


class QASet(Model):
    doc_id: str
    items: list[QA] = Field(default_factory=list)


# --- 入出力 ------------------------------------------------------------------


ListItem.model_rebuild()
TreeNode.model_rebuild()
BoxBlock.model_rebuild()
Node.model_rebuild()
SourceDraft.model_rebuild()
Source.model_rebuild()


def dump_json(model: BaseModel, path: Path | None = None, *, exclude: set[str] | None = None) -> str:
    """仕様どおりの体裁（UTF-8・ensure_ascii=False・indent 2・定義順）で書き出す。

    `exclude` を渡すとそのトップレベル項目を落とす（`answer.json` から
    `source` / `layout` を外すのに使う。docs/remaining_issues.md R3）。
    """
    text = json.dumps(
        model.model_dump(mode="json", by_alias=True, exclude_none=False, exclude=exclude),
        ensure_ascii=False,
        indent=2,
        sort_keys=False,
    )
    if path is not None:
        path.write_text(text + "\n", encoding="utf-8")
    return text


def json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema 2020-12 を返す。"""
    schema = model.model_json_schema(by_alias=True, mode="serialization")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema


#: `yakkan schema export` が書き出すモデル。
def _export_row_models() -> dict[str, type[BaseModel]]:
    """評価向けの派生成果物の型（`yakkan/export_models.py`）。循環 import を避けて遅延で引く。"""
    from yakkan.export_models import ElementRow, Passage, Qrel, Query

    return {"element": ElementRow, "passage": Passage, "query": Query, "qrel": Qrel}


EXPORTED_SCHEMAS: dict[str, type[BaseModel]] = {
    "source_draft": SourceDraft,
    "source": Source,
    "layout": Layout,
    "answer": Answer,
    "qa": QASet,
    **_export_row_models(),
}
