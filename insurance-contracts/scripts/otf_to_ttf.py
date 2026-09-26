"""CFF（OpenType/.otf）を TrueType 輪郭（.ttf）に変換する（docs/gotchas.md 2026-09-26）。

WeasyPrint 70.0 が Noto Sans/Serif JP（CFF・`CIDFontType0`埋め込み）を PDF に
埋め込むと、pdfium2・poppler では正しく読めるが、macOS の Quartz/PDFKit
（Preview.app・Quick Look・Safari 内蔵ビューア）では本文が描画されない
（構造上は正しい PDF で、テキスト抽出も往復一致するため lint/verify は通る）。
`CIDFontType2`（TrueType 輪郭）で埋め込まれた IPAex 系フォントでは再現しない。

対処は輪郭形式だけを TrueType に変換すること（フォントの見た目・cmap・hmtx の
advance width は変えない）。Google Fonts チームの `otf2ttf`
（https://github.com/googlefonts/otf2ttf）と同じ手順を fontTools 単体で実装した
（`otf2ttf` パッケージ自体は本環境に無いため、その中核である
`fontTools.pens.cu2quPen.Cu2QuPen` を直接使う）。

使い方：
    uv run python scripts/otf_to_ttf.py assets/fonts/NotoSansJP-Regular.otf
    → assets/fonts/NotoSansJP-Regular.ttf を書き出す（advance width は変更しない）
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f

#: 変換誤差の上限（em 単位）。otf2ttf の既定値と同じ。unitsPerEm=1000 なら 1.0pt 相当。
MAX_ERR_EM = 0.001


def glyphs_to_quadratic(glyph_set: object, units_per_em: int) -> dict[str, object]:
    max_err = units_per_em * MAX_ERR_EM
    quad_glyphs: dict[str, object] = {}
    for name in glyph_set:
        glyph = glyph_set[name]
        pen = TTGlyphPen(glyph_set)
        cu2qu_pen = Cu2QuPen(pen, max_err, reverse_direction=True)
        glyph.draw(cu2qu_pen)
        quad_glyphs[name] = pen.glyph()
    return quad_glyphs


def convert(src: Path, dst: Path) -> None:
    font = TTFont(src)
    if font.sfntVersion != "OTTO" or "CFF " not in font:
        raise ValueError(f"{src} は CFF（OTTO）フォントではない: sfntVersion={font.sfntVersion}")

    glyph_order = font.getGlyphOrder()
    units_per_em = font["head"].unitsPerEm
    glyph_set = font.getGlyphSet()

    # advance width は素通しする（advance width が変わると WeasyPrint の行分割・
    # ページ割りが変わりうる。既存の layout.json / verify の許容誤差 0.5pt を壊さないため、
    # ここだけは絶対に維持する）。
    original_widths = {name: font["hmtx"][name][0] for name in glyph_order}

    quad_glyphs = glyphs_to_quadratic(glyph_set, units_per_em)

    glyf = table__g_l_y_f()
    glyf.glyphOrder = glyph_order
    glyf.glyphs = quad_glyphs
    font["loca"] = newTable("loca")
    font["glyf"] = glyf
    font.setGlyphOrder(glyph_order)
    font["glyf"].compile(font)

    # hmtx: width は元のまま、lsb だけ新しい輪郭の xMin に合わせる（otf2ttf と同じ）。
    hmtx = font["hmtx"]
    for name in glyph_order:
        g = glyf[name]
        lsb = g.xMin if hasattr(g, "xMin") else 0
        hmtx[name] = (original_widths[name], lsb)
        assert hmtx[name][0] == original_widths[name]

    max_points = 0
    max_contours = 0
    for name in glyph_order:
        g = glyf[name]
        if g.numberOfContours > 0:
            max_points = max(max_points, len(g.coordinates))
            max_contours = max(max_contours, g.numberOfContours)
        # cu2quPen/TTGlyphPen produces simple glyphs only（CFF に TrueType 複合グリフの
        # 概念は無い）。numberOfContours<=0（空グリフ）はそのままで良い。

    font["maxp"] = newTable("maxp")
    font["maxp"].tableVersion = 0x00010000
    font["maxp"].numGlyphs = len(glyph_order)
    font["maxp"].maxPoints = max_points
    font["maxp"].maxContours = max_contours
    font["maxp"].maxCompositePoints = 0
    font["maxp"].maxCompositeContours = 0
    font["maxp"].maxZones = 1
    font["maxp"].maxTwilightPoints = 0
    font["maxp"].maxStorage = 0
    font["maxp"].maxFunctionDefs = 0
    font["maxp"].maxInstructionDefs = 0
    font["maxp"].maxStackElements = 0
    font["maxp"].maxSizeOfInstructions = 0
    font["maxp"].maxComponentElements = 0
    font["maxp"].maxComponentDepth = 0
    del font["CFF "]
    if "VORG" in font:
        del font["VORG"]  # CFF 専用（縦書きの原点）。TrueType では使わない
    font.sfntVersion = "\x00\x01\x00\x00"

    dst.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(dst))


def main(argv: list[str]) -> int:
    if not argv:
        print("使い方: otf_to_ttf.py <font1.otf> [font2.otf ...]", file=sys.stderr)
        return 2
    for arg in argv:
        src = Path(arg)
        dst = src.with_suffix(".ttf")
        print(f"{src} -> {dst}")
        convert(src, dst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
