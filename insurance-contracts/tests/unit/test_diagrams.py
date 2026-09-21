"""図の SVG 化（docs/rendering.md §6.7）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from yakkan.models import Figure
from yakkan.render.diagrams import DiagramStyle, render_diagram
from yakkan.render.diagrams.base import char_width, text_width, wrap_text

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "diagrams"
KINDS = ("flowchart", "tree", "steps", "timeline", "annotated_mock", "matrix")


def load(kind: str) -> Figure:
    path = FIXTURES / f"{kind}.json"
    return Figure.model_validate(json.loads(path.read_text(encoding="utf-8")))


def style() -> DiagramStyle:
    return DiagramStyle()


def test_文字幅の見積り() -> None:
    assert char_width("あ") == 1.0
    assert char_width("漢") == 1.0
    assert char_width("①") == 1.0
    assert char_width("A") == 0.55
    assert char_width("ｱ") == 0.5
    assert text_width("あA", 10) == pytest.approx(15.5)


def test_折返し() -> None:
    assert wrap_text("あいうえお", 30, 10) == ["あいう", "えお"]
    assert wrap_text("改行\nあり", 100, 10) == ["改行", "あり"]
    assert wrap_text("", 100, 10) == [""]


@pytest.mark.parametrize("kind", KINDS)
def test_6種すべて描画できる(kind: str) -> None:
    figure = load(kind)
    result = render_diagram(figure.diagram, style(), figure.id)
    assert result.svg.startswith("<svg")
    assert result.svg.endswith("</svg>")
    assert result.width > 0 and result.height > 0
    assert result.nodes, "figure_layout（ノード bbox）が空"


@pytest.mark.parametrize("kind", KINDS)
def test_textには必ずfont_familyとfont_sizeがある(kind: str) -> None:
    """無指定だと同梱外フォントに化ける（docs/gotchas.md）。"""
    figure = load(kind)
    svg = render_diagram(figure.diagram, style(), figure.id).svg
    for tag in re.findall(r"<text\b[^>]*>", svg):
        assert "font-family=" in tag, tag
        assert "font-size=" in tag, tag


@pytest.mark.parametrize("kind", KINDS)
def test_ノードbboxがviewBoxに収まる(kind: str) -> None:
    figure = load(kind)
    result = render_diagram(figure.diagram, style(), figure.id)
    for node_id, (x0, y0, x1, y1) in result.nodes.items():
        assert x0 < x1 and y0 < y1, f"{node_id}: bbox が潰れている"
        assert x0 >= -1 and x1 <= result.width + 1, f"{node_id}: 横にはみ出している"
        assert y0 >= -1 and y1 <= result.height + 1, f"{node_id}: 縦にはみ出している"


@pytest.mark.parametrize("kind", KINDS)
def test_決定論_2回描画して同じSVGになる(kind: str) -> None:
    figure = load(kind)
    first = render_diagram(figure.diagram, style(), figure.id)
    second = render_diagram(figure.diagram, style(), figure.id)
    assert first.svg == second.svg
    assert first.nodes == second.nodes


def test_矢頭マーカーのidは図ごとに分かれる() -> None:
    """1 つの HTML に複数の SVG が入るので id が衝突してはいけない。"""
    figure = load("flowchart")
    a = render_diagram(figure.diagram, style(), "fig_a").svg
    b = render_diagram(figure.diagram, style(), "fig_b").svg
    assert 'id="fig_a__arrow"' in a
    assert 'id="fig_b__arrow"' in b
    assert "fig_a__arrow" not in b


def test_flowchartはノードごとにbboxを返す() -> None:
    figure = load("flowchart")
    result = render_diagram(figure.diagram, style(), figure.id)
    assert set(result.nodes) == {n.id for n in figure.diagram.nodes}


def test_matrixはセル単位のbboxを返す() -> None:
    figure = load("matrix")
    result = render_diagram(figure.diagram, style(), figure.id)
    rows, cols = len(figure.diagram.rows), len(figure.diagram.cols)
    assert "cell0_0" in result.nodes
    assert f"cell{rows - 1}_{cols - 1}" in result.nodes
    assert len(result.nodes) == rows * cols + rows + cols


def test_装飾を入れない() -> None:
    """実物の約款図に無い装飾（影・グラデーション）を使っていないこと。"""
    for kind in KINDS:
        figure = load(kind)
        svg = render_diagram(figure.diagram, style(), figure.id).svg
        for banned in ("filter=", "linearGradient", "radialGradient", "drop-shadow", "opacity="):
            assert banned not in svg, f"{kind}: {banned} を使っている"
