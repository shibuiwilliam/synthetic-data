"""steps：手続きのステップ図。LR は矢羽根形、TB は角丸枠＋下向き矢印。"""

from __future__ import annotations

from keiyaku.models import Steps
from keiyaku.render.diagrams.base import DiagramStyle, Svg, SvgResult, text_width, wrap_text

PADDING = 6.0
CHEVRON_W = 130.0
CHEVRON_H = 40.0
CHEVRON_NOTCH = 12.0
CHEVRON_GAP = 4.0
TB_W = 200.0
TB_H = 34.0
TB_GAP = 22.0
SUB_GAP = 4.0
SUB_LINE = 12.0
#: 小枠の見出し。**約款の言い回し（「お願い」「書類例」）は契約書では使わない**
#: （2026-09-27：賃貸借の更新の手順の図で「お願い」がそのまま出た。yakkan からの持ち越し）。
SUB_TITLES = {"detail": "内容", "asks": "行うこと", "docs": "書類"}


def render(diagram: Steps, style: DiagramStyle, figure_id: str) -> SvgResult:
    svg = Svg(style=style, figure_id=figure_id)
    if diagram.direction == "LR":
        return _render_lr(svg, diagram, style)
    return _render_tb(svg, diagram, style)


def _sub_lines(step) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for key in ("detail", "asks", "docs"):
        values = getattr(step, key)
        if values:
            out.append((SUB_TITLES[key], list(values)))
    return out


def _render_lr(svg: Svg, diagram: Steps, style: DiagramStyle) -> SvgResult:
    n = len(diagram.steps)
    sub_blocks = [_sub_lines(s) for s in diagram.steps]
    sub_rows = max((sum(1 + len(v) for _, v in block) for block in sub_blocks), default=0)
    # 1 行目のベースラインが枠の上端から SUB_LINE*0.85 下に来るので、その分も高さに含める
    sub_h = (sub_rows * SUB_LINE + SUB_GAP * 3) if sub_rows else 0.0

    for i, step in enumerate(diagram.steps):
        x = PADDING + i * (CHEVRON_W + CHEVRON_GAP)
        y = PADDING
        points = [
            (x, y),
            (x + CHEVRON_W - CHEVRON_NOTCH, y),
            (x + CHEVRON_W, y + CHEVRON_H / 2),
            (x + CHEVRON_W - CHEVRON_NOTCH, y + CHEVRON_H),
            (x, y + CHEVRON_H),
            (x + (CHEVRON_NOTCH if i else 0), y + CHEVRON_H / 2),
        ]
        svg.polygon(points, fill=style.band, node_id=step.id)
        lines = wrap_text(step.title, CHEVRON_W - CHEVRON_NOTCH * 2, style.small_font_size)
        svg.text_block(x + CHEVRON_W / 2, y + CHEVRON_H / 2, lines, size=style.small_font_size, bold=True)

        if sub_blocks[i]:
            top = y + CHEVRON_H + SUB_GAP
            svg.rect(x, top, CHEVRON_W - CHEVRON_GAP, sub_h - SUB_GAP, fill="#ffffff")
            cursor = top + SUB_LINE * 0.85
            for title, values in sub_blocks[i]:
                svg.text(
                    x + 5,
                    cursor,
                    title,
                    size=style.small_font_size - 2,
                    anchor="start",
                    color=style.accent,
                    bold=True,
                )
                cursor += SUB_LINE
                for value in values:
                    svg.text(
                        x + 9,
                        cursor,
                        value,
                        size=style.small_font_size - 2,
                        anchor="start",
                        color=style.muted,
                    )
                    cursor += SUB_LINE

    width = PADDING * 2 + n * CHEVRON_W + (n - 1) * CHEVRON_GAP
    height = PADDING * 2 + CHEVRON_H + sub_h
    return svg.finish(width, height)


def _render_tb(svg: Svg, diagram: Steps, style: DiagramStyle) -> SvgResult:
    y = PADDING
    width = PADDING * 2 + TB_W
    for i, step in enumerate(diagram.steps):
        svg.rect(PADDING, y, TB_W, TB_H, fill=style.band, node_id=step.id)
        lines = wrap_text(step.title, TB_W - 12, style.small_font_size)
        svg.text_block(PADDING + TB_W / 2, y + TB_H / 2, lines, size=style.small_font_size, bold=True)

        blocks = _sub_lines(step)
        if blocks:
            bx = PADDING + TB_W + 10
            rows = sum(1 + len(v) for _, v in blocks)
            box_h = rows * SUB_LINE + SUB_GAP * 3
            box_w = max(text_width(t, style.small_font_size - 2) + 16 for t, _ in blocks)
            for _, values in blocks:
                for value in values:
                    box_w = max(box_w, text_width(value, style.small_font_size - 2) + 22)
            svg.rect(bx, y, box_w, box_h, fill="#ffffff")
            cursor = y + SUB_GAP + SUB_LINE * 0.75
            for title, values in blocks:
                svg.text(
                    bx + 5,
                    cursor,
                    title,
                    size=style.small_font_size - 2,
                    anchor="start",
                    color=style.accent,
                    bold=True,
                )
                cursor += SUB_LINE
                for value in values:
                    svg.text(
                        bx + 9,
                        cursor,
                        value,
                        size=style.small_font_size - 2,
                        anchor="start",
                        color=style.muted,
                    )
                    cursor += SUB_LINE
            width = max(width, bx + box_w + PADDING)
            y += max(TB_H, box_h)
        else:
            y += TB_H

        if i < len(diagram.steps) - 1:
            svg.line(PADDING + TB_W / 2, y, PADDING + TB_W / 2, y + TB_GAP, arrow=True)
            y += TB_GAP

    return svg.finish(width, y + PADDING)
