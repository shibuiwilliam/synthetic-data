"""`SourceDraft` → `Source`：番号・参照・平文・表のヘッダ経路・図の経路を導出する。

    uv run keiyaku build content/<content_id>     # → content/<content_id>/source.json

執筆者は番号を書かない（CLAUDE.md §2-2）。ここが唯一の導出点で、描画側は `derived` を読むだけにする。
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from keiyaku.compose import load_draft
from keiyaku.figure_graph import build_graph, graph_paths
from keiyaku.lint.walk import document_nodes, iter_blocks, iter_nodes
from keiyaku.models import (
    BoxBlock,
    Cell,
    CommentaryBlock,
    Derived,
    Enumeration,
    EnumerationItem,
    Figure,
    FigureDerived,
    FootnoteIndex,
    FootnotesBlock,
    Formula,
    FormulaDerived,
    HeaderPath,
    ListBlock,
    ListItem,
    Node,
    ParagraphBlock,
    PartyDef,
    PartyUse,
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
from keiyaku.numbering import (
    DocumentIndex,
    NumberingContext,
    footnote_marker,
    resolve_ref,
)
from keiyaku.richtext import (
    Const,
    Party,
    PlainContext,
    Ref,
    Term,
    iter_tokens,
    parse,
    to_plain,
    with_label,
)


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

    @property
    def parties(self) -> dict[str, PartyDef]:
        """key → PartyDef。`meta.parties` の順序が「甲・乙・丙」の順序。"""
        return {p.key: p for p in self.draft.meta.parties}

    def resolve_party(self, key: str, mode: str) -> str:
        """`{party:key|mode}` を紙面の文字列にする（docs/schema.md §4）。

        `full` は「株式会社◯◯（以下「甲」という。）」の導入形。前文・当事者表示でのみ使う
        （2 回以上使うと lint L19 が warn を出す）。
        """
        party = self.parties.get(key)
        if party is None:
            known = "、".join(self.parties) or "（meta.parties が空）"
            raise BuildError(f"{{party:{key}}} が meta.parties に無い（あるのは {known}）")
        match mode:
            case "alias":
                return party.alias
            case "name":
                return party.name
            case "role":
                if not party.role_label:
                    raise BuildError(f"{{party:{key}|role}} だが role_label が宣言されていない")
                return party.role_label
            case "full":
                return f"{party.name}（以下「{party.alias}」という。）"
        raise BuildError(f"{{party:{key}}} の修飾子が不正: {mode}")

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
            resolve_party=lambda key, mode: self.resolve_party(key, mode),
            footnote_marker=lambda n: footnote_marker(self.numbering, n),
            auto_label=auto_label,
        )


# --- キャプション採番 ---------------------------------------------------------


def _chapter_of(draft: SourceDraft) -> dict[str, int]:
    """ノード id → その要素が属する章の 1 始まり番号（章の外は 0）。

    `meta.caption_numbering == "chapter"` のときに「表1-1」を作るために使う。
    """
    out: dict[str, int] = {}

    def walk(nodes: list[Node], chapter: int) -> None:
        index = 0
        for node in nodes:
            here = chapter
            if node.kind == "chapter":
                index += 1
                here = index if chapter == 0 else chapter
            out[node.id] = here
            walk(node.children or [], here)
            for block in node.blocks:
                out.setdefault(block.id, here)

    walk(draft.body, 0)
    return out


def assign_caption_labels(draft: SourceDraft, ctx: NumberingContext) -> dict[str, str]:
    """表・図に「表１」「図１」を文書順で振る（docs/schema.md §5.4 の「番号は build が付与」）。

    `meta.caption_numbering == "chapter"` のときは章番号を含める（「表1-1」「表3-2」）。
    実物の団体保険の加入のしおり（docs/reference_structures.md #14）がこの形。
    この方式では**章に属さない表・図（前付け・別表の中）には番号を振らない**。
    実物がそうであるうえ、「表1-1」と「表1」が同居すると読み取りの正解として
    紛らわしいためである（docs/remaining_issues.md S2）。
    """
    from keiyaku.numbering import to_digits

    # **キャプションのある表・図だけに番号を振る。**
    # 文と一体の列挙表（「次に掲げる事由」の受けなど）はキャプションを持たず、
    # 実物の約款でも「表N」を振らない。これらを数えていたため、読者に見える番号が
    # 「表１→表３」のように飛んでいた（P5 の執筆担当 4 人が独立に報告）。
    by_chapter = draft.meta.caption_numbering == "chapter"
    chapters = _chapter_of(draft) if by_chapter else {}
    labels: dict[str, str] = {}
    counters: dict[tuple[str, int], int] = {}
    digits = ctx.digit_style

    def number(kind: str, owner_id: str) -> str | None:
        chapter = chapters.get(owner_id, 0) if by_chapter else 0
        if by_chapter and not chapter:
            return None
        key = (kind, chapter)
        counters[key] = counters.get(key, 0) + 1
        n = to_digits(counters[key], digits)
        if by_chapter and chapter:
            return f"{kind}{to_digits(chapter, digits)}-{n}"
        return f"{kind}{n}"

    for block, owner, _article in iter_blocks(draft):
        if isinstance(block, Table | Figure):
            if not (block.caption or "").strip():
                continue
            label = number("表" if isinstance(block, Table) else "図", owner)
            if label is not None:
                labels[block.id] = label
    return labels


# --- 図・算式のトークン解決 ----------------------------------------------------

#: 図と算式で使ってよいトークン。SVG も算式の箱も行内マークアップを持てないので、
#: 値を差し込むものだけを許す（太字・ルビ・改行・脚注は L06 が弾く）。
#: `{party:}` も値を差し込むだけなので入れる。**外していたため図のノード名に
#: `{party:client}` と書くと生のまま SVG に出た**（lint も verify も拾えなかった）。
#: 当事者の呼称は直書きできない（L19）ので、図で当事者に触れるにはこれが要る。
FLAT_TOKENS = (Ref, Term, Const, Party)


def iter_model_strings(value: object) -> Iterator[str]:
    """pydantic モデル・リスト・辞書を歩いて、すべての文字列を出す。"""
    if isinstance(value, str):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from iter_model_strings(getattr(value, name))
    elif isinstance(value, list | tuple):
        for item in value:
            yield from iter_model_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_model_strings(item)


def resolved_labels(value: object, ctx: BuildContext, owner_id: str) -> dict[str, str]:
    """図・算式の中のトークンを含む文字列を「生文字列 → 解決後」の対応表にする。

    描画側はこの対応表を当ててから SVG・算式を組む（docs/shared_fixes.md A2）。
    トークンを含まない文字列は入れない（対応表を小さく保ち、差分を読みやすくする）。
    解決は文字列単位で、同じ生文字列は同じ結果になる（`{ref:}` の起点は図・算式そのもの）。
    """
    out: dict[str, str] = {}
    for raw in iter_model_strings(value):
        if raw in out or "{" not in raw:
            continue
        nodes = parse(raw)
        if not any(isinstance(t, FLAT_TOKENS) for t in iter_tokens(nodes)):
            continue
        out[raw] = to_plain(nodes, ctx.plain_context(owner_id))
    return out


def resolve_strings[M: BaseModel](value: M, labels: dict[str, str]) -> M:
    """`resolved_labels` の対応表を当てたモデルの複製を返す。元のモデルは変えない。"""
    if not labels:
        return value
    return type(value).model_validate(_substitute(value.model_dump(mode="python", by_alias=True), labels))


def _substitute(value: object, labels: dict[str, str]) -> object:
    if isinstance(value, str):
        return labels.get(value, value)
    if isinstance(value, list):
        return [_substitute(v, labels) for v in value]
    if isinstance(value, dict):
        return {k: _substitute(v, labels) for k, v in value.items()}
    return value


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
    """列挙表（`{auto_label}`）の自動採番。

    **記号は番号方式に従う。** 以前は `circled()` を無条件に呼んでいたため、
    定款でも ①②③ になっていた（定款の慣行は `（１）（２）`）。
    ノードの号（`item`）と同じ記号を使うのが筋なので `label_for` 経由にする。
    """
    from keiyaku.numbering import label_for

    labels: dict[str, str] = {}
    if table.semantic_type not in AUTO_LABEL_TYPES:
        return labels
    n = 0
    for row in table.grid:
        for cell in row:
            if isinstance(cell, Cell) and "{auto_label}" in cell.text:
                n += 1
                labels[cell.id] = label_for(ctx.numbering, "item", n, node_id=cell.id, siblings=99)
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


# --- 列挙 ---------------------------------------------------------------------


def build_enumerations(ctx: BuildContext, plain: dict[str, PlainText]) -> list[Enumeration]:
    """「列挙された項目の一つ」を辿れるようにする（docs/eval_dataset_plan.md P4）。

    3 系統をまとめる：
    - **表の列挙**：`{auto_label}` を持つ表。項目は stub セルの隣の本文セル。
    - **号のノード**：`item` / `subitem` / `subsubitem`。親の項ごとにまとめる。
    - **箇条書き**：`ListBlock`。
    """
    out: list[Enumeration] = []

    def text_of(element_id: str) -> str:
        entry = plain.get(element_id)
        return entry.without_label if entry else ""

    # 表の列挙
    for block, owner_id, _article in iter_blocks(ctx.draft):
        if not isinstance(block, Table):
            continue
        auto = enumeration_labels(block, ctx)
        if not auto:
            continue
        items: list[EnumerationItem] = []
        for row in block.grid:
            cells = [c for c in row if isinstance(c, Cell)]
            marker = next((c for c in cells if c.id in auto), None)
            if marker is None:
                continue
            body = next((c for c in cells if c.id != marker.id), marker)
            items.append(
                EnumerationItem(
                    id=body.id,
                    index=len(items) + 1,
                    label=auto[marker.id],
                    text=text_of(body.id),
                )
            )
        if items:
            out.append(
                Enumeration(
                    id=block.id,
                    source="table",
                    owner_id=owner_id,
                    citation=ctx.index.citation(owner_id) if owner_id in ctx.index else "",
                    items=items,
                )
            )

    # 号のノード（親の項ごと）
    for node, _ancestors in iter_nodes(document_nodes(ctx.draft)):
        children = [c for c in node.children if c.kind in ("item", "subitem", "subsubitem")]
        if len(children) < 2:
            continue
        out.append(
            Enumeration(
                id=f"{node.id}__enum",
                source="nodes",
                owner_id=node.id,
                citation=ctx.index.citation(node.id),
                items=[
                    EnumerationItem(
                        id=child.id,
                        index=i + 1,
                        label=ctx.index[child.id].label,
                        text=text_of(child.id),
                    )
                    for i, child in enumerate(children)
                ],
            )
        )

    # 箇条書き
    for block, owner_id, _article in iter_blocks(ctx.draft):
        if not isinstance(block, ListBlock) or len(block.items) < 2:
            continue
        out.append(
            Enumeration(
                id=block.id,
                source="list",
                owner_id=owner_id,
                citation=ctx.index.citation(owner_id) if owner_id in ctx.index else "",
                items=[
                    EnumerationItem(id=item.id, index=i + 1, label="", text=text_of(item.id))
                    for i, item in enumerate(block.items)
                ],
            )
        )
    return out


# --- 目次 ---------------------------------------------------------------------


def build_toc(ctx: BuildContext) -> list[TocEntry]:
    """構造から目次を作る（ページ番号は描画時に `target-counter` が入れる）。"""
    toc_spec = ctx.draft.front_matter.toc
    if toc_spec is None:
        return []  # 目次を持たない文書（契約書の既定）。verify は V-P3 でスキップを明記する
    depth_limit = toc_spec.depth
    entries: list[TocEntry] = []
    for node, ancestors in iter_nodes(document_nodes(ctx.draft)):
        if node.kind in ("paragraph", "item", "subitem", "subsubitem"):
            continue
        depth = len(ancestors)
        if depth >= depth_limit:
            continue
        item = ctx.index[node.id]
        # **ラベルも見出し文言も持たない節点は目次に入れない**（`docs/schema.md` §8・yakkan T7）。
        # 前文・記名押印欄がこれに当たる。入れるとリーダー罫とページ番号だけの空行が出る
        # （2026-09-27：sysdev の目次の先頭に実際に出た）。
        if not item.label and not (node.title or "").strip():
            continue
        entries.append(
            TocEntry(
                id=node.id,
                depth=depth,
                label=item.label,
                title=node.title or "",
                heading_text=item.heading_text,
                summary=node.summary,
                kind=node.kind,
                parent_id=item.parent_id,
                path_ids=list(item.ancestors),
                citation=ctx.index.citation(node.id),
            )
        )
    return entries


# --- 平文 ---------------------------------------------------------------------


def _iter_list_items(items: list[ListItem]) -> Iterator[ListItem]:
    for item in items:
        yield item
        yield from _iter_list_items(item.children)


def build_plain_text(
    ctx: BuildContext,
) -> tuple[dict[str, PlainText], list[RefInfo], list[TermUse], list[PartyUse]]:
    """全要素の平文（ラベル有無）と、参照・用語・当事者の使用記録。"""
    plain: dict[str, PlainText] = {}
    refs: list[RefInfo] = []
    terms: list[TermUse] = []
    parties: list[PartyUse] = []

    # ノード（見出しと本文）
    for node, _ancestors in iter_nodes(document_nodes(ctx.draft)):
        item = ctx.index[node.id]
        if node.kind in ("paragraph", "item", "subitem", "subsubitem") and node.text:
            pc = ctx.plain_context(node.id)
            body = to_plain(parse(node.text), pc)
            _collect(pc, node.id, refs, terms, parties)
            # `article_heading == "above"` の第1項は、条ラベルが本文の先頭に走り込む
            prefix = item.run_in_label or item.label
            plain[node.id] = PlainText(with_label=with_label(prefix, body), without_label=body)
        else:
            plain[node.id] = PlainText(
                with_label=item.heading_text,
                without_label=node.title or "",
            )
        # 見出しのバッジ（「契約概要」など）も読み取りの対象にする
        for i, badge in enumerate(node.badges):
            plain[f"{node.id}__badge{i}"] = PlainText(with_label=badge, without_label=badge)

    # 定義語（`defined_terms[].definition` は RichText だが、これまで平文化していなかった。
    # 用語そのものが検索・抽出の対象になるので正解に含める）
    for term in ctx.draft.defined_terms:
        pc = ctx.plain_context(f"term_{term.id}")
        text = to_plain(parse(term.definition), pc)
        _collect(pc, f"term_{term.id}", refs, terms, parties)
        plain[f"term_{term.id}"] = PlainText(with_label=f"{term.term}　{text}", without_label=text)

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
                _collect(pc, block.id, refs, terms, parties)
                plain[block.id] = PlainText(with_label=text, without_label=text)
            case ListBlock():
                for list_item in _iter_list_items(block.items):
                    pc = ctx.plain_context(list_item.id)
                    text = to_plain(parse(list_item.text), pc)
                    _collect(pc, list_item.id, refs, terms, parties)
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
                        _collect(pc, cell.id, refs, terms, parties)
                        plain[cell.id] = PlainText(with_label=text, without_label=text)
                for i, note in enumerate(block.notes):
                    note_id = f"{block.id}__note{i}"
                    pc = ctx.plain_context(note_id)
                    text = to_plain(parse(note), pc)
                    _collect(pc, note_id, refs, terms, parties)
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
                    _collect(pc, note_id, refs, terms, parties)
                    marker = footnote_marker(ctx.numbering, note.n)
                    plain[note_id] = PlainText(with_label=f"{marker}　{text}", without_label=text)
            case BoxBlock():
                if block.title:
                    plain[f"{block.id}__title"] = PlainText(with_label=block.title, without_label=block.title)
            case CommentaryBlock():
                # 逐条解説も `plain_text` に入れる。**紙面にある文字は正解の根拠にできる**
                # 必要があり、入れないと QA の evidence に指定できない（L14 が落ちる）。
                # id は HTML の段落 id（`<block>__p{i}`）と合わせる。
                if block.title:
                    plain[f"{block.id}__title"] = PlainText(with_label=block.title, without_label=block.title)
                for i, text in enumerate(block.text):
                    line_id = f"{block.id}__p{i}"
                    pc = ctx.plain_context(line_id)
                    body = to_plain(parse(text), pc)
                    _collect(pc, line_id, refs, terms, parties)
                    plain[line_id] = PlainText(with_label=body, without_label=body)
    return plain, refs, terms, parties


def _collect(
    pc: PlainContext,
    owner_id: str,
    refs: list[RefInfo],
    terms: list[TermUse],
    parties: list[PartyUse] | None = None,
) -> None:
    for target, mode, rendered in pc.used_refs:
        refs.append(RefInfo(from_id=owner_id, to_id=target, mode=mode, rendered=rendered))
    for term_id in pc.used_terms:
        terms.append(TermUse(term_id=term_id, in_id=owner_id))
    if parties is not None:
        for key, party_mode, rendered in pc.used_parties:
            parties.append(PartyUse(key=key, mode=party_mode, rendered=rendered, in_id=owner_id))


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
    numbering = NumberingContext(
        draft.meta.numbering_scheme,
        draft.meta.digit_style,
        article_heading=draft.meta.article_heading,
        footnote_style=draft.meta.footnote_style,
    )
    index = DocumentIndex(numbering, draft.body, draft.appendices, draft.back_matter.signature)
    ctx = BuildContext(
        draft=draft,
        index=index,
        numbering=numbering,
        caption_labels=assign_caption_labels(draft, numbering),
        terms={t.id: t.term for t in draft.defined_terms},
    )

    plain, refs, terms, party_uses = build_plain_text(ctx)

    tables: dict[str, TableDerived] = {}
    figures: dict[str, FigureDerived] = {}
    formulas: dict[str, FormulaDerived] = {}
    for block, _owner, _article in iter_blocks(draft):
        if isinstance(block, Table):
            tables[block.id] = TableDerived(
                caption_label=ctx.caption_labels.get(block.id),
                header_path=header_paths(block, ctx),
                auto_labels=enumeration_labels(block, ctx),
            )
        elif isinstance(block, Figure):
            labels = resolved_labels(block, ctx, block.id)
            # 経路はラベルの列なので、トークンを解決してから取る（正解に生トークンを残さない）
            resolved = resolve_strings(block, labels)
            order, _ = figure_paths(resolved)
            graph = build_graph(resolved)
            figures[block.id] = FigureDerived(
                caption_label=ctx.caption_labels.get(block.id),
                node_order=order,
                paths=graph_paths(graph),
                graph=graph,
                resolved_labels=labels,
            )
        elif isinstance(block, Formula):
            formulas[block.id] = FormulaDerived(resolved_labels=resolved_labels(block, ctx, block.id))

    derived = Derived(
        labels=index.labels(),
        refs=refs,
        term_uses=terms,
        party_uses=party_uses,
        footnote_index=build_footnote_index(ctx),
        plain_text=plain,
        tables=tables,
        figures=figures,
        formulas=formulas,
        enumerations=build_enumerations(ctx, plain),
        toc=build_toc(ctx),
    )
    return Source(**draft.model_dump(), derived=derived)


def build_content(content_dir: Path) -> Source:
    """content ディレクトリを読んで `source.json` を書き出す。"""
    source = build(load_draft(content_dir))
    dump_json(source, content_dir / "source.json")
    return source


def source_is_stale(content_dir: Path) -> bool:
    """`source.json` が執筆物より古いか。

    render は `source.json` があればそれを使う。執筆物（`doc.json` と `parts/*.json`）を
    直したあと build を挟まずに render すると、**直す前の版が描かれたまま気づけない**。
    実際に図の位置を直して render し直したのに版面が変わらず、原因の特定に時間を使った。
    「古ければ黙って build し直す」ために更新時刻を見る。
    """
    source_path = content_dir / "source.json"
    if not source_path.is_file():
        return True
    built_at = source_path.stat().st_mtime
    inputs = [content_dir / "doc.json", *sorted((content_dir / "parts").glob("*.json"))]
    if any(path.is_file() and path.stat().st_mtime > built_at for path in inputs):
        return True
    # **build の実装を直したときも古い**。`{party:}` を図で解けるようにした直後、
    # 執筆物を触っていないので「新しい」と判定され、直す前の source.json が描かれた。
    # 番号方式の**宣言**（`numbering/*.yaml`）も build の入力なので同じ扱いにする
    # （頭書の段落を無番号にしたとき、実装を触っていないので気づけなかった）。
    from keiyaku.numbering_spec import NUMBERING_DIR

    sources = [*Path(__file__).parent.rglob("*.py"), *NUMBERING_DIR.glob("*.yaml")]
    return any(path.stat().st_mtime > built_at for path in sources)


def unresolved_characters(source: Source) -> list[str]:
    """平文に `{` `}` が残っていないか（トークンの取りこぼし検出）。"""
    return [
        element_id
        for element_id, text in source.derived.plain_text.items()
        if "{" in text.without_label or "}" in text.without_label
    ]
