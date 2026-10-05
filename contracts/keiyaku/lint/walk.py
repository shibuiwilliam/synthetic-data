"""SourceDraft の走査ヘルパ。lint と build が共有する。"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from keiyaku.models import (
    BoxBlock,
    Cell,
    CommentaryBlock,
    Figure,
    FootnotesBlock,
    Formula,
    FormulaBox,
    FormulaFraction,
    ListBlock,
    ListItem,
    MergedCell,
    Node,
    ParagraphBlock,
    PartiesBlock,
    QaHeadingBlock,
    SourceDraft,
    Table,
)


@dataclass(frozen=True)
class OwnedText:
    """文書内のどこかに現れる文字列 1 つ。"""

    owner_id: str
    path: str  # "ch1_a1.text" のような場所
    text: str
    rich: bool  # RichText としてパースすべきか
    article_id: str | None = None  # 直近の条（脚注の対応検査に使う）
    #: 図・算式の文字列。値を差し込むトークン（{ref:} {term:} {const:}）だけ書ける
    #: （docs/shared_fixes.md A2）。行内マークアップは L06 が弾く。
    flat: bool = False

    @property
    def parseable(self) -> bool:
        """RichText としてパースしてよいか（rich か flat）。"""
        return self.rich or self.flat


@dataclass(frozen=True)
class OwnedId:
    id: str
    kind: str
    path: str


def iter_nodes(nodes: list[Node], ancestors: tuple[str, ...] = ()) -> Iterator[tuple[Node, tuple[str, ...]]]:
    for node in nodes:
        yield node, ancestors
        yield from iter_nodes(node.children, ancestors + (node.id,))


def document_nodes(draft: SourceDraft) -> list[Node]:
    """文書のノード全体（本文＋別紙＋**記名押印欄**）。

    走査は必ずここを通す。`body + appendices` と書くと `back_matter.signature` が漏れて、
    記名押印欄が lint・平文化・描画・正解データのどこかから抜け落ちる
    （実際に平文化から漏れて `sig_p1` が `derived.plain_text` に入らなかった）。
    """
    return [*draft.body, *draft.appendices, *draft.back_matter.signature]


def _iter_list_items(
    items: list[ListItem], owner: str, path: str, article_id: str | None
) -> Iterator[OwnedText]:
    for item in items:
        yield OwnedText(item.id, f"{path}.{item.id}", item.text, True, article_id)
        yield from _iter_list_items(item.children, owner, f"{path}.{item.id}", article_id)


def _iter_list_item_ids(items: list[ListItem], path: str) -> Iterator[OwnedId]:
    for item in items:
        yield OwnedId(item.id, "list_item", path)
        yield from _iter_list_item_ids(item.children, path)


def iter_block_texts(block, owner_id: str, article_id: str | None) -> Iterator[OwnedText]:
    """1 ブロックに含まれる文字列を列挙する。"""
    match block:
        case ParagraphBlock():
            yield OwnedText(block.id, f"{owner_id}.{block.id}", block.text, True, article_id)
        case ListBlock():
            yield from _iter_list_items(block.items, block.id, f"{owner_id}.{block.id}", article_id)
        case Table():
            if block.caption:
                yield OwnedText(block.id, f"{block.id}.caption", block.caption, False, article_id)
            for row in block.grid:
                for cell in row:
                    if isinstance(cell, Cell):
                        yield OwnedText(cell.id, cell.id, cell.text, True, article_id)
            for i, note in enumerate(block.notes):
                yield OwnedText(block.id, f"{block.id}.notes[{i}]", note, True, article_id)
        case Figure():
            if block.caption:
                yield OwnedText(block.id, f"{block.id}.caption", block.caption, False, article_id)
            yield OwnedText(block.id, f"{block.id}.alt", block.alt, False, article_id, flat=True)
            for i, fact in enumerate(block.facts):
                yield OwnedText(block.id, f"{block.id}.facts[{i}]", fact, False, article_id, flat=True)
            yield from _iter_diagram_texts(block, article_id)
        case Formula():
            yield OwnedText(block.id, f"{block.id}.alt", block.alt, False, article_id, flat=True)
            for i, term in enumerate(block.terms):
                if isinstance(term, FormulaBox):
                    yield OwnedText(
                        block.id, f"{block.id}.terms[{i}]", term.box, False, article_id, flat=True
                    )
                elif isinstance(term, FormulaFraction):
                    yield OwnedText(
                        block.id,
                        f"{block.id}.terms[{i}].num",
                        term.fraction.num,
                        False,
                        article_id,
                        flat=True,
                    )
                    yield OwnedText(
                        block.id,
                        f"{block.id}.terms[{i}].den",
                        term.fraction.den,
                        False,
                        article_id,
                        flat=True,
                    )
        case BoxBlock():
            if block.title:
                yield OwnedText(block.id, f"{block.id}.title", block.title, False, article_id)
            for inner in block.blocks:
                yield from iter_block_texts(inner, block.id, article_id)
        case FootnotesBlock():
            for note in block.notes:
                yield OwnedText(block.id, f"{block.id}.notes[{note.n}]", note.text, True, article_id)
        case QaHeadingBlock():
            yield OwnedText(block.id, f"{block.id}.question", block.question, False, article_id)
        case CommentaryBlock():
            # **逐条解説も lint の対象**。紙面に描かれる文字なので、架空性（L08）・文体（L10）・
            # 定数の直書き（L11）・番号ラベルの直書き（L03）がすべて効く必要がある
            # （2026-09-27：歩いていなかったため素通りしていた）。
            if block.title:
                yield OwnedText(block.id, f"{block.id}.title", block.title, False, article_id)
            for i, text in enumerate(block.text):
                yield OwnedText(block.id, f"{block.id}.text[{i}]", text, True, article_id)
        case PartiesBlock():
            pass  # 中身は meta.parties から導出する（当事者の文字列は meta 側で歩く）


def _iter_diagram_texts(figure: Figure, article_id: str | None) -> Iterator[OwnedText]:
    diagram = figure.diagram
    base = f"{figure.id}.diagram"
    match diagram.kind:
        case "flowchart":
            for node in diagram.nodes:
                yield OwnedText(figure.id, f"{base}.{node.id}", node.label, False, article_id, flat=True)
            for i, edge in enumerate(diagram.edges):
                if edge.label:
                    yield OwnedText(figure.id, f"{base}.edges[{i}]", edge.label, False, article_id, flat=True)
        case "tree":
            stack = [diagram.root]
            while stack:
                current = stack.pop()
                yield OwnedText(
                    figure.id, f"{base}.{current.id}", current.label, False, article_id, flat=True
                )
                if current.note:
                    yield OwnedText(
                        figure.id, f"{base}.{current.id}.note", current.note, False, article_id, flat=True
                    )
                stack.extend(current.children)
        case "steps":
            for step in diagram.steps:
                yield OwnedText(figure.id, f"{base}.{step.id}", step.title, False, article_id, flat=True)
                for group in (step.detail, step.asks, step.docs):
                    for i, line in enumerate(group):
                        yield OwnedText(
                            figure.id, f"{base}.{step.id}[{i}]", line, False, article_id, flat=True
                        )
        case "timeline":
            for span in diagram.spans:
                yield OwnedText(figure.id, f"{base}.{span.id}", span.label, False, article_id, flat=True)
            for event in diagram.events:
                yield OwnedText(figure.id, f"{base}.{event.id}", event.label, False, article_id, flat=True)
        case "annotated_mock":
            for field_ in diagram.fields:
                yield OwnedText(figure.id, f"{base}.{field_.id}", field_.label, False, article_id, flat=True)
                if field_.value:
                    yield OwnedText(
                        figure.id, f"{base}.{field_.id}.value", field_.value, False, article_id, flat=True
                    )
            for legend in diagram.legend:
                yield OwnedText(
                    figure.id, f"{base}.legend{legend.badge}", legend.title, False, article_id, flat=True
                )
                yield OwnedText(
                    figure.id, f"{base}.legend{legend.badge}.text", legend.text, False, article_id, flat=True
                )
        case "matrix":
            for i, row in enumerate(diagram.rows):
                yield OwnedText(figure.id, f"{base}.rows[{i}]", row, False, article_id, flat=True)
            for i, col in enumerate(diagram.cols):
                yield OwnedText(figure.id, f"{base}.cols[{i}]", col, False, article_id, flat=True)
            for legend in diagram.legend:
                yield OwnedText(
                    figure.id, f"{base}.legend.{legend.mark}", legend.meaning, False, article_id, flat=True
                )


def iter_blocks(draft: SourceDraft) -> Iterator[tuple[object, str, str | None]]:
    """(block, owner_id, article_id) をすべて返す（入れ子の box も展開する）。"""

    def walk(blocks: list, owner_id: str, article_id: str | None) -> Iterator[tuple[object, str, str | None]]:
        for block in blocks:
            yield block, owner_id, article_id
            if isinstance(block, BoxBlock):
                yield from walk(block.blocks, block.id, article_id)

    front = draft.front_matter
    yield from walk(front.preface, "front_matter.preface", None)
    kinds = node_kinds(draft)
    for node, ancestors in iter_nodes(document_nodes(draft)):
        article_id = node.id if node.kind in FOOTNOTE_OWNER_KINDS else _nearest_article(ancestors, kinds)
        yield from walk(node.blocks, node.id, article_id)
    yield from walk(draft.back_matter.colophon, "back_matter.colophon", None)
    yield from walk(draft.back_matter.contact, "back_matter.contact", None)


#: 脚注（`footnotes` ブロック）を持てるノード。
#: 条が基本だが、**別表にも注記が付く**ので appendix 系も所属先として認める
#: （docs/decisions.md 2026-09-21）。
#: `appendix_section`（別表内の「第1」などの区分）は所属先にしない。
#: 別表の注記は別表の末尾にまとめるのが実物の体裁のため。
FOOTNOTE_OWNER_KINDS = frozenset({"article", "appendix"})


def node_kinds(draft: SourceDraft) -> dict[str, str]:
    """ノード id → kind。走査 1 回ぶんの表として呼び出し側で持ち回す。

    **`id(draft)` をキーにしたモジュール変数で持ってはいけない。**
    Python の `id()` は解放されたオブジェクトのアドレスを再利用するので、
    別の文書が同じアドレスに載ると**前の文書の表を引く**（2026-09-27 に実際に踏んだ。
    脚注の所属先が None になり L02 が偽の error を出した）。
    """
    return {node.id: node.kind for node, _ in iter_nodes(document_nodes(draft))}


def _nearest_article(ancestors: tuple[str, ...], kinds: dict[str, str]) -> str | None:
    """直近の「脚注の所属先」を返す。番号は所属先ごとに 1 から振り直す。"""
    for ancestor in reversed(ancestors):
        if kinds.get(ancestor) in FOOTNOTE_OWNER_KINDS:
            return ancestor
    return None


def iter_texts(draft: SourceDraft) -> Iterator[OwnedText]:
    """文書に現れるすべての文字列（RichText かどうかの別つき）。

    **`meta` の文字列も含める。** 当事者の名称・住所・代表者は紙面に描かれる（記名押印欄・
    当事者表示・頭書）うえ、**実在の社名が最も入りやすい場所**なので、denylist（L08）の
    検査対象に入っていないと架空性の検査が素通りする（2026-09-26 に実際に素通りした）。
    """
    meta = draft.meta
    for name in ("title", "subtitle", "contract_number", "form_code"):
        value = getattr(meta, name, None)
        if value:
            yield OwnedText("meta", f"meta.{name}", value, False)
    for i, party in enumerate(meta.parties):
        for field_name in ("alias", "name", "address", "representative", "role_label"):
            value = getattr(party, field_name, None)
            if value:
                yield OwnedText("meta", f"meta.parties[{i}].{field_name}", value, False)
    if meta.issuer is not None:
        for field_name in ("name", "short_name"):
            value = getattr(meta.issuer, field_name, None)
            if value:
                yield OwnedText("meta", f"meta.issuer.{field_name}", value, False)
    for key, value in meta.constants.items():
        if value:
            yield OwnedText("meta", f"meta.constants.{key}", value, False)
    if meta.disclaimer:
        yield OwnedText("meta", "meta.disclaimer", meta.disclaimer, False)

    # 契約書は表紙を持たないのが普通なので cover は任意（docs/schema.md §2）
    cover = draft.front_matter.cover
    if cover is not None:
        for name in ("title", "subtitle", "issuer_name", "contract_number", "form_code"):
            value = getattr(cover, name)
            if value:
                yield OwnedText("front_matter.cover", f"cover.{name}", value, False)
        for i, note in enumerate(cover.notes):
            yield OwnedText("front_matter.cover", f"cover.notes[{i}]", note, True)

    for term in draft.defined_terms:
        yield OwnedText(term.id, f"{term.id}.term", term.term, False)
        yield OwnedText(term.id, f"{term.id}.definition", term.definition, True)
        for i, note in enumerate(term.notes):
            yield OwnedText(term.id, f"{term.id}.notes[{i}]", note, True)

    kinds = node_kinds(draft)
    for node, ancestors in iter_nodes(document_nodes(draft)):
        article_id = node.id if node.kind in FOOTNOTE_OWNER_KINDS else _nearest_article(ancestors, kinds)
        if node.title:
            yield OwnedText(node.id, f"{node.id}.title", node.title, False, article_id)
        if node.text:
            yield OwnedText(node.id, f"{node.id}.text", node.text, True, article_id)
        if node.summary:
            yield OwnedText(node.id, f"{node.id}.summary", node.summary, False, article_id)

    for block, owner_id, article_id in iter_blocks(draft):
        yield from iter_block_texts(block, owner_id, article_id)


def iter_ids(draft: SourceDraft) -> Iterator[OwnedId]:
    """文書内で一意であるべき id をすべて返す。"""
    for term in draft.defined_terms:
        yield OwnedId(term.id, "term", "defined_terms")
    for node, _ in iter_nodes(document_nodes(draft)):
        yield OwnedId(node.id, node.kind, "body/appendices")
    for block, owner_id, _ in iter_blocks(draft):
        block_type = getattr(block, "type", None)
        if block_type in (None, "page_break"):
            continue
        yield OwnedId(block.id, block_type, owner_id)
        if isinstance(block, Table):
            for row in block.grid:
                for cell in row:
                    if isinstance(cell, Cell):
                        yield OwnedId(cell.id, "cell", block.id)
        elif isinstance(block, ListBlock):
            yield from _iter_list_item_ids(block.items, block.id)
        elif isinstance(block, Figure) and block.diagram.kind == "flowchart":
            for node in block.diagram.nodes:
                yield OwnedId(f"{block.id}__{node.id}", "figure_node", block.id)


def merged_targets(table: Table) -> Iterator[tuple[MergedCell, str]]:
    for row in table.grid:
        for cell in row:
            if isinstance(cell, MergedCell):
                yield cell, table.id
