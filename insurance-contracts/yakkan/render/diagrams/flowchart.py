"""flowchart：格子配置＋直交エッジ＋矢頭（docs/rendering.md §6.7）。"""

from __future__ import annotations

from yakkan.models import Flowchart
from yakkan.render.diagrams.base import DiagramStyle, Svg, SvgResult, wrap_text

#: 格子 1 マスの大きさ（px）
CELL_W = 150.0
CELL_H = 64.0
#: マス内のノードの余白
GAP_X = 18.0
GAP_Y = 26.0
PADDING = 6.0


def render(diagram: Flowchart, style: DiagramStyle, figure_id: str) -> SvgResult:
    svg = Svg(style=style, figure_id=figure_id)
    cols = max((n.col for n in diagram.nodes), default=0) + 1
    rows = max((n.row for n in diagram.nodes), default=0) + 1
    node_w = CELL_W - GAP_X
    node_h = CELL_H - GAP_Y

    centers: dict[str, tuple[float, float]] = {}
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for node in diagram.nodes:
        cx = PADDING + node.col * CELL_W + CELL_W / 2
        cy = PADDING + node.row * CELL_H + CELL_H / 2
        centers[node.id] = (cx, cy)
        boxes[node.id] = (cx - node_w / 2, cy - node_h / 2, cx + node_w / 2, cy + node_h / 2)

    # エッジを先に描いてノードの下に敷く
    for edge in diagram.edges:
        if edge.from_ not in centers or edge.to not in centers:
            continue
        _edge(svg, boxes[edge.from_], boxes[edge.to], edge, style)

    for node in diagram.nodes:
        _node(svg, node, boxes[node.id], style)

    return svg.finish(PADDING * 2 + cols * CELL_W, PADDING * 2 + rows * CELL_H)


def _node(svg: Svg, node, box, style: DiagramStyle) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lines = wrap_text(node.label, w - 10, style.small_font_size)

    match node.shape:
        case "decision":
            svg.polygon(
                [(cx, y0 - 6), (x1 + 6, cy), (cx, y1 + 6), (x0 - 6, cy)],
                fill=style.band,
                node_id=node.id,
            )
        case "start" | "end":
            svg.rect(x0, y0, w, h, fill=style.band, radius=h / 2, node_id=node.id)
        case "note":
            svg.rect(x0, y0, w, h, fill="#ffffff", dashed=True, node_id=node.id)
        case "document":
            # 下辺を波形にした書類の形
            svg.parts.append(
                f'<path d="M{x0},{y0} H{x1} V{y1 - 5} '
                f'C{x0 + w * 0.75},{y1 + 4} {x0 + w * 0.25},{y1 - 12} {x0},{y1 - 5} Z" '
                f'fill="{style.fill}" stroke="{style.stroke}" stroke-width="{style.stroke_width}"/>'
            )
            svg.nodes[node.id] = box
        case _:
            svg.rect(x0, y0, w, h, fill=style.fill, node_id=node.id)

    svg.text_block(cx, cy, lines, size=style.small_font_size)


def _edge(svg: Svg, a, b, edge, style: DiagramStyle) -> None:
    """直交エッジ。同じ列なら縦、同じ行なら横、それ以外は L 字に曲げる。"""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    acx, acy = (ax0 + ax1) / 2, (ay0 + ay1) / 2
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2
    dashed = edge.style == "dashed"

    if abs(acx - bcx) < 1:  # 縦
        points = [(acx, ay1), (bcx, by0)] if bcy > acy else [(acx, ay0), (bcx, by1)]
        label_at = ((acx + bcx) / 2 + 6, (points[0][1] + points[1][1]) / 2 + 3)
        anchor = "start"
    elif abs(acy - bcy) < 1:  # 横
        points = [(ax1, acy), (bx0, bcy)] if bcx > acx else [(ax0, acy), (bx1, bcy)]
        label_at = ((points[0][0] + points[1][0]) / 2, acy - 5)
        anchor = "middle"
    else:  # L 字：分岐は横に出してから下り、相手の上辺に入る（下辺から出すと本線と重なる）
        side_x = ax1 if bcx > acx else ax0
        enter_y = by0 if bcy > acy else by1
        points = [(side_x, acy), (bcx, acy), (bcx, enter_y)]
        label_at = ((side_x + bcx) / 2, acy - 4)
        anchor = "middle"

    svg.polyline(points, dashed=dashed, arrow=True)
    if edge.label:
        svg.text(
            label_at[0],
            label_at[1],
            edge.label,
            size=style.small_font_size - 1,
            anchor=anchor,
            color=style.muted,
        )
