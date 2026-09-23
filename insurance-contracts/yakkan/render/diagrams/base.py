"""図の SVG 化の共通部品（docs/rendering.md §6.7）。

- 座標はすべて Python で決める。外部レイアウトエンジンは使わない（CLAUDE.md §2-5）。
- viewBox の単位は CSS px。`figure_layout`（ノード id → viewBox 内 bbox）を返し、
  描画後に `layout.figures[].nodes` へページ座標（pt）で変換する（§6.8-3）。
- **`<text>` には `font-family` と `font-size` を必ず属性で書く。**
  無指定だと同梱外のシステムフォントに化けて字幅の見積りも再現性も壊れる（実測、docs/gotchas.md）。
- 配色は style の palette。線幅 1px、角丸 4px。**地味で説明的に**（影・グラデーション・装飾は入れない）。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from html import escape

#: viewBox 内の bbox（x0, y0, x1, y1）
Box = tuple[float, float, float, float]

#: 半角として数える文字幅（em）
WIDTH_ASCII = 0.55
#: 半角カタカナ
WIDTH_HALFWIDTH_KANA = 0.5
#: 全角（CJK・記号）
WIDTH_FULLWIDTH = 1.0


def char_width(char: str) -> float:
    """1 文字の幅（em）。docs/rendering.md §6.7 の概算。"""
    if char == "\n":
        return 0.0
    east_asian = unicodedata.east_asian_width(char)
    if east_asian in ("W", "F"):
        return WIDTH_FULLWIDTH
    if east_asian == "H":  # 半角カタカナ
        return WIDTH_HALFWIDTH_KANA
    if ord(char) >= 0x2000:  # ①❶◆☞ などの記号は全角扱い
        return WIDTH_FULLWIDTH
    return WIDTH_ASCII


def text_width(text: str, font_size: float) -> float:
    """文字列の描画幅（px）の見積り。"""
    return sum(char_width(c) for c in text) * font_size


def wrap_text(text: str, max_width: float, font_size: float) -> list[str]:
    """`max_width`（px）に収まるよう折り返す。改行文字は尊重する。"""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        width = 0.0
        for char in paragraph:
            w = char_width(char) * font_size
            if current and width + w > max_width:
                lines.append(current)
                current, width = char, w
            else:
                current += char
                width += w
        lines.append(current)
    return lines or [""]


@dataclass(frozen=True)
class DiagramStyle:
    """図の描画スタイル。style の palette から作る。"""

    font_family: str = "Noto Sans JP"
    font_size: float = 11.0
    small_font_size: float = 9.0
    text: str = "#111111"
    stroke: str = "#333333"
    fill: str = "#f3f4f6"
    accent: str = "#1f4e79"
    band: str = "#eef1f4"
    muted: str = "#666666"
    stroke_width: float = 1.0
    radius: float = 4.0

    @classmethod
    def from_style(cls, style) -> DiagramStyle:
        palette = getattr(style, "palette", {}) or {}
        fonts = getattr(style, "fonts", None)
        return cls(
            font_family=getattr(fonts, "heading", cls.font_family),
            text=palette.get("text", cls.text),
            stroke=palette.get("rule", cls.stroke),
            fill=palette.get("note_bg", cls.fill),
            accent=palette.get("accent", cls.accent),
            band=palette.get("band", cls.band),
        )


@dataclass
class SvgResult:
    """図 1 点ぶんの描画結果。"""

    svg: str
    width: float
    height: float
    #: ノード id → viewBox 内 bbox
    nodes: dict[str, Box] = field(default_factory=dict)


@dataclass
class Svg:
    """SVG 断片の組立て。座標は viewBox（px）。"""

    style: DiagramStyle
    figure_id: str
    width: float = 0.0
    height: float = 0.0
    parts: list[str] = field(default_factory=list)
    nodes: dict[str, Box] = field(default_factory=dict)
    #: 置いた辺ラベルの矩形。重なりを避けるために覚えておく
    _label_boxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    #: 辺ラベルは**最後に**描く。先に描くと、後から引かれた連結線が白地の上を横切る
    _label_parts: list[str] = field(default_factory=list)

    @property
    def arrow_id(self) -> str:
        """矢頭マーカーの id。図ごとに分ける（1 つの HTML に複数の SVG が入るため）。"""
        return f"{self.figure_id}__arrow"

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str | None = None,
        stroke: str | None = None,
        radius: float | None = None,
        dashed: bool = False,
        node_id: str | None = None,
        element_id: str | None = None,
    ) -> None:
        attrs = [
            f'x="{_n(x)}"',
            f'y="{_n(y)}"',
            f'width="{_n(w)}"',
            f'height="{_n(h)}"',
            f'rx="{_n(self.style.radius if radius is None else radius)}"',
            f'fill="{fill or self.style.fill}"',
            f'stroke="{stroke or self.style.stroke}"',
            f'stroke-width="{self.style.stroke_width}"',
        ]
        if dashed:
            attrs.append('stroke-dasharray="3 2"')
        if element_id:
            attrs.insert(0, f'id="{element_id}"')
        self.parts.append(f"<rect {' '.join(attrs)}/>")
        if node_id:
            self.nodes[node_id] = (x, y, x + w, y + h)

    def polygon(
        self,
        points: list[tuple[float, float]],
        *,
        fill: str | None = None,
        stroke: str | None = None,
        node_id: str | None = None,
    ) -> None:
        coords = " ".join(f"{_n(x)},{_n(y)}" for x, y in points)
        self.parts.append(
            f'<polygon points="{coords}" fill="{fill or self.style.fill}" '
            f'stroke="{stroke or self.style.stroke}" stroke-width="{self.style.stroke_width}"/>'
        )
        if node_id:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            self.nodes[node_id] = (min(xs), min(ys), max(xs), max(ys))

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        dashed: bool = False,
        arrow: bool = False,
        stroke: str | None = None,
    ) -> None:
        attrs = [
            f'x1="{_n(x1)}"',
            f'y1="{_n(y1)}"',
            f'x2="{_n(x2)}"',
            f'y2="{_n(y2)}"',
            f'stroke="{stroke or self.style.stroke}"',
            f'stroke-width="{self.style.stroke_width}"',
        ]
        if dashed:
            attrs.append('stroke-dasharray="3 2"')
        if arrow:
            attrs.append(f'marker-end="url(#{self.arrow_id})"')
        self.parts.append(f"<line {' '.join(attrs)}/>")

    def polyline(
        self, points: list[tuple[float, float]], *, dashed: bool = False, arrow: bool = False
    ) -> None:
        coords = " ".join(f"{_n(x)},{_n(y)}" for x, y in points)
        attrs = [
            f'points="{coords}"',
            'fill="none"',
            f'stroke="{self.style.stroke}"',
            f'stroke-width="{self.style.stroke_width}"',
        ]
        if dashed:
            attrs.append('stroke-dasharray="3 2"')
        if arrow:
            attrs.append(f'marker-end="url(#{self.arrow_id})"')
        self.parts.append(f"<polyline {' '.join(attrs)}/>")

    def text(
        self,
        x: float,
        y: float,
        content: str,
        *,
        size: float | None = None,
        anchor: str = "middle",
        color: str | None = None,
        bold: bool = False,
        element_id: str | None = None,
    ) -> None:
        """1 行のテキスト。font-family と font-size は必ず属性で書く。"""
        size = size or self.style.font_size
        attrs = [
            f'x="{_n(x)}"',
            f'y="{_n(y)}"',
            f'text-anchor="{anchor}"',
            f'font-family="{self.style.font_family}"',
            f'font-size="{_n(size)}"',
            f'fill="{color or self.style.text}"',
        ]
        if bold:
            attrs.append('font-weight="700"')
        if element_id:
            attrs.insert(0, f'id="{element_id}"')
        self.parts.append(f"<text {' '.join(attrs)}>{escape(content)}</text>")

    def edge_label(
        self,
        x: float,
        y: float,
        content: str,
        *,
        size: float | None = None,
        anchor: str = "middle",
        color: str | None = None,
    ) -> None:
        """辺のラベル。**重なりを避け、線の上に白地を敷いてから**描く。

        同じ位置に 2 本の辺のラベルが来ると文字が重なって読めなくなる
        （golf-0001 の図2 で「90日以内」と「いいえ（30日以内）」が重なった。
        docs/remaining_issues.md X3）。置いた矩形を覚えておき、ぶつかるときは
        下へずらす。連結線がラベルを貫くのも読みにくいので、白い下地を敷く。
        """
        size = size or self.style.font_size
        width = text_width(content, size)
        left = {"start": x, "middle": x - width / 2, "end": x - width}[anchor]
        for _ in range(5):
            box = (left - 1.5, y - size, left + width + 1.5, y + size * 0.3)
            if not any(
                box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]
                for other in self._label_boxes
            ):
                break
            y += size + 2.5
        else:
            box = (left - 1.5, y - size, left + width + 1.5, y + size * 0.3)
        self._label_boxes.append(box)
        before = len(self.parts)
        self.parts.append(
            f'<rect x="{_n(box[0])}" y="{_n(box[1])}" width="{_n(box[2] - box[0])}" '
            f'height="{_n(box[3] - box[1])}" fill="#ffffff" stroke="none"/>'
        )
        self.text(x, y, content, size=size, anchor=anchor, color=color)
        self._label_parts.extend(self.parts[before:])
        del self.parts[before:]

    def text_block(
        self,
        cx: float,
        cy: float,
        lines: list[str],
        *,
        size: float | None = None,
        anchor: str = "middle",
        color: str | None = None,
        bold: bool = False,
    ) -> None:
        """複数行を中央（cy）に縦積みする。"""
        size = size or self.style.font_size
        leading = size * 1.35
        top = cy - (len(lines) - 1) * leading / 2
        for i, line in enumerate(lines):
            # ベースラインは中心から約 0.35em 下
            self.text(
                cx, top + i * leading + size * 0.35, line, size=size, anchor=anchor, color=color, bold=bold
            )

    def finish(self, width: float, height: float) -> SvgResult:
        defs = (
            f'<defs><marker id="{self.arrow_id}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{self.style.stroke}"/></marker></defs>'
        )
        svg = (
            f'<svg id="{self.figure_id}__svg" data-kind="diagram" '
            f'viewBox="0 0 {_n(width)} {_n(height)}" width="{_n(width)}" height="{_n(height)}" '
            f'role="img">{defs}{"".join(self.parts)}{"".join(self._label_parts)}</svg>'
        )
        return SvgResult(svg=svg, width=width, height=height, nodes=dict(self.nodes))


def _n(value: float) -> str:
    """座標の文字列化。決定論のため常に同じ丸め方にする。"""
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"
