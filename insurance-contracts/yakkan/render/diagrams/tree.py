"""tree：約款の構成図など（lines / bracket / nested）。"""

from __future__ import annotations

from yakkan.models import Tree, TreeNode
from yakkan.render.diagrams.base import DiagramStyle, Svg, SvgResult, text_width, wrap_text

PADDING = 6.0
ROW_H = 24.0
INDENT = 18.0
NODE_PAD = 6.0
NOTE_GAP = 8.0


def _flatten(node: TreeNode, depth: int = 0, out: list[tuple[TreeNode, int]] | None = None):
    out = [] if out is None else out
    out.append((node, depth))
    for child in node.children:
        _flatten(child, depth + 1, out)
    return out


def render(diagram: Tree, style: DiagramStyle, figure_id: str) -> SvgResult:
    svg = Svg(style=style, figure_id=figure_id)
    items = _flatten(diagram.root)
    if diagram.style == "nested":
        return _render_nested(svg, diagram.root, style)

    width = PADDING * 2
    positions: dict[str, tuple[float, float, float, float]] = {}
    for i, (node, depth) in enumerate(items):
        x = PADDING + depth * INDENT
        y = PADDING + i * ROW_H
        label_w = text_width(node.label, style.small_font_size) + NODE_PAD * 2
        positions[node.id] = (x, y, x + label_w, y + ROW_H - 6)
        note_w = text_width(node.note or "", style.small_font_size - 1)
        width = max(width, x + label_w + (NOTE_GAP + note_w if node.note else 0) + PADDING)

    # 罫線（lines）か括弧（bracket）
    for node, depth in items:
        x0, y0, x1, y1 = positions[node.id]
        cy = (y0 + y1) / 2
        if depth > 0:
            parent_x = PADDING + (depth - 1) * INDENT
            svg.line(parent_x + 6, cy, x0, cy)
        if node.children:
            first = positions[node.children[0].id]
            last = positions[node.children[-1].id]
            if diagram.style == "bracket":
                # 「｛」に見えるよう、子の範囲を縦線＋上下の短い横線で囲む
                bx = x0 + INDENT - 6
                svg.line(bx, (first[1] + first[3]) / 2, bx, (last[1] + last[3]) / 2)
            else:
                svg.line(x0 + 6, y1, x0 + 6, (last[1] + last[3]) / 2)

    for node, depth in items:
        x0, y0, x1, y1 = positions[node.id]
        filled = depth == 0
        svg.rect(
            x0,
            y0,
            x1 - x0,
            y1 - y0,
            fill=style.band if filled else "#ffffff",
            node_id=node.id,
        )
        svg.text(
            x0 + NODE_PAD,
            (y0 + y1) / 2 + style.small_font_size * 0.35,
            node.label,
            size=style.small_font_size,
            anchor="start",
            bold=filled,
        )
        if node.note:
            svg.text(
                x1 + NOTE_GAP,
                (y0 + y1) / 2 + style.small_font_size * 0.3,
                node.note,
                size=style.small_font_size - 1,
                anchor="start",
                color=style.muted,
            )

    height = PADDING * 2 + len(items) * ROW_H
    return svg.finish(width, height)


def _render_nested(svg: Svg, root: TreeNode, style: DiagramStyle) -> SvgResult:
    """入れ子枠。親の枠の中に子の枠を並べる。"""

    def measure(node: TreeNode) -> tuple[float, float]:
        label_w = text_width(node.label, style.small_font_size) + NODE_PAD * 2
        if not node.children:
            return label_w, ROW_H - 4
        inner = [measure(c) for c in node.children]
        w = max(max(iw for iw, _ in inner) + NODE_PAD * 2, label_w)
        h = ROW_H + sum(ih for _, ih in inner) + NODE_PAD * (len(inner) + 1)
        return w, h

    def draw(node: TreeNode, x: float, y: float, w: float, h: float) -> None:
        svg.rect(x, y, w, h, fill=style.band if node.children else "#ffffff", node_id=node.id)
        svg.text(
            x + NODE_PAD,
            y + ROW_H * 0.62,
            node.label,
            size=style.small_font_size,
            anchor="start",
            bold=bool(node.children),
        )
        cursor = y + ROW_H
        for child in node.children:
            cw, ch = measure(child)
            draw(child, x + NODE_PAD, cursor, w - NODE_PAD * 2, ch)
            cursor += ch + NODE_PAD

    width, height = measure(root)
    draw(root, PADDING, PADDING, width, height)
    return svg.finish(width + PADDING * 2, height + PADDING * 2)


__all__ = ["render", "wrap_text"]
