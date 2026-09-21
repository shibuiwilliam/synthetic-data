"""P0 の smoke：A4 2 段組 PDF が生成でき、テキスト層が原文と一致することを確かめる。

macOS では `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が要る（`make check` 経由なら自動）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts import smoke_render  # noqa: E402
from yakkan.layout.extract import Fragment, span_bands  # noqa: E402
from yakkan.verify.normalize import normalize, page_text, read_lines  # noqa: E402

# @page margin: 16mm 14mm 18mm 14mm → ヘッダ/フッタ帯の境界（pt, 1mm = 2.8346pt）
MM = 2.83465
HEADER_BELOW = 16 * MM
FOOTER_ABOVE = 841.89 - 18 * MM
# 段間 8mm。本文領域は左右マージン 14mm を除いた範囲で、その中央に段間がある。
_CONTENT = 595.28 - 2 * 14 * MM
GUTTER = ((595.28 - 8 * MM) / 2, (595.28 + 8 * MM) / 2)
CONTENT_WIDTH = 595.28 - 2 * 14 * MM


def _lines(page, fragments_json: Path):
    """PDF の行を、box ツリー由来の段またぎ帯つきで読み出す。"""
    import json

    frags = [
        Fragment(d["id"], d["box"], d["page"], *d["bbox_pt"]) for d in json.loads(fragments_json.read_text())
    ]
    return read_lines(
        page,
        header_below=HEADER_BELOW,
        footer_above=FOOTER_ABOVE,
        gutter=GUTTER,
        columns=2,
        span_bands=span_bands(frags, page=1, content_width=CONTENT_WIDTH),
    )


@pytest.fixture(scope="module")
def rendered(tmp_path_factory) -> tuple[Path, list[Path]]:
    out = tmp_path_factory.mktemp("smoke")
    return smoke_render.render(out)


def test_1ページに収まる(rendered) -> None:
    pdf_path, pngs = rendered
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        assert len(pdf.pages) == 1
    assert len(pngs) == 1
    assert pngs[0].stat().st_size > 10_000


def test_PNGが150dpiのA4である(rendered) -> None:
    from PIL import Image

    _, pngs = rendered
    with Image.open(pngs[0]) as img:
        # A4 = 595.28 x 841.89pt → 150dpi で 1240 x 1754px（丸めで ±1px）
        assert abs(img.width - 1240) <= 1
        assert abs(img.height - 1754) <= 1


def test_本文のテキスト層が原文と一致する(rendered) -> None:
    """読み順に並べ直した本文に、原文の各文字列がそのまま現れること。"""
    import pdfplumber

    pdf_path, _ = rendered
    with pdfplumber.open(pdf_path) as pdf:
        lines = _lines(pdf.pages[0], pdf_path.parent / "fragments.json")
    body = normalize(page_text(lines, "body"))

    missing = [
        e for e in smoke_render.expected_strings() if e.region == "body" and normalize(e.text) not in body
    ]
    assert not missing, "PDF から読み出せない本文: " + " / ".join(f"{e.id}:{e.text[:24]}" for e in missing)


def test_ヘッダとフッタが本文と区別できる(rendered) -> None:
    import pdfplumber

    pdf_path, _ = rendered
    with pdfplumber.open(pdf_path) as pdf:
        lines = _lines(pdf.pages[0], pdf_path.parent / "fragments.json")
    header = normalize(page_text(lines, "header"))
    footer = normalize(page_text(lines, "footer"))
    assert normalize(smoke_render.CHAPTER) in header
    assert smoke_render.FORM_CODE in footer
    assert "1" in footer  # ページ番号


def test_SVG内の日本語がテキスト層に載る(rendered) -> None:
    """図のラベルが抽出できること（P2 の往復比較では figure 領域として区別する）。"""
    import pdfplumber

    pdf_path, _ = rendered
    with pdfplumber.open(pdf_path) as pdf:
        text = normalize("".join(c["text"] for c in pdf.pages[0].chars))
    for label in smoke_render.SVG_LABELS:
        assert label in text, f"SVG 内テキストが抽出できない: {label}"


def test_フォールバックフォントが混ざっていない(rendered) -> None:
    """同梱フォント以外が使われていたら豆腐・字形差の温床になる（lint L07）。"""
    import pdfplumber

    pdf_path, _ = rendered
    with pdfplumber.open(pdf_path) as pdf:
        fonts = {c["fontname"].split("+")[-1] for c in pdf.pages[0].chars}
    assert fonts <= {"Noto-Serif-JP", "Noto-Sans-JP", "Noto-Sans-JP-Bold"}, f"想定外のフォント: {fonts}"


def test_決定論_2回描画してテキスト層が一致する(tmp_path) -> None:
    import pdfplumber

    texts = []
    for i in range(2):
        pdf_path, _ = smoke_render.render(tmp_path / f"run{i}")
        with pdfplumber.open(pdf_path) as pdf:
            texts.append("".join(c["text"] for c in pdf.pages[0].chars))
    assert texts[0] == texts[1]
