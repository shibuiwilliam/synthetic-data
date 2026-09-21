"""同梱フォントの台帳と cmap 被覆（lint L07 の下地）。"""

from __future__ import annotations

from yakkan.fonts import FONTS, REPRESENTATIVE_CHARS, coverage, font_face_css


def test_全フォントが配置されている() -> None:
    missing = [f.filename for f in FONTS if not f.exists]
    assert not missing, f"assets/fonts に無い: {missing}（SOURCES.md の手順で取得する）"


def test_本文フォントは代表文字をすべて持つ() -> None:
    body_fonts = [f for f in FONTS if "Symbols" not in f.family]
    for spec in body_fonts:
        cov = coverage(spec)
        missing = [c for c, ok in cov.items() if not ok]
        assert not missing, f"{spec.family} に無い文字: {missing}"


def test_代表文字はいずれかのフォントに存在する() -> None:
    covered = {c: False for c in REPRESENTATIVE_CHARS}
    for spec in FONTS:
        for c, ok in coverage(spec).items():
            covered[c] = covered[c] or ok
    assert all(covered.values()), f"どのフォントにも無い: {[c for c, v in covered.items() if not v]}"


def test_font_face_cssがfileスキームで参照する() -> None:
    css = font_face_css()
    assert css.count("@font-face") == len(FONTS)
    assert "file://" in css
