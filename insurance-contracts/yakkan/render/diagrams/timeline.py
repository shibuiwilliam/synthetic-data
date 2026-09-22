"""timeline：保険期間・等級推移などの時間軸図。レーン・区間バー・イベント旗。"""

from __future__ import annotations

from yakkan.models import Timeline
from yakkan.render.diagrams.base import DiagramStyle, Svg, SvgResult, text_width

PADDING = 8.0
AXIS_PAD_LEFT = 8.0
AXIS_PAD_RIGHT = 8.0
LANE_H = 26.0
BAR_H = 16.0
AXIS_H = 20.0
EVENT_H = 26.0
WIDTH = 460.0


def render(diagram: Timeline, style: DiagramStyle, figure_id: str) -> SvgResult:
    svg = Svg(style=style, figure_id=figure_id)
    ticks = list(diagram.axis.ticks) or [diagram.axis.start, diagram.axis.end]
    positions = _tick_positions(diagram, ticks)

    lanes = max((s.lane for s in diagram.spans), default=0) + 1
    top = PADDING + EVENT_H if diagram.events else PADDING
    axis_y = top + lanes * LANE_H + 4

    # 区間バー
    for span in diagram.spans:
        x0 = positions(span.from_)
        x1 = positions(span.to)
        y = top + span.lane * LANE_H
        svg.rect(x0, y, max(x1 - x0, 2), BAR_H, fill=style.band, node_id=span.id)
        label_x = (x0 + x1) / 2
        if text_width(span.label, style.small_font_size - 1) > (x1 - x0) - 6:
            svg.text(x1 + 4, y + BAR_H * 0.72, span.label, size=style.small_font_size - 1, anchor="start")
        else:
            svg.text(label_x, y + BAR_H * 0.72, span.label, size=style.small_font_size - 1)

    # 軸と目盛
    svg.line(PADDING, axis_y, WIDTH - PADDING, axis_y)
    tick_size = style.small_font_size - 2
    for tick in ticks:
        x = positions(tick)
        svg.line(x, axis_y - 3, x, axis_y + 3)
        # 目盛のラベルは既定では中央揃え。両端の目盛は軸の端にあるので、
        # そのままだと**ラベルの半分が viewBox の外に出て切れる**（5 文字を超えると顕著）。
        # 端では内側に寄せ、中間でも枠から出そうなら寄せる。
        label = str(tick)
        half = text_width(label, tick_size) / 2
        if x - half < 1.0:
            # anchor="start" は **左端**の座標を指定する
            svg.text(
                1.0,
                axis_y + AXIS_H * 0.75,
                label,
                size=tick_size,
                color=style.muted,
                anchor="start",
            )
        elif x + half > WIDTH - 1.0:
            # anchor="end" は **右端**の座標を指定する
            svg.text(
                WIDTH - 1.0,
                axis_y + AXIS_H * 0.75,
                label,
                size=tick_size,
                color=style.muted,
                anchor="end",
            )
        else:
            svg.text(x, axis_y + AXIS_H * 0.75, label, size=tick_size, color=style.muted)

    # イベント旗
    for event in diagram.events:
        x = positions(event.at)
        svg.line(x, PADDING + EVENT_H, x, axis_y, dashed=True)
        label_w = text_width(event.label, style.small_font_size - 1) + 10
        # 端のイベントは旗が viewBox からはみ出すので、内側に寄せる
        label_x = min(max(x - label_w / 2, PADDING), WIDTH - PADDING - label_w)
        svg.rect(label_x, PADDING, label_w, EVENT_H - 8, fill="#ffffff", node_id=event.id)
        svg.text(
            label_x + label_w / 2, PADDING + (EVENT_H - 8) * 0.68, event.label, size=style.small_font_size - 1
        )

    return svg.finish(WIDTH, axis_y + AXIS_H + PADDING)


def _tick_positions(diagram: Timeline, ticks: list[str]):
    """目盛ラベル or 数値 → x 座標。"""
    left = PADDING + AXIS_PAD_LEFT
    right = WIDTH - PADDING - AXIS_PAD_RIGHT
    index = {str(t): i for i, t in enumerate(ticks)}
    last = max(len(ticks) - 1, 1)

    def position(value) -> float:
        key = str(value)
        if key in index:
            return left + (right - left) * index[key] / last
        try:  # 数値指定は 0..last の内分とみなす
            number = float(value)
        except (TypeError, ValueError):
            return left
        return left + (right - left) * max(0.0, min(number, last)) / last

    return position
