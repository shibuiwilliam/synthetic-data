"""図のノード座標を viewBox からページ座標（pt）へ変換する計算（docs/rendering.md §6.8-3）。"""

from __future__ import annotations

from keiyaku.layout.extract import _figure_layouts
from keiyaku.models import ElementFragment, ElementLayout
from keiyaku.render.diagrams.base import SvgResult


def elements(bbox, page=2) -> dict[str, ElementLayout]:
    return {"fig_x__svg": ElementLayout(kind="diagram", fragments=[ElementFragment(page=page, bbox=bbox)])}


def test_縮小なしなら倍率は1でノードは平行移動する() -> None:
    result = SvgResult(svg="", width=200.0, height=100.0, nodes={"n1": (10.0, 20.0, 60.0, 50.0)})
    # svg が 200pt 幅で描かれた ＝ 倍率 1.0
    layouts = _figure_layouts(elements((100.0, 300.0, 300.0, 400.0)), {"fig_x": result})
    figure = layouts["fig_x"]
    assert figure.page == 2
    assert figure.scale == 1.0
    assert figure.nodes["n1"] == (110.0, 320.0, 160.0, 350.0)


def test_CSSで縮小された場合は倍率が効く() -> None:
    result = SvgResult(svg="", width=400.0, height=200.0, nodes={"n1": (0.0, 0.0, 100.0, 50.0)})
    # 400px の図が 200pt に縮んだ ＝ 倍率 0.5
    layouts = _figure_layouts(elements((50.0, 60.0, 250.0, 160.0)), {"fig_x": result})
    figure = layouts["fig_x"]
    assert figure.scale == 0.5
    assert figure.nodes["n1"] == (50.0, 60.0, 100.0, 85.0)


def test_px_pt_換算の実寸_倍率は0_75になる() -> None:
    """viewBox の単位は CSS px。等倍で置くと pt では 0.75 倍になる。"""
    result = SvgResult(svg="", width=312.0, height=396.0, nodes={"n1": (6.0, 6.0, 138.0, 44.0)})
    layouts = _figure_layouts(
        elements((45.0, 100.0, 45.0 + 312.0 * 0.75, 100.0 + 396.0 * 0.75)), {"fig_x": result}
    )
    figure = layouts["fig_x"]
    assert figure.scale == 0.75
    assert figure.nodes["n1"] == (49.5, 104.5, 148.5, 133.0)


def test_svgが描画されていなければ図は出力しない() -> None:
    result = SvgResult(svg="", width=100.0, height=100.0, nodes={"n1": (0.0, 0.0, 10.0, 10.0)})
    assert _figure_layouts({}, {"fig_x": result}) == {}
