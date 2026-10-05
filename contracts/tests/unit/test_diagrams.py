"""図の SVG 化（docs/rendering.md §6.7）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from keiyaku.models import Figure
from keiyaku.render.diagrams import DiagramStyle, render_diagram
from keiyaku.render.diagrams.base import char_width, text_width, wrap_text

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


def _text_extents(svg: str) -> list[tuple[float, float]]:
    """SVG の `<text>` の描画範囲（左端, 右端）を、アンカーを考慮して求める。"""
    import re

    from keiyaku.render.diagrams.base import text_width

    out = []
    for match in re.finditer(r"<text\b[^>]*>([^<]*)</text>", svg):
        tag, text = match.group(0), match.group(1)
        x = float(re.search(r'\bx="([-\d.]+)"', tag).group(1))
        size = float(re.search(r'font-size="([\d.]+)"', tag).group(1))
        anchor_match = re.search(r'text-anchor="(\w+)"', tag)
        anchor = anchor_match.group(1) if anchor_match else "middle"
        width = text_width(text, size)
        left = x if anchor == "start" else (x - width if anchor == "end" else x - width / 2)
        out.append((left, left + width))
    return out


def test_timelineの軸目盛が長くても枠からはみ出さない():
    """両端の目盛は中央揃えだとラベルの半分が viewBox の外に出て切れていた。"""
    from keiyaku.models import Timeline, TimelineAxis, TimelineSpan
    from keiyaku.render.diagrams.base import DiagramStyle
    from keiyaku.render.diagrams.timeline import WIDTH, render

    labels = ["申込みの受付日", "補償の開始日", "保険期間の満了日"]
    diagram = Timeline(
        axis=TimelineAxis(start=labels[0], end=labels[-1], ticks=labels),
        spans=[TimelineSpan(id="s1", **{"from": labels[0]}, to=labels[-1], label="保険期間", lane=0)],
        events=[],
    )
    svg = render(diagram, DiagramStyle(), "fig_t").svg
    for left, right in _text_extents(svg):
        assert left >= -0.5, f"左にはみ出している: {left}"
        assert right <= WIDTH + 0.5, f"右にはみ出している: {right} > {WIDTH}"


def _polylines(svg: str) -> list[list[tuple[float, float]]]:
    import re

    out = []
    for m in re.finditer(r'<polyline[^>]*points="([^"]+)"', svg):
        out.append([tuple(float(v) for v in p.split(",")) for p in m.group(1).split()])
    return out


def _flowchart(nodes, edges):
    from keiyaku.models import Flowchart

    return Flowchart(
        direction="TB",
        nodes=[{"id": i, "label": lb, "shape": sh, "col": c, "row": r} for i, lb, sh, c, r in nodes],
        edges=edges,
    )


def test_flowchartの戻り経路は他のノードを縦に貫かない() -> None:
    """行を 2 つ以上またぐ経路は、**間の行のノードを真上に貫いて**いた。

    判断のひし形をそのまま通り抜け、あたかもそこへ繋がっているように見えた
    （2026-09-27：更新拒絶の図の「次の期間」の戻り経路）。
    """
    from keiyaku.render.diagrams.base import DiagramStyle
    from keiyaku.render.diagrams.flowchart import render

    diagram = _flowchart(
        [
            ("n1", "起点", "start", 1, 0),
            ("n2", "受付", "process", 1, 1),
            ("n3", "判断", "decision", 1, 2),
            ("n4", "終了", "end", 0, 3),
            ("n5", "更新", "process", 2, 3),
        ],
        [
            {"from": "n1", "to": "n2"},
            {"from": "n2", "to": "n3"},
            {"from": "n3", "to": "n4", "label": "あり"},
            {"from": "n3", "to": "n5", "label": "なし"},
            {"from": "n5", "to": "n2", "label": "次の期間"},
        ],
    )
    result = render(diagram, DiagramStyle(), "fig_r")
    x0, y0, x1, y1 = result.nodes["n3"]
    for points in _polylines(result.svg):
        for (px, py), (qx, qy) in zip(points, points[1:], strict=False):
            if abs(px - qx) > 0.5:  # 横の脚は見ない
                continue
            lo, hi = sorted((py, qy))
            # ひし形は箱より 6px はみ出して描かれるので、端で触れるぶんは許す。
            overlap = min(hi, y1) - max(lo, y0)
            inside = x0 <= px <= x1 and overlap > 8
            assert not inside, f"判断のノードを縦に貫いている: {points}"


def test_flowchartの狭い横エッジのラベルは箱の上へ逃がす() -> None:
    """隣り合う列の間は 18px しかなく、行の中心に置くと両側の箱に重なる。"""
    from keiyaku.render.diagrams.base import DiagramStyle
    from keiyaku.render.diagrams.flowchart import render

    diagram = _flowchart(
        [
            ("n1", "起点", "start", 0, 0),
            ("n2", "左", "process", 0, 1),
            ("n3", "右", "process", 1, 1),
            ("n4", "分岐", "decision", 0, 2),
            ("n5", "終了", "end", 1, 2),
        ],
        [
            {"from": "n1", "to": "n2"},
            {"from": "n3", "to": "n2", "label": "次の期間"},
            {"from": "n2", "to": "n4"},
            {"from": "n4", "to": "n5"},
        ],
    )
    result = render(diagram, DiagramStyle(), "fig_l")
    _, top, _, _ = result.nodes["n2"]
    label_y = [
        float(m) for m in __import__("re").findall(r'<text[^>]*y="([\d.]+)"[^>]*>次の期間<', result.svg)
    ]
    assert label_y, "ラベルが描かれていない"
    assert label_y[0] < top, "ラベルが箱の高さに重なっている"


def test_stepsの小枠の見出しは契約書の言い回し() -> None:
    """約款の「お願い」「書類例」は契約書では使わない（yakkan からの持ち越しだった）。"""
    from keiyaku.render.diagrams.steps import SUB_TITLES

    assert set(SUB_TITLES) == {"detail", "asks", "docs"}
    assert "お願い" not in SUB_TITLES.values()
    assert "書類例" not in SUB_TITLES.values()
