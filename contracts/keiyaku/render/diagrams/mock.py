"""annotated_mock：保険証券などの模式図に ❶..⑳ のバッジを打ち、凡例を添える。"""

from __future__ import annotations

from keiyaku.models import AnnotatedMock
from keiyaku.render.diagrams.base import DiagramStyle, Svg, SvgResult, text_width, wrap_text

PADDING = 8.0
MOCK_W = 300.0
MOCK_H = 190.0
BADGE_R = 7.0
LEGEND_LINE = 13.0
LEGEND_GAP = 12.0
#: 黒丸数字 ❶〜⑳（⑩以降は白丸で代用）
BADGES = "❶❷❸❹❺❻❼❽❾❿⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴"

SUBJECT_TITLES = {
    "order_form": "注文書（見本）",
    "invoice": "請求書（見本）",
    "app_screen": "申込画面（見本）",
}


def badge_char(n: int) -> str:
    return BADGES[n - 1] if 1 <= n <= len(BADGES) else f"({n})"


def render(diagram: AnnotatedMock, style: DiagramStyle, figure_id: str) -> SvgResult:
    svg = Svg(style=style, figure_id=figure_id)
    title = SUBJECT_TITLES.get(diagram.subject, "見本")

    # 証券の外枠
    svg.rect(PADDING, PADDING, MOCK_W, MOCK_H, fill="#ffffff")
    svg.rect(PADDING, PADDING, MOCK_W, 20, fill=style.band, radius=0)
    svg.text(PADDING + MOCK_W / 2, PADDING + 14, title, size=style.small_font_size, bold=True)

    # フィールド枠（x, y, w, h は 0..1 の相対座標として扱う）
    for field in diagram.fields:
        x = PADDING + field.x * MOCK_W
        y = PADDING + 20 + field.y * (MOCK_H - 20)
        w = field.w * MOCK_W
        h = field.h * (MOCK_H - 20)
        svg.rect(x, y, w, h, fill=style.fill, node_id=field.id)
        svg.text(
            x + 5, y + 11, field.label, size=style.small_font_size - 2, anchor="start", color=style.muted
        )
        if field.value:
            svg.text(x + 5, y + h - 5, field.value, size=style.small_font_size - 1, anchor="start")
        # バッジは枠の左上に重ねる
        svg.parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{BADGE_R}" fill="{style.accent}" '
            f'stroke="#ffffff" stroke-width="1"/>'
        )
        svg.text(x, y + 3.2, str(field.badge), size=style.small_font_size - 2, color="#ffffff", bold=True)

    # 凡例
    legend_x = PADDING + MOCK_W + LEGEND_GAP
    legend_w = 0.0
    for item in diagram.legend:
        legend_w = max(legend_w, text_width(f"{badge_char(item.badge)} {item.title}", style.small_font_size))
        for line in wrap_text(_plain(item.text), 180, style.small_font_size - 2):
            legend_w = max(legend_w, text_width(line, style.small_font_size - 2) + 10)
    legend_w = min(max(legend_w, 120.0), 200.0)

    cursor = PADDING + 4
    for item in diagram.legend:
        svg.text(
            legend_x,
            cursor,
            f"{badge_char(item.badge)}　{item.title}",
            size=style.small_font_size - 1,
            anchor="start",
            bold=True,
        )
        cursor += LEGEND_LINE
        for line in wrap_text(_plain(item.text), legend_w - 10, style.small_font_size - 2):
            svg.text(
                legend_x + 10, cursor, line, size=style.small_font_size - 2, anchor="start", color=style.muted
            )
            cursor += LEGEND_LINE - 2
        cursor += 3

    width = legend_x + legend_w + PADDING
    height = max(PADDING * 2 + MOCK_H, cursor + PADDING)
    return svg.finish(width, height)


def _plain(text: str) -> str:
    """凡例の RichText は図では素の文字として描く（トークンは使わせない運用）。"""
    return text
