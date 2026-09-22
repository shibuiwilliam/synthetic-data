"""Source → HTML（docs/rendering.md §6.3）。

- すべての正解要素に `id` と `data-kind` を付ける。`layout.json` はこれを拾う。
- 見出しはラベル span と文言 span を分ける。
- 項・号は CSS grid のぶら下げインデント。float・絶対配置は本文に使わない。
- 段またぎの表は `<figure>` でくるんでそちらに `column-span: all` を当てる
  （`<table>` 直接指定は効かない：docs/decisions.md 2026-09-21）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from yakkan.build import BuildContext, enumeration_labels
from yakkan.fonts import font_face_css
from yakkan.models import (
    BoxBlock,
    Cell,
    Figure,
    FootnotesBlock,
    Formula,
    ListBlock,
    ListItem,
    Node,
    PageBreakBlock,
    ParagraphBlock,
    QaHeadingBlock,
    Source,
    Table,
)
from yakkan.numbering import HEADING_SPACE, NumberingContext, footnote_marker
from yakkan.render.inline import InlineContext, render_inline
from yakkan.styles import Style

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
CSS_DIR = Path(__file__).resolve().parents[2] / "styles" / "css"

#: 見出しの HTML タグ（ぶら下げ段落にしない種別）
HEADING_TAGS = {
    # part と chapter は同じ h2（版面を変えないため）。
    # @page のヘッダで編と章を分けるのは CSS 側の属性セレクタで行う。
    "part": "h2",
    "chapter": "h2",
    "section": "h3",
    "article": "h4",
    "appendix": "h2",
    "appendix_section": "h3",
}
PARAGRAPH_KINDS = {"paragraph", "item", "subitem", "subsubitem"}


def _is_trailing(block) -> bool:
    """条末（子ノードの後）に置くブロックか。脚注と欄外注がこれにあたる（docs/schema.md §5.6）。"""
    if isinstance(block, FootnotesBlock):
        return True
    return isinstance(block, BoxBlock) and block.style == "margin_note"


@dataclass
class HtmlBuilder:
    """1 文書ぶんの HTML を組み立てる。"""

    source: Source
    style: Style
    ctx: BuildContext
    notes: list[str] = field(default_factory=list)
    #: 図 id → SVG の描画結果（viewBox 内のノード bbox を持つ）
    figure_nodes: dict = field(default_factory=dict)

    def inline_ctx(self, element_id: str, auto_label: str = "") -> InlineContext:
        return InlineContext(
            resolve_ref=lambda target, mode: self.ctx.resolve_ref(target, mode, element_id),
            resolve_term=lambda term_id: self.ctx.terms.get(term_id, term_id),
            resolve_const=lambda key: self.source.meta.constants.get(key, ""),
            footnote_marker=lambda n: footnote_marker(self.ctx.numbering, n),
            auto_label=auto_label,
            element_id=element_id,
        )

    def inline(self, text: str, element_id: str, auto_label: str = "") -> str:
        return render_inline(text, self.inline_ctx(element_id, auto_label))

    # --- ノード -------------------------------------------------------------

    #: ヘッダに経路を出すノード（部・章・別表）。節や条までは出さない。
    HEADER_PATH_KINDS = frozenset({"part", "chapter", "appendix"})

    def _header_path(self, node: Node) -> str:
        """`@page` のヘッダに出す文字列（「第１編␣ご契約のしおり␣第３章␣…」）。

        `derived.labels[].path`（祖先の heading_text）に自分の heading_text を足す。
        **別表は編の外**にあるので祖先を付けない。
        """
        if node.kind not in self.HEADER_PATH_KINDS:
            return ""
        info = self.source.derived.labels.get(node.id)
        if info is None:
            return ""
        if node.kind == "appendix":
            return info.heading_text
        return HEADING_SPACE.join([*info.path, info.heading_text])

    def node_html(self, node: Node, depth: int = 0) -> str:
        parts: list[str] = []
        label = self.source.derived.labels[node.id].label
        title = node.title or ""
        if node.kind in PARAGRAPH_KINDS:
            parts.append(self._paragraph_html(node, label))
        else:
            tag = HEADING_TAGS.get(node.kind, "h4")
            label_span = f'<span class="label" id="{node.id}_label">{escape(label)}</span>' if label else ""
            # derived.heading_text と PDF のテキスト層を一字一句そろえる。
            # 条は「第１条（告知義務）」、それ以外は「第１章␣賠償責任条項」（␣ は U+3000）。
            # 間隔を CSS の margin で空けるとテキスト層に文字が入らず heading_text と食い違う。
            if node.kind == "article" and title:
                title_text, separator = f"（{title}）", ""
            else:
                title_text = title
                separator = HEADING_SPACE if (label and title) else ""
            sep_span = f'<span class="sep">{separator}</span>' if separator else ""
            title_span = (
                f'<span class="title" id="{node.id}_title">{escape(title_text)}</span>' if title_text else ""
            )
            # ヘッダに出す経路を **1 本の文字列**として渡す。
            # 編と章を別々の CSS string にすると、編の境界がページ途中に来たとき
            # 別々の編の値を拾って噛み合わなくなる（life-0002 で「第2編…第6章（実は第1編）」が出た）。
            header_path = self._header_path(node)
            path_attr = f' data-headerpath="{escape(header_path)}"' if header_path else ""
            parts.append(
                f'<{tag} id="{node.id}" data-kind="{node.kind}"{path_attr}>'
                f"{label_span}{sep_span}{title_span}</{tag}>"
            )
        # 条末に置くブロック（脚注・欄外注）は子（項）をすべて出してから最後に置く。
        # それ以外のブロック（項に付く列挙表など）は、その場に置く。
        leading = [b for b in node.blocks if not _is_trailing(b)]
        trailing = [b for b in node.blocks if _is_trailing(b)]
        for block in leading:
            parts.append(self.block_html(block))
        for child in node.children:
            parts.append(self.node_html(child, depth + 1))
        for block in trailing:
            parts.append(self.block_html(block))
        return "\n".join(p for p in parts if p)

    def _paragraph_html(self, node: Node, label: str) -> str:
        text = self.inline(node.text or "", node.id)
        if not label:
            return f'<div class="para no-label" id="{node.id}" data-kind="{node.kind}">{text}</div>'
        return (
            f'<div class="para" id="{node.id}" data-kind="{node.kind}">'
            f'<span class="label" id="{node.id}_label">{escape(label)}</span>'
            f'<span class="text" id="{node.id}_text">{text}</span></div>'
        )

    # --- ブロック -----------------------------------------------------------

    def block_html(self, block) -> str:
        match block:
            case ParagraphBlock():
                return (
                    f'<div class="para no-label" id="{block.id}" data-kind="paragraph">'
                    f"{self.inline(block.text, block.id)}</div>"
                )
            case ListBlock():
                return self._list_html(block)
            case Table():
                return self._table_html(block)
            case Figure():
                return self._figure_html(block)
            case Formula():
                return self._formula_html(block)
            case BoxBlock():
                inner = "\n".join(self.block_html(b) for b in block.blocks)
                title = (
                    f'<span class="box-title" id="{block.id}_title">{escape(block.title)}</span>'
                    if block.title
                    else ""
                )
                anchor = f' data-anchor="{block.anchor}"' if block.anchor else ""
                return (
                    f'<div class="box" id="{block.id}" data-kind="box" data-style="{block.style}"{anchor}>'
                    f"{title}{inner}</div>"
                )
            case FootnotesBlock():
                lines = []
                for note in block.notes:
                    note_id = f"{block.id}__n{note.n}"
                    marker = escape(footnote_marker(self.ctx.numbering, note.n))
                    lines.append(
                        f'<div class="fn-line" id="{note_id}" data-kind="footnote">'
                        f'<span class="label">{marker}</span>'
                        f'<span class="text">{self.inline(note.text, note_id)}</span></div>'
                    )
                return (
                    f'<div class="footnotes" id="{block.id}" data-kind="footnotes">'
                    + "".join(lines)
                    + "</div>"
                )
            case QaHeadingBlock():
                return f'<h4 id="{block.id}" data-kind="qa_heading">{escape(block.question)}</h4>'
            case PageBreakBlock():
                # **段組コンテナを閉じて開き直す**ことで改ページする。
                # `break-before: page` は multicol の中では効かない（書き方を 5 通り試して全滅）。
                return (
                    f'</div><div class="page-break" id="{block.id}" data-kind="page_break"></div>'
                    f'<div class="cols">'
                )
        return ""

    def _list_html(self, block: ListBlock) -> str:
        def items(items_: list[ListItem], depth: int) -> str:
            out = []
            for item in items_:
                out.append(
                    f'<div class="para no-label" id="{item.id}" data-kind="list_item" '
                    f'style="margin-left:{depth * 1.6}em">{self.inline(item.text, item.id)}</div>'
                )
                if item.children:
                    out.append(items(item.children, depth + 1))
            return "".join(out)

        return f'<div class="list" id="{block.id}" data-kind="list">{items(block.items, 0)}</div>'

    def _table_html(self, table: Table) -> str:
        auto = enumeration_labels(table, self.ctx)
        header_rows = table.layout.header_rows
        rows_html: list[str] = []
        for r, row in enumerate(table.grid):
            cells: list[str] = []
            for cell in row:
                if not isinstance(cell, Cell):
                    continue  # 被結合位置は描画しない
                tag = "th" if cell.role == "header" else "td"
                classes = []
                if cell.role == "stub":
                    classes.append("stub")
                if cell.align:
                    classes.append(f"align-{cell.align}")
                attrs = f' class="{" ".join(classes)}"' if classes else ""
                if cell.rowspan > 1:
                    attrs += f' rowspan="{cell.rowspan}"'
                if cell.colspan > 1:
                    attrs += f' colspan="{cell.colspan}"'
                body = self.inline(cell.text, cell.id, auto_label=auto.get(cell.id, ""))
                cells.append(
                    f'<{tag} id="{cell.id}" data-kind="cell" data-role="{cell.role}"{attrs}>{body}</{tag}>'
                )
            rows_html.append((r, "".join(cells)))

        head = "".join(f"<tr>{html}</tr>" for r, html in rows_html if r < header_rows)
        body = "".join(f"<tr>{html}</tr>" for r, html in rows_html if r >= header_rows)
        thead = f"<thead>{head}</thead>" if head else ""
        caption_label = self.source.derived.tables[table.id].caption_label or ""
        caption = ""
        if table.caption:
            caption = (
                f'<figcaption id="{table.id}__caption" data-kind="caption">'
                f"{escape(caption_label)}　{escape(table.caption)}</figcaption>"
            )
        notes = "".join(
            f'<div class="table-note" id="{table.id}__note{i}" data-kind="table_note">'
            f"{self.inline(note, f'{table.id}__note{i}')}</div>"
            for i, note in enumerate(table.notes)
        )
        span = " span-all" if table.layout.span_columns else ""
        enum_class = " enumeration" if table.semantic_type == "enumeration" else ""
        # col_widths（比率）は <colgroup> で渡す。指定が無ければブラウザ既定の自動幅
        colgroup = ""
        if table.layout.col_widths:
            total = sum(table.layout.col_widths) or 1
            cols = "".join(f'<col style="width:{w / total * 100:.2f}%">' for w in table.layout.col_widths)
            colgroup = f"<colgroup>{cols}</colgroup>"
        return (
            f'<figure class="table-wrap{span}" id="{table.id}__wrap" data-kind="table_wrap">'
            f"{caption}"
            f'<table id="{table.id}" data-kind="table" data-semantic="{table.semantic_type}"'
            f' class="{enum_class.strip()}">{colgroup}{thead}<tbody>{body}</tbody></table>{notes}</figure>'
        )

    def _figure_html(self, figure: Figure) -> str:
        from yakkan.build import resolve_strings
        from yakkan.render.diagrams import DiagramStyle, render_diagram

        derived = self.source.derived.figures[figure.id]
        # 図の中の {const:} {term:} {ref:} は build が解決済み。SVG を組む前に当てる（A2）
        figure = resolve_strings(figure, derived.resolved_labels)
        caption_label = derived.caption_label or ""
        caption = ""
        if figure.caption:
            caption = (
                f'<figcaption id="{figure.id}__caption" data-kind="caption">'
                f"{escape(caption_label)}　{escape(figure.caption)}</figcaption>"
            )
        span = " span-all" if figure.size == "full" else ""
        result = render_diagram(figure.diagram, DiagramStyle.from_style(self.style), figure.id)
        # ノードの viewBox 内 bbox を控えておき、描画後にページ座標へ変換する（§6.8-3）
        self.figure_nodes[figure.id] = result
        return (
            f'<figure class="figure-wrap{span}" id="{figure.id}__wrap" data-kind="figure_wrap">'
            f'<div class="figure-body" id="{figure.id}" data-kind="figure">{result.svg}</div>'
            f"{caption}</figure>"
        )

    def _formula_html(self, formula: Formula) -> str:
        from yakkan.build import resolve_strings
        from yakkan.render.formula import formula_html

        derived = self.source.derived.formulas.get(formula.id)
        labels = derived.resolved_labels if derived else {}
        return formula_html(resolve_strings(formula, labels))


def build_css(style: Style, source: Source) -> str:
    env = Environment(loader=FileSystemLoader(str(CSS_DIR)), undefined=StrictUndefined, autoescape=False)
    template = env.get_template(f"{style.style_id}.css.j2")
    fallbacks = ", ".join(f"'{f}'" for f in style.fonts.symbol_fallback)
    sizes = dict(style.sizes)
    sizes.setdefault("cover_pt", 20.0)
    return template.render(
        style=style,
        m=style.page.margin_mm,
        s=sizes,
        p=style.palette,
        font_faces=font_face_css(),
        fallbacks=fallbacks,
        form_code=source.meta.form_code,
        digit_style=source.meta.digit_style,
    )


def build_html(
    source: Source, style: Style, toc_pages: dict[str, int] | None = None
) -> tuple[str, list[str], dict]:
    """HTML・注意メッセージ・図の viewBox 内ノード bbox を返す。

    `toc_pages` を渡すと、目次のページ番号を `target-counter` ではなく**文字として**埋める
    （2 パス描画。docs/gotchas.md「目次のページ番号が収束しない」）。
    """
    numbering = NumberingContext(source.meta.numbering_scheme, source.meta.digit_style)
    from yakkan.build import assign_caption_labels
    from yakkan.numbering import DocumentIndex

    ctx = BuildContext(
        draft=source,
        index=DocumentIndex(numbering, source.body, source.appendices),
        numbering=numbering,
        caption_labels=assign_caption_labels(source, numbering),
        terms={t.id: t.term for t in source.defined_terms},
    )
    builder = HtmlBuilder(source=source, style=style, ctx=ctx)

    body_html = "\n".join(builder.node_html(node) for node in source.body)
    appendices_html = "\n".join(builder.node_html(node) for node in source.appendices)
    colophon_html = "\n".join(builder.block_html(b) for b in source.back_matter.colophon)
    # 前付け（§3.1 A2/A3/A5）。lint は source を見るので、ここで描かないと
    # 「JSON にはあるが PDF に出ない」要素ができてしまう（verify V05/V10 が検出する）
    front = source.front_matter
    preface_html = "\n".join(builder.block_html(b) for b in front.preface)
    purpose_index_html = builder.block_html(front.purpose_index) if front.purpose_index else ""
    rider_index_html = builder.block_html(front.rider_index) if front.rider_index else ""
    petname_table_html = builder.block_html(front.petname_table) if front.petname_table else ""
    note_html = [
        builder.inline(note, f"cover_note{i}") for i, note in enumerate(source.front_matter.cover.notes)
    ]

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)), undefined=StrictUndefined, autoescape=False
    )
    template = env.get_template("document.html.j2")
    html = template.render(
        source=source,
        cover=source.front_matter.cover,
        note_html=note_html,
        toc=source.derived.toc if source.front_matter.toc.enabled else [],
        body_html=body_html,
        appendices_html=appendices_html,
        colophon_html=colophon_html,
        preface_html=preface_html,
        purpose_index_html=purpose_index_html + petname_table_html,
        rider_index_html=rider_index_html,
        css=build_css(style, source),
        toc_pages=toc_pages or {},
    )
    return html, builder.notes, builder.figure_nodes
