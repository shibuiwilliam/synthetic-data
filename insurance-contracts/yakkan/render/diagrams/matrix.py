"""matrix：補償項目 × プランの対応表（格子＋記号＋凡例）。"""

from __future__ import annotations

from yakkan.models import Matrix
from yakkan.render.diagrams.base import DiagramStyle, Svg, SvgResult, text_width

PADDING = 6.0
ROW_H = 22.0
HEAD_H = 24.0
COL_W = 62.0
LEGEND_H = 16.0


def render(diagram: Matrix, style: DiagramStyle, figure_id: str) -> SvgResult:
    svg = Svg(style=style, figure_id=figure_id)
    row_label_w = max((text_width(r, style.small_font_size) for r in diagram.rows), default=60.0) + 14
    width = PADDING * 2 + row_label_w + len(diagram.cols) * COL_W
    body_h = len(diagram.rows) * ROW_H

    # 見出し行
    svg.rect(PADDING, PADDING, row_label_w, HEAD_H, fill=style.band, radius=0)
    for c, col in enumerate(diagram.cols):
        x = PADDING + row_label_w + c * COL_W
        svg.rect(x, PADDING, COL_W, HEAD_H, fill=style.band, radius=0, node_id=f"col{c}")
        svg.text(x + COL_W / 2, PADDING + HEAD_H * 0.66, col, size=style.small_font_size, bold=True)

    # 本体
    for r, row in enumerate(diagram.rows):
        y = PADDING + HEAD_H + r * ROW_H
        svg.rect(PADDING, y, row_label_w, ROW_H, fill="#ffffff", radius=0, node_id=f"row{r}")
        svg.text(PADDING + 7, y + ROW_H * 0.68, row, size=style.small_font_size, anchor="start")
        for c in range(len(diagram.cols)):
            x = PADDING + row_label_w + c * COL_W
            mark = diagram.marks[r][c] if r < len(diagram.marks) and c < len(diagram.marks[r]) else ""
            svg.rect(x, y, COL_W, ROW_H, fill="#ffffff", radius=0, node_id=f"cell{r}_{c}")
            svg.text(x + COL_W / 2, y + ROW_H * 0.7, mark, size=style.small_font_size)

    height = PADDING + HEAD_H + body_h
    if diagram.legend:
        height += 6
        text = "　".join(f"{item.mark}＝{item.meaning}" for item in diagram.legend)
        svg.text(
            PADDING,
            height + LEGEND_H * 0.6,
            text,
            size=style.small_font_size - 2,
            anchor="start",
            color=style.muted,
        )
        height += LEGEND_H
    return svg.finish(width, height + PADDING)
