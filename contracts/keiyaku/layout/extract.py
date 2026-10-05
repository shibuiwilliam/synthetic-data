"""WeasyPrint の box ツリーから `layout.json` を作る（docs/schema.md §5.7 / docs/rendering.md §6.8）。

**probe 結果（2026-09-21・WeasyPrint 70.0、`scripts/probe_weasy.py`）**

- `document.pages[i]._page_box` は私的 API だが健在。`box.element.get("id")` で HTML の id が取れる。
- 座標は `border_box_x() / border_box_y()`、寸法は `border_width() / border_height()`。
  単位は CSS px、pt へは ×0.75（`PX_TO_PT`）。原点は左上。`border_box_width()` は**存在しない**。
- 段またぎ・改ページで分割された要素は **同じ id の box が複数**現れる ＝ `fragments`。
- `thead` の繰り返しでも同じセル id が出るため、2 回目以降は `repeated: true` にする。
- `LineBox` / `TextBox` から行単位の bbox と文字列が取れる ＝ `text_lines`。
"""

from __future__ import annotations

from dataclasses import dataclass

from keiyaku.models import (
    BBox,
    ElementFragment,
    ElementLayout,
    FigureLayout,
    Furniture,
    Layout,
    PageLayout,
    Renderer,
    Source,
    TextLine,
)
from keiyaku.styles import Style

#: CSS px → PDF pt（WeasyPrint は 96dpi の px、PDF は 72dpi の pt）
PX_TO_PT = 0.75

#: 本文の読み順に含めない領域
FURNITURE_KINDS = frozenset({"header", "footer"})

#: @page のマージンボックス → 領域名。y 座標ではなく **box の種類** で判定する
#: （本文 1 行目が上マージンと同じ y から始まるため、座標では区別できない）
MARGIN_REGION: dict[str, str] = {
    "@top-left": "header",
    "@top-center": "header",
    "@top-right": "header",
    "@bottom-left": "footer",
    "@bottom-center": "footer",
    "@bottom-right": "footer",
}


def _attr(box, name: str) -> str | None:
    element = getattr(box, "element", None)
    if element is None or not hasattr(element, "get"):
        return None
    return element.get(name)


def extract_layout(
    document, *, source: Source, style: Style, doc_id: str, figure_nodes: dict | None = None
) -> Layout:
    """box ツリー → `Layout`。"""
    import weasyprint

    elements: dict[str, ElementLayout] = {}
    seen_ids: set[str] = set()
    pages: dict[int, PageLayout] = {}
    for number in range(1, len(document.pages) + 1):
        pages[number] = PageLayout(number=number, columns=style.columns.count)

    # 祖先の id を引き継ぎながら走査する（TextBox に id は無いため）
    for page_number, page in enumerate(document.pages, start=1):
        _walk(
            page._page_box,
            page_number,
            owner_id="",
            owner_kind="",
            region=None,
            elements=elements,
            seen=seen_ids,
            page_layout=pages[page_number],
            source=source,
        )

    # ヘッダ・フッタを本文から分離し、読み順を確定する
    for page_layout in pages.values():
        _split_furniture(page_layout)
        page_layout.reading_order = _reading_order(page_layout, elements)

    # fragment が自分の text_lines を覆っていないことがある（実例：段またぎの脚注で、
    # id を持つ span の box が右段の 1 行目を含まず、行だけが先に出る）。
    # fragment と text_lines はどちらも正解データなので、食い違ったままにしない。
    # 表題を持つ表は CSS 上 2 つの box を作る（表題を含む table wrapper box と、
    # 罫線が引かれる table box）。どちらも同じ id を持つので fragment が二重になる。
    # 正解としては罫線の内側＝内側の box だけが欲しい（docs/shared_fixes.md B1）。
    _drop_wrapper_fragments(elements)

    _extend_fragments_to_lines(elements, pages)

    fonts = sorted({f.family for f in _used_fonts()})
    return Layout(
        doc_id=doc_id,
        content_id=source.content_id,
        style_id=style.style_id,
        renderer=Renderer(version=weasyprint.__version__, fonts=fonts),
        page_size_pt=(style.page.width_pt, style.page.height_pt),
        page_count=len(document.pages),
        pages=[pages[n] for n in sorted(pages)],
        elements=elements,
        figures=_figure_layouts(elements, figure_nodes or {}),
    )


def _used_fonts():
    from keiyaku.fonts import FONTS

    return [f for f in FONTS if f.exists]


def _extend_fragments_to_lines(elements: dict[str, ElementLayout], pages: dict[int, PageLayout]) -> None:
    """要素の fragment が、同じページの自分の text_lines を覆うように広げる。

    box ツリーの走査では、id を持つ box が自分の行をすべて含まないことがある
    （段またぎで分割された inline の span で観測）。fragment（要素の bbox）と
    text_lines（行の bbox）はどちらも正解データなので、包含関係を保つ。
    """
    for page_layout in pages.values():
        by_element: dict[str, list[tuple[float, float, float, float]]] = {}
        for line in page_layout.text_lines:
            if line.element_id and line.region in ("body", "margin"):
                by_element.setdefault(line.element_id, []).append(line.bbox)
        for element_id, boxes in by_element.items():
            entry = elements.get(element_id)
            if entry is None:
                continue
            fragments = [f for f in entry.fragments if f.page == page_layout.number]
            if not fragments:
                continue
            for bbox in boxes:
                # その行に最も近い fragment を広げる（段が違えば別の fragment になる）
                nearest = min(
                    fragments,
                    key=lambda f: abs((f.bbox[0] + f.bbox[2]) / 2 - (bbox[0] + bbox[2]) / 2),
                )
                if _contains(nearest.bbox, bbox):
                    continue
                nearest.bbox = (
                    min(nearest.bbox[0], bbox[0]),
                    min(nearest.bbox[1], bbox[1]),
                    max(nearest.bbox[2], bbox[2]),
                    max(nearest.bbox[3], bbox[3]),
                )


def _drop_wrapper_fragments(elements: dict[str, ElementLayout]) -> None:
    """同じ要素・同じページで、別の fragment を丸ごと含む fragment を落とす。

    分割された fragment どうしは重ならないので、包含が起きるのは
    「同じ要素に外側の box と内側の box がある」ときだけ。
    """
    for entry in elements.values():
        if len(entry.fragments) < 2:
            continue
        keep = []
        for i, fragment in enumerate(entry.fragments):
            outer = any(
                j != i
                and other.page == fragment.page
                and _contains(fragment.bbox, other.bbox)
                and other.bbox != fragment.bbox
                for j, other in enumerate(entry.fragments)
            )
            if not outer:
                keep.append(fragment)
        entry.fragments[:] = keep


def _contains(outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]) -> bool:
    return (
        outer[0] <= inner[0] + 0.5
        and outer[1] <= inner[1] + 0.5
        and outer[2] >= inner[2] - 0.5
        and outer[3] >= inner[3] - 0.5
    )


#: 読み順・行の帰属先にしない、要素の内訳を表す span
INLINE_PART_KINDS: frozenset[str] = frozenset({"label", "text", "title", "box_title", "toc_link", "toc_page"})


def _walk(
    box,
    page_number: int,
    owner_id: str,
    owner_kind: str,
    region: str | None,
    *,
    elements: dict[str, ElementLayout],
    seen: set[str],
    page_layout: PageLayout,
    source: Source,
    in_line: bool = False,
) -> None:
    box_type = type(box).__name__
    element_id = _attr(box, "id")
    data_kind = _attr(box, "data-kind")
    # 行の帰属先（＝読み順の単位）は**内容の単位**にする。ラベルと本文を分けた内部の span は
    # bbox の正解としては要るが、読み順に出ると「項」が消えて使えなくなる
    # （docs/eval_dataset_plan.md F11）。
    if element_id and data_kind not in INLINE_PART_KINDS:
        owner_id, owner_kind = element_id, data_kind or box_type
    if box_type == "MarginBox":
        region = MARGIN_REGION.get(getattr(box, "at_keyword", ""), region)

    x = box.border_box_x() * PX_TO_PT
    y = box.border_box_y() * PX_TO_PT
    bbox: BBox = (x, y, x + box.border_width() * PX_TO_PT, y + box.border_height() * PX_TO_PT)

    # box 種別で絞らない。display:grid は GridContainerBox、表は TableBox… と種類が多く、
    # 白リストにすると静かに取りこぼす（実際 .para の grid 化で 11 ノードが欠けた）。
    # 同じ (id, page, x, y) は 1 つにまとめるので重複は出ない。
    if element_id and box_type not in ("TextBox", "LineBox"):
        repeated = element_id in seen and _attr(box, "data-role") == "header"
        entry = elements.get(element_id)
        if entry is None:
            entry = ElementLayout(
                kind=data_kind or box_type,
                fragments=[],
                label=source.derived.labels[element_id].label
                if element_id in source.derived.labels
                else None,
                heading_text=(
                    source.derived.labels[element_id].heading_text
                    if element_id in source.derived.labels
                    else None
                ),
            )
            elements[element_id] = entry
        if not any(
            f.page == page_number and abs(f.bbox[0] - x) < 0.01 and abs(f.bbox[1] - y) < 0.01
            for f in entry.fragments
        ):
            entry.fragments.append(ElementFragment(page=page_number, bbox=bbox, repeated=repeated))
        seen.add(element_id)

    # 行単位で 1 本の TextLine にまとめる（TextBox は span ごとに分かれるため細かすぎる）。
    # **入れ子の LineBox からは出さない。** `display: inline-block`（記名押印欄の「印」の丸枠）は
    # 行の中にさらに LineBox を作るので、そのまま出すと同じ文字が 2 行ぶん載り、
    # PDF のテキスト層と食い違って verify V03 が落ちる（2026-09-26 に実際に踏んだ）。
    if box_type == "LineBox" and not in_line:
        texts = list(_iter_text_boxes(box))
        if texts:
            page_layout.text_lines.append(
                TextLine(
                    bbox=_union([tb[1] for tb in texts]),
                    text="".join(tb[0] for tb in texts),
                    element_id=owner_id,
                    region=region or _content_region(owner_kind),
                )
            )

    for child in getattr(box, "children", []):
        _walk(
            child,
            page_number,
            owner_id,
            owner_kind,
            region,
            elements=elements,
            seen=seen,
            page_layout=page_layout,
            source=source,
            in_line=in_line or box_type == "LineBox",
        )


def _iter_text_boxes(box):
    """LineBox 配下の TextBox を (テキスト, bbox) で返す。"""
    for child in getattr(box, "children", []):
        if type(child).__name__ == "TextBox" and child.text:
            x = child.border_box_x() * PX_TO_PT
            y = child.border_box_y() * PX_TO_PT
            yield (
                child.text,
                (x, y, x + child.border_width() * PX_TO_PT, y + child.border_height() * PX_TO_PT),
            )
        else:
            yield from _iter_text_boxes(child)


def _content_region(owner_kind: str) -> str:
    """本文領域の中での細かい区分（往復比較で除外する領域を分けるため）。"""
    if owner_kind in ("figure", "figure_wrap"):
        return "figure"
    if owner_kind in ("table", "cell", "table_wrap", "table_note", "caption"):
        return "table"
    if owner_kind == "box":
        return "margin_note"
    # 逐条解説の枠。**本文と区別するが正解テキストには含める**（docs/schema.md §11.3）
    if owner_kind in ("commentary", "commentary_title"):
        return "commentary"
    return "body"


def _split_furniture(page_layout: PageLayout) -> None:
    """ヘッダ・フッタを `header` / `footer` に移し、本文の読み順を確定する。"""
    header_lines = [ln for ln in page_layout.text_lines if ln.region == "header"]
    footer_lines = [ln for ln in page_layout.text_lines if ln.region == "footer"]
    if header_lines:
        page_layout.header = Furniture(
            text="".join(ln.text for ln in sorted(header_lines, key=lambda ln: ln.bbox[0])),
            bbox=_union([ln.bbox for ln in header_lines]),
        )
    if footer_lines:
        page_layout.footer = Furniture(
            text=" ".join(ln.text for ln in sorted(footer_lines, key=lambda ln: ln.bbox[0])),
            bbox=_union([ln.bbox for ln in footer_lines]),
        )


def _union(bboxes: list[BBox]) -> BBox:
    return (
        min(b[0] for b in bboxes),
        min(b[1] for b in bboxes),
        max(b[2] for b in bboxes),
        max(b[3] for b in bboxes),
    )


def _reading_order(page_layout: PageLayout, elements: dict[str, ElementLayout]) -> list[str]:
    """このページに現れる要素 id を読み順に並べる（本文 → 欄外注。ヘッダ/フッタは含めない）。

    text_lines は box ツリーの走査順（＝文書順）で積んであるので、その順に重複を除くだけでよい。
    欄外注（margin_note）は本文をすべて出してから最後に付ける（docs/schema.md §5.7）。
    """
    body: list[str] = []
    notes: list[str] = []
    for line in page_layout.text_lines:
        if line.region in FURNITURE_KINDS or not line.element_id:
            continue
        bucket = notes if line.region == "margin_note" else body
        if line.element_id not in bucket:
            bucket.append(line.element_id)
    seen: set[str] = set()
    ordered: list[str] = []
    for element_id in body + notes:
        if element_id not in seen and element_id in elements:
            seen.add(element_id)
            ordered.append(element_id)
    return ordered


# --- 旧 P0 の最小 API（smoke と fallback_align が使う）-------------------------


@dataclass(frozen=True)
class Fragment:
    """1 ページ上に現れた要素の 1 断片。座標は pt・原点左上。"""

    element_id: str
    box_type: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def iter_fragments(document, *, box_types: tuple[str, ...] = ()) -> list[Fragment]:
    """id を持つ box の断片を文書順で返す（P0 smoke 用の簡易版）。"""
    fragments: list[Fragment] = []

    def walk(box, page_number: int) -> None:
        element_id = _attr(box, "id")
        kind = type(box).__name__
        if element_id and (not box_types or kind in box_types):
            x = box.border_box_x() * PX_TO_PT
            y = box.border_box_y() * PX_TO_PT
            fragments.append(
                Fragment(
                    element_id=element_id,
                    box_type=kind,
                    page=page_number,
                    x0=x,
                    y0=y,
                    x1=x + box.border_width() * PX_TO_PT,
                    y1=y + box.border_height() * PX_TO_PT,
                )
            )
        for child in getattr(box, "children", []):
            walk(child, page_number)

    for page_number, page in enumerate(document.pages, start=1):
        walk(page._page_box, page_number)
    return fragments


def span_bands(
    fragments: list[Fragment], *, page: int, content_width: float, ratio: float = 0.9
) -> list[tuple[float, float]]:
    """段またぎ要素（本文幅をほぼ占める要素）の y 範囲。段組の読み順判定に使う。"""
    bands: list[tuple[float, float]] = []
    for f in fragments:
        if f.page != page or f.box_type != "BlockBox":
            continue
        if f.width >= content_width * ratio:
            bands.append((f.y0, f.y1))
    return _merge_bands(bands)


def _merge_bands(bands: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(bands):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _figure_layouts(elements: dict[str, ElementLayout], figure_nodes: dict) -> dict[str, FigureLayout]:
    """SVG の viewBox 内座標を、描画後のページ座標（pt）へ変換する（docs/rendering.md §6.8-3）。

    `<svg>` 要素の実寸（pt）と viewBox の幅から倍率を求め、ノードの bbox に掛ける。
    列幅に収まらず CSS で縮小された場合も、この倍率で正しく追従する。
    """
    out: dict[str, FigureLayout] = {}
    for figure_id, result in figure_nodes.items():
        svg_element = elements.get(f"{figure_id}__svg")
        if svg_element is None or not svg_element.fragments or not result.width:
            continue
        fragment = svg_element.fragments[0]
        x0, y0, x1, _y1 = fragment.bbox
        scale = (x1 - x0) / result.width
        out[figure_id] = FigureLayout(
            page=fragment.page,
            bbox=fragment.bbox,
            scale=scale,
            nodes={
                node_id: (
                    x0 + bx0 * scale,
                    y0 + by0 * scale,
                    x0 + bx1 * scale,
                    y0 + by1 * scale,
                )
                for node_id, (bx0, by0, bx1, by1) in result.nodes.items()
            },
        )
    return out
