"""matrix：補償項目 × プランの対応表（格子＋記号＋凡例）。"""

from __future__ import annotations

from yakkan.models import Matrix
from yakkan.render.diagrams.base import DiagramStyle, Svg, SvgResult, text_width, wrap_text

PADDING = 6.0
ROW_H = 22.0
HEAD_H = 24.0
#: 列の最小幅。見出しが長いときは見出しに合わせて広げる
COL_W_MIN = 62.0
LEGEND_H = 16.0
#: 図全体の最大幅（段幅に収めるための上限）
MAX_WIDTH = 460.0


def render(diagram: Matrix, style: DiagramStyle, figure_id: str) -> SvgResult:
    svg = Svg(style=style, figure_id=figure_id)
    row_label_w = max((text_width(r, style.small_font_size) for r in diagram.rows), default=60.0) + 14
    # 列幅は**見出しに合わせて広げる**。固定幅だと列見出しを短縮するしかなく、
    # 実際に「けが／病気／特約」まで削らされた（docs/shared_fixes.md B6）。
    col_w = max(
        COL_W_MIN,
        max((text_width(c, style.small_font_size) for c in diagram.cols), default=0.0) + 10,
    )
    # ただし段幅に収める。入りきらないときは最小幅まで戻す。
    if PADDING * 2 + row_label_w + len(diagram.cols) * col_w > MAX_WIDTH and diagram.cols:
        col_w = max(COL_W_MIN, (MAX_WIDTH - PADDING * 2 - row_label_w) / len(diagram.cols))
    width = PADDING * 2 + row_label_w + len(diagram.cols) * col_w
    body_h = len(diagram.rows) * ROW_H

    # 見出し行
    svg.rect(PADDING, PADDING, row_label_w, HEAD_H, fill=style.band, radius=0)
    for c, col in enumerate(diagram.cols):
        x = PADDING + row_label_w + c * col_w
        svg.rect(x, PADDING, col_w, HEAD_H, fill=style.band, radius=0, node_id=f"col{c}")
        svg.text(x + col_w / 2, PADDING + HEAD_H * 0.66, col, size=style.small_font_size, bold=True)

    # 本体
    for r, row in enumerate(diagram.rows):
        y = PADDING + HEAD_H + r * ROW_H
        svg.rect(PADDING, y, row_label_w, ROW_H, fill="#ffffff", radius=0, node_id=f"row{r}")
        svg.text(PADDING + 7, y + ROW_H * 0.68, row, size=style.small_font_size, anchor="start")
        for c in range(len(diagram.cols)):
            x = PADDING + row_label_w + c * col_w
            mark = diagram.marks[r][c] if r < len(diagram.marks) and c < len(diagram.marks[r]) else ""
            svg.rect(x, y, col_w, ROW_H, fill="#ffffff", radius=0, node_id=f"cell{r}_{c}")
            svg.text(x + col_w / 2, y + ROW_H * 0.7, mark, size=style.small_font_size)

    height = PADDING + HEAD_H + body_h
    if diagram.legend:
        height += 6
        text = "　".join(f"{item.mark}＝{item.meaning}" for item in diagram.legend)
        # 凡例は 1 行に詰め込むと枠からはみ出す。図の幅で折り返す。
        size = style.small_font_size - 2
        for line in wrap_text(text, width - PADDING * 2, size):
            svg.text(
                PADDING,
                height + LEGEND_H * 0.6,
                line,
                size=size,
                anchor="start",
                color=style.muted,
            )
            height += LEGEND_H
    return svg.finish(width, height + PADDING)
