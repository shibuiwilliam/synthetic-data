"""評価向けの派生成果物の型（`elements.jsonl` と検索評価セット）。

`source` / `layout` / `answer` / `qa` と同じように、**形を宣言してから書き出す**
（docs/remaining_issues.md S9）。素の dict で組み立てていたころは

- CLAUDE.md §13 の「pydantic モデル外で dict を裸で回さない」に反していて、
- 利用者（採点スクリプト・検索エンジンへの投入）が形を検証できず、
- フィールドを足してもどこにも宣言が残らなかった。

`yakkan schema export` が `schema/element.schema.json` などを書き出す。

**行の形は変えない。** スカラのフィールドは値が `null` でも必ず出す（利用者が
`row["parent_id"]` と書けるように）。出し分けるのは `table` / `figure` /
`figure_node` / `enumeration` の入れ子だけで、これは dict で組んでいたころから
「当てはまるときだけ足す」形だった。
"""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

#: 見出し・要素の種別。`yakkan.models.NodeKind` と同じ語彙
#: （import すると循環するので、ここで宣言して `tests` で一致を固定する）。
NodeKindName = Literal[
    "part",
    "chapter",
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


class ExportRow(BaseModel):
    """JSONL の 1 行になるモデルの共通の土台。"""

    model_config = ConfigDict(extra="forbid")

    def jsonl_row(self) -> dict[str, object]:
        """JSONL の 1 行にする。既定はすべてのフィールドを出す。"""
        return self.model_dump(mode="json")


class ElementTable(ExportRow):
    """要素が表のセルであるときの位置と意味座標。"""

    table_id: str
    caption_label: str | None = None
    row: int
    col: int
    row_headers: list[str] = Field(default_factory=list)
    col_headers: list[str] = Field(default_factory=list)


class ElementFigure(ExportRow):
    """要素が図そのものであるときの規模。"""

    caption_label: str | None = None
    node_count: int
    edge_count: int
    paths: list[list[str]] = Field(default_factory=list)


class ElementFigureNode(ExportRow):
    """要素が図の中のノードであるときの出どころ。"""

    figure_id: str
    node_id: str
    role: str | None = None


class ElementEnumeration(ExportRow):
    """要素が列挙の項目であるときの、親と何番目か。"""

    enum_id: str
    enum_source: str
    enum_owner_id: str
    index: int
    label: str | None = None


class ElementRow(ExportRow):
    """`elements.jsonl` の 1 行。**評価スクリプトが最初に読む平らな索引**。"""

    doc_id: str
    content_id: str
    style_id: str
    genre: str
    element_id: str
    #: layout での種別。描画されなかった要素は `unrendered`、図のノードは `figure_node`
    kind: str
    #: body / table / margin_note / header / footer / figure
    region: str
    text: str
    text_with_label: str
    label: str | None = None
    heading_text: str | None = None
    #: `NodeKind`（paragraph / item / article …）。本文ノードでなければ null
    node_kind: str | None = None
    #: 「第2章 第1条 (1)」。**構造内の位置づけの正解**
    citation: str = ""
    parent_id: str | None = None
    path_ids: list[str] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    #: pt・原点左上。段組では 1 要素が複数の fragment に割れる
    bboxes: list[list[float]] = Field(default_factory=list)
    bboxes_norm: list[list[float]] = Field(default_factory=list)
    #: 表頭の再掲など、同じ文字列が複数回出るもの
    repeated: bool = False
    table: ElementTable | None = None
    figure: ElementFigure | None = None
    figure_node: ElementFigureNode | None = None
    enumeration: ElementEnumeration | None = None

    #: 当てはまるときだけ行に出す入れ子。スカラは null のままでも出す
    OPTIONAL_CONTAINERS: ClassVar[tuple[str, ...]] = ("table", "figure", "figure_node", "enumeration")

    def jsonl_row(self) -> dict[str, object]:
        row = self.model_dump(mode="json")
        for name in self.OPTIONAL_CONTAINERS:
            if row.get(name) is None:
                row.pop(name, None)
        return row


class Passage(ExportRow):
    """`passages.jsonl` の 1 行。**検索エンジンに登録する単位**。"""

    #: `"<doc_id>::<element_id>"`。qrels の突合キー
    passage_id: str
    doc_id: str
    content_id: str
    genre: str
    product_name: str
    issuer: str
    #: article / paragraph / table / figure / definition / other
    kind: str
    title: str
    citation: str
    text: str
    element_ids: list[str] = Field(default_factory=list)
    pages: list[int] = Field(default_factory=list)
    #: qrels の部分適合を導くための関係。**`derived` に実在するものだけ**
    terms_used: list[str] = Field(default_factory=list)
    refs_to: list[str] = Field(default_factory=list)


class Query(ExportRow):
    """`queries.jsonl` の 1 行。"""

    query_id: str
    #: term / heading / scoped / qa
    kind: str
    query: str
    note: str = ""
    n_relevant: int
    n_exact: int
    n_related: int
    #: 打ち切る前の grade 1 の数
    n_related_total: int
    #: grade 1 を `MAX_RELATED` で打ち切ったか。**打ち切った分は qrels に出ない**
    related_truncated: bool = False


class Qrel(ExportRow):
    """`qrels.jsonl` の 1 行。grade は 2＝答えがそこにある、1＝関連する。"""

    query_id: str
    passage_id: str
    grade: int


# --- 読み取り側が出す形（docs/evaluation.md §1・§2） --------------------------


class PredictionPage(ExportRow):
    """ページ本文。ヘッダ・フッタ・図中の文字は含めない。"""

    number: int
    text: str = ""


class PredictionOutline(ExportRow):
    """見出し 1 件。`kind` の語彙は docs/evaluation.md §3。迷ったら null。"""

    label: str = ""
    title: str = ""
    heading_text: str = ""
    kind: NodeKindName | None = None
    page: int | None = None
    citation: str = ""


class PredictionElement(ExportRow):
    """本文の要素。**読み順に**並べる（読み順の τ はこの並びで測る）。"""

    text: str
    page: int | None = None
    kind: NodeKindName | None = None
    citation: str = ""
    #: pt・原点左上。出すと IoU が採点される
    bbox: list[float] | None = None


class PredictionCell(ExportRow):
    """表のセルの意味座標。`grid`（見た目）とは**別に**採点する。"""

    row_headers: list[str] = Field(default_factory=list)
    col_headers: list[str] = Field(default_factory=list)
    value: str


class PredictionTable(ExportRow):
    caption_label: str | None = None
    #: 結合を展開した矩形。被結合位置には結合元の値を入れる
    grid: list[list[str]] = Field(default_factory=list)
    cells: list[PredictionCell] = Field(default_factory=list)


class PredictionNode(ExportRow):
    #: 予測の中で一意ならなんでもよい（edges から参照するためだけに使う）
    id: str
    label: str = ""
    role: str | None = None


class PredictionEdge(ExportRow):
    from_: str = Field(alias="from")
    to: str
    relation: str | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PredictionFigure(ExportRow):
    caption_label: str | None = None
    nodes: list[PredictionNode] = Field(default_factory=list)
    edges: list[PredictionEdge] = Field(default_factory=list)
    paths: list[list[str]] = Field(default_factory=list)


class PredictionEnumeration(ExportRow):
    #: 親（導入文）の位置づけ
    citation: str = ""
    #: 行頭の番号は**付けても付けなくてもよい**（docs/remaining_issues.md T8）
    items: list[str] = Field(default_factory=list)


class PredictionQA(ExportRow):
    #: `qa.json` の id をそのまま使う
    id: str
    answer: object = None


class Prediction(ExportRow):
    """読み取りの予測 JSON（docs/evaluation.md §1）。

    **すべてのキーが任意。** 出さない観点はその指標が 0 になるだけで、他は採点される。
    突合は中身で行う（予測に我々の内部 id は無い前提）。
    """

    doc_id: str | None = None
    pages: list[PredictionPage] = Field(default_factory=list)
    outline: list[PredictionOutline] = Field(default_factory=list)
    elements: list[PredictionElement] = Field(default_factory=list)
    tables: list[PredictionTable] = Field(default_factory=list)
    figures: list[PredictionFigure] = Field(default_factory=list)
    enumerations: list[PredictionEnumeration] = Field(default_factory=list)
    qa: list[PredictionQA] = Field(default_factory=list)


class SearchRunEntry(ExportRow):
    query_id: str
    #: 順位つきの passage_id
    passages: list[str] = Field(default_factory=list)


class SearchRun(ExportRow):
    """検索結果（docs/evaluation.md §2）。"""

    runs: list[SearchRunEntry] = Field(default_factory=list)
