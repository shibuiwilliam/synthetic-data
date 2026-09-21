"""`SourceDraft` → `Source`：番号・参照・平文・表のヘッダ経路・図の経路を導出する。

    uv run yakkan build content/<content_id>     # → content/<content_id>/source.json

執筆者は番号を書かない（CLAUDE.md §2-2）。ここが唯一の導出点で、描画側は `derived` を読むだけにする。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from yakkan.compose import load_draft
from yakkan.lint.walk import iter_blocks, iter_nodes
from yakkan.models import (
    BoxBlock,
    Cell,
    Derived,
    Figure,
    FigureDerived,
    FootnoteIndex,
    FootnotesBlock,
    HeaderPath,
    ListBlock,
    ListItem,
    ParagraphBlock,
    PlainText,
    RefInfo,
    Source,
    SourceDraft,
    Table,
    TableDerived,
    TermUse,
    TocEntry,
    dump_json,
)
from yakkan.numbering import (
    DocumentIndex,
    NumberingContext,
    circled,
    footnote_marker,
    resolve_ref,
)
from yakkan.richtext import PlainContext, parse, to_plain, with_label


class BuildError(ValueError):
    """derived を組み立てられない（参照切れなど）。lint を先に通すこと。"""


@dataclass
class BuildContext:
    """1 文書ぶんの導出に使う道具一式。"""

    draft: SourceDraft
    index: DocumentIndex
    numbering: NumberingContext
    #: 表・図のキャプション番号（「表１」「図２」）
    caption_labels: dict[str, str] = field(default_factory=dict)
    terms: dict[str, str] = field(default_factory=dict)

    def resolve_ref(self, target: str, mode: str, from_id: str) -> str:
        if target in self.index:
            return resolve_ref(self.index, from_id, target, mode)  # type: ignore[arg-type]
        if target in self.caption_labels:
            return self.caption_labels[target]
        raise BuildError(f"{from_id} からの {{ref:{target}}} を解決できない")

    def plain_context(self, from_id: str, auto_label: str = "") -> PlainContext:
        return PlainContext(
            resolve_ref=lambda target, mode: self.resolve_ref(target, mode, from_id),
            resolve_term=lambda term_id: self.terms.get(term_id, term_id),
            resolve_const=lambda key: self.draft.meta.constants.get(key, ""),
            footnote_marker=lambda n: footnote_marker(self.numbering, n),
            auto_label=auto_label,
        )


# --- キャプション採番 ---------------------------------------------------------


def assign_caption_labels(draft: SourceDraft, ctx: NumberingContext) -> dict[str, str]:
    """表・図に「表１」「図１」を文書順で振る（docs/schema.md §5.4 の「番号は build が付与」）。"""
    from yakkan.numbering import to_digits

    labels: dict[str, str] = {}
    table_n = figure_n = 0
    for block, _owner, _article in iter_blocks(draft):
        if isinstance(block, Table):
            table_n += 1
            labels[block.id] = f"表{to_digits(table_n, ctx.digit_style)}"
        elif isinstance(block, Figure):
            figure_n += 1
            labels[block.id] = f"図{to_digits(figure_n, ctx.digit_style)}"
    return labels


# --- 表のヘッダ経路 -----------------------------------------------------------


def expand_grid(table: Table) -> list[list[Cell | None]]:
    """結合を解いて (行, 列) → 実体セル の格子にする。被結合位置には結合元のセルを置く。"""
    by_id = {c.id: c for row in table.grid for c in row if isinstance(c, Cell)}
    out: list[list[Cell | None]] = []
    for row in table.grid:
        expanded: list[Cell | None] = []
        for cell in row:
            expanded.append(cell if isinstance(cell, Cell) else by_id.get(cell.merged_into))
        out.append(expanded)
    return out


def header_paths(table: Table, ctx: BuildContext) -> dict[str, HeaderPath]:
    """body セルごとに「どの行見出し × どの列見出しに属するか」を求める（docs/schema.md §5.4）。"""
    grid = expand_grid(table)
    header_rows = table.layout.header_rows
    header_cols = table.layout.header_cols
    out: dict[str, HeaderPath] = {}

    def cell_plain(cell: Cell) -> str:
        return to_plain(parse(cell.text), ctx.plain_context(cell.id)).strip()

    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell is None or r < header_rows or c < header_cols:
                continue
            if cell.role == "header":
                continue
            col_headers: list[str] = []
            for hr in range(header_rows):
                head = grid[hr][c] if c < len(grid[hr]) else None
                if head is not None and (not col_headers or col_headers[-1] != cell_plain(head)):
                    col_headers.append(cell_plain(head))
            row_headers: list[str] = []
            for hc in range(header_cols):
                head = row[hc] if hc < len(row) else None
                if head is not None and (not row_headers or row_headers[-1] != cell_plain(head)):
                    row_headers.append(cell_plain(head))
            # 同じセルが複数位置に現れる（結合）場合は最初の 1 回だけ記録する
            out.setdefault(cell.id, HeaderPath(row_headers=row_headers, col_headers=col_headers))
    return out


#: `{auto_label}` で自動採番する表の意味種別。
#: 免責事由の列挙（exclusions）も実物では ①②… が振られるので対象に含める。
AUTO_LABEL_TYPES = frozenset({"enumeration", "exclusions"})


def enumeration_labels(table: Table, ctx: BuildContext) -> dict[str, str]:
    """列挙表（`{auto_label}`）の自動採番。第 1 列の stub に ①②… を振る。"""
    labels: dict[str, str] = {}
    if table.semantic_type not in AUTO_LABEL_TYPES:
        return labels
    n = 0
    for row in table.grid:
        for cell in row:
            if isinstance(cell, Cell) and "{auto_label}" in cell.text:
                n += 1
                labels[cell.id] = circled(n, ctx.numbering.digit_style, ctx.numbering.warnings, cell.id)
    return labels


# --- 図の経路 -----------------------------------------------------------------


def figure_paths(figure: Figure) -> tuple[list[str], list[list[str]]]:
    """(ノードの文書順, start→end の経路のラベル列) を返す。"""
    diagram = figure.diagram
    if diagram.kind != "flowchart":
        return _diagram_node_order(figure), []
    order = [n.id for n in diagram.nodes]
    labels = {n.id: n.label for n in diagram.nodes}
    edges: dict[str, list[str]] = {}
    for edge in diagram.edges:
        edges.setdefault(edge.from_, []).append(edge.to)
    starts = [n.id for n in diagram.nodes if n.shape == "start"] or order[:1]
    ends = {n.id for n in diagram.nodes if n.shape == "end"}
    paths: list[list[str]] = []

    def walk(current: str, seen: tuple[str, ...]) -> None:
        if current in ends or current not in edges:
            paths.append([labels[n] for n in (*seen, current)])
            return
        for nxt in edges[current]:
            if nxt in seen:  # 循環は打ち切る
                continue
            walk(nxt, (*seen, current))

    for start in starts:
        walk(start, ())
    return order, paths


def _diagram_node_order(figure: Figure) -> list[str]:
    diagram = figure.diagram
    match diagram.kind:
        case "tree":
            order: list[str] = []
            stack = [diagram.root]
            while stack:
                node = stack.pop(0)
                order.append(node.id)
                stack = list(node.children) + stack
            return order
        case "steps":
            return [s.id for s in diagram.steps]
        case "timeline":
            return [s.id for s in diagram.spans] + [e.id for e in diagram.events]
        case "annotated_mock":
            return [f.id for f in diagram.fields]
    return []


# --- 目次 ---------------------------------------------------------------------


def build_toc(ctx: BuildContext) -> list[TocEntry]:
    """構造から目次を作る（ページ番号は描画時に `target-counter` が入れる）。"""
    depth_limit = ctx.draft.front_matter.toc.depth
    entries: list[TocEntry] = []
    for node, ancestors in iter_nodes(ctx.draft.body + ctx.draft.appendices):
        if node.kind in ("paragraph", "item", "subitem", "subsubitem"):
            continue
        depth = len(ancestors)
        if depth >= depth_limit:
            continue
        item = ctx.index[node.id]
        entries.append(
            TocEntry(
                id=node.id,
                depth=depth,
                label=item.label,
                title=node.title or "",
                heading_text=item.heading_text,
                summary=node.summary,
            )
        )
    return entries


# --- 平文 ---------------------------------------------------------------------


def _iter_list_items(items: list[ListItem]) -> Iterator[ListItem]:
    for item in items:
        yield item
        yield from _iter_list_items(item.children)


def build_plain_text(ctx: BuildContext) -> tuple[dict[str, PlainText], list[RefInfo], list[TermUse]]:
    """全要素の平文（ラベル有無）と、参照・用語の使用記録。"""
    plain: dict[str, PlainText] = {}
    refs: list[RefInfo] = []
    terms: list[TermUse] = []

    # ノード（見出しと本文）
    for node, _ancestors in iter_nodes(ctx.draft.body + ctx.draft.appendices):
        item = ctx.index[node.id]
        if node.kind in ("paragraph", "item", "subitem", "subsubitem") and node.text:
            pc = ctx.plain_context(node.id)
            body = to_plain(parse(node.text), pc)
            _collect(pc, node.id, refs, terms)
            plain[node.id] = PlainText(with_label=with_label(item.label, body), without_label=body)
        else:
            plain[node.id] = PlainText(
                with_label=item.heading_text,
                without_label=node.title or "",
            )

    # ブロック
    enum_labels: dict[str, str] = {}
    for block, _owner, _article in iter_blocks(ctx.draft):
        if isinstance(block, Table):
            enum_labels |= enumeration_labels(block, ctx)

    for block, _owner, _article in iter_blocks(ctx.draft):
        match block:
            case ParagraphBlock():
                pc = ctx.plain_context(block.id)
                text = to_plain(parse(block.text), pc)
                _collect(pc, block.id, refs, terms)
                plain[block.id] = PlainText(with_label=text, without_label=text)
            case ListBlock():
                for list_item in _iter_list_items(block.items):
                    pc = ctx.plain_context(list_item.id)
                    text = to_plain(parse(list_item.text), pc)
                    _collect(pc, list_item.id, refs, terms)
                    plain[list_item.id] = PlainText(with_label=text, without_label=text)
            case Table():
                caption = ctx.caption_labels.get(block.id, "")
                if block.caption:
                    plain[f"{block.id}__caption"] = PlainText(
                        with_label=f"{caption}　{block.caption}" if caption else block.caption,
                        without_label=block.caption,
                    )
                for row in block.grid:
                    for cell in row:
                        if not isinstance(cell, Cell):
                            continue
                        auto = enum_labels.get(cell.id, "")
                        pc = ctx.plain_context(cell.id, auto_label=auto)
                        text = to_plain(parse(cell.text), pc)
                        _collect(pc, cell.id, refs, terms)
                        plain[cell.id] = PlainText(with_label=text, without_label=text)
                for i, note in enumerate(block.notes):
                    note_id = f"{block.id}__note{i}"
                    pc = ctx.plain_context(note_id)
                    text = to_plain(parse(note), pc)
                    _collect(pc, note_id, refs, terms)
                    plain[note_id] = PlainText(with_label=text, without_label=text)
            case Figure():
                caption = ctx.caption_labels.get(block.id, "")
                if block.caption:
                    plain[f"{block.id}__caption"] = PlainText(
                        with_label=f"{caption}　{block.caption}" if caption else block.caption,
                        without_label=block.caption,
                    )
            case FootnotesBlock():
                for note in block.notes:
                    note_id = f"{block.id}__n{note.n}"
                    pc = ctx.plain_context(note_id)
                    text = to_plain(parse(note.text), pc)
                    _collect(pc, note_id, refs, terms)
                    marker = footnote_marker(ctx.numbering, note.n)
                    plain[note_id] = PlainText(with_label=f"{marker}　{text}", without_label=text)
            case BoxBlock():
                if block.title:
                    plain[f"{block.id}__title"] = PlainText(with_label=block.title, without_label=block.title)
    return plain, refs, terms


def _collect(pc: PlainContext, owner_id: str, refs: list[RefInfo], terms: list[TermUse]) -> None:
    for target, mode, rendered in pc.used_refs:
        refs.append(RefInfo(from_id=owner_id, to_id=target, mode=mode, rendered=rendered))
    for term_id in pc.used_terms:
        terms.append(TermUse(term_id=term_id, in_id=owner_id))


def build_footnote_index(ctx: BuildContext) -> list[FootnoteIndex]:
    out: list[FootnoteIndex] = []
    for block, owner, article in iter_blocks(ctx.draft):
        if not isinstance(block, FootnotesBlock):
            continue
        for note in block.notes:
            note_id = f"{block.id}__n{note.n}"
            text = to_plain(parse(note.text), ctx.plain_context(note_id))
            out.append(
                FootnoteIndex(
                    article_id=article or owner,
                    n=note.n,
                    marker=footnote_marker(ctx.numbering, note.n),
                    text=text,
                )
            )
    return out


# --- 入口 ---------------------------------------------------------------------


def build(draft: SourceDraft) -> Source:
    """執筆物から `derived` 付きの `Source` を作る。"""
    numbering = NumberingContext(draft.meta.numbering_scheme, draft.meta.digit_style)
    index = DocumentIndex(numbering, draft.body, draft.appendices)
    ctx = BuildContext(
        draft=draft,
        index=index,
        numbering=numbering,
        caption_labels=assign_caption_labels(draft, numbering),
        terms={t.id: t.term for t in draft.defined_terms},
    )

    plain, refs, terms = build_plain_text(ctx)

    tables: dict[str, TableDerived] = {}
    figures: dict[str, FigureDerived] = {}
    for block, _owner, _article in iter_blocks(draft):
        if isinstance(block, Table):
            tables[block.id] = TableDerived(
                caption_label=ctx.caption_labels.get(block.id),
                header_path=header_paths(block, ctx),
                auto_labels=enumeration_labels(block, ctx),
            )
        elif isinstance(block, Figure):
            order, paths = figure_paths(block)
            figures[block.id] = FigureDerived(
                caption_label=ctx.caption_labels.get(block.id),
                node_order=order,
                paths=paths,
            )

    derived = Derived(
        labels=index.labels(),
        refs=refs,
        term_uses=terms,
        footnote_index=build_footnote_index(ctx),
        plain_text=plain,
        tables=tables,
        figures=figures,
        toc=build_toc(ctx),
    )
    return Source(**draft.model_dump(), derived=derived)


def build_content(content_dir: Path) -> Source:
    """content ディレクトリを読んで `source.json` を書き出す。"""
    source = build(load_draft(content_dir))
    dump_json(source, content_dir / "source.json")
    return source


def unresolved_characters(source: Source) -> list[str]:
    """平文に `{` `}` が残っていないか（トークンの取りこぼし検出）。"""
    return [
        element_id
        for element_id, text in source.derived.plain_text.items()
        if "{" in text.without_label or "}" in text.without_label
    ]
