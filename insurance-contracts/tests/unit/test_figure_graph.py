"""図の正規化グラフ（docs/eval_dataset_plan.md P1）。"""

from __future__ import annotations

from yakkan.figure_graph import build_graph, graph_paths
from yakkan.models import Figure


def _figure(diagram: dict) -> Figure:
    return Figure.model_validate({"id": "fig_x", "alt": "説明", "facts": ["事実"], "diagram": diagram})


def test_flowchartは宣言したedgesをそのまま使う() -> None:
    graph = build_graph(
        _figure(
            {
                "kind": "flowchart",
                "nodes": [
                    {"id": "a", "label": "受付", "shape": "start", "col": 0, "row": 0},
                    {"id": "b", "label": "審査", "shape": "process", "col": 0, "row": 1},
                    {"id": "c", "label": "支払", "shape": "end", "col": 0, "row": 2},
                ],
                "edges": [{"from": "a", "to": "b"}, {"from": "b", "to": "c"}],
            }
        )
    )
    assert [n.label for n in graph.nodes] == ["受付", "審査", "支払"]
    assert [e.relation for e in graph.edges] == ["flow", "flow"]
    assert graph_paths(graph) == [["受付", "審査", "支払"]]


def test_treeは親から子への辺になる() -> None:
    graph = build_graph(
        _figure(
            {
                "kind": "tree",
                "root": {
                    "id": "r",
                    "label": "約款",
                    "children": [{"id": "c1", "label": "補償条項"}, {"id": "c2", "label": "基本条項"}],
                },
            }
        )
    )
    assert {e.relation for e in graph.edges} == {"child"}
    assert graph_paths(graph) == [["約款", "補償条項"], ["約款", "基本条項"]]


def test_stepsは順番の辺になり詳細は経路に混ざらない() -> None:
    graph = build_graph(
        _figure(
            {
                "kind": "steps",
                "steps": [
                    {"id": "s1", "title": "連絡", "detail": ["すぐに"]},
                    {"id": "s2", "title": "提出"},
                ],
            }
        )
    )
    assert graph_paths(graph) == [["連絡", "提出"]], "detail は経路に入れない"
    assert any(n.role == "detail" for n in graph.nodes), "detail はノードとしては持つ"


def test_timelineは目盛の鎖と区間の端点を持つ() -> None:
    graph = build_graph(
        _figure(
            {
                "kind": "timeline",
                "axis": {"start": "始期", "end": "満期", "ticks": ["始期", "中間", "満期"]},
                "spans": [{"id": "sp", "from": "始期", "to": "中間", "label": "待機"}],
                "events": [{"id": "ev", "at": "満期", "label": "終了"}],
            }
        )
    )
    assert graph_paths(graph) == [["始期", "中間", "満期"]]
    relations = {e.relation for e in graph.edges}
    assert {"next", "from", "to", "at"} <= relations


def test_matrixは行からセルを経て列に至る() -> None:
    graph = build_graph(
        _figure(
            {
                "kind": "matrix",
                "rows": ["Ａ型", "Ｂ型"],
                "cols": ["対人", "対物"],
                "marks": [["○", "×"], ["○", "○"]],
                "legend": [{"mark": "○", "meaning": "対象"}],
            }
        )
    )
    paths = graph_paths(graph)
    assert ["Ａ型", "○", "対人"] in paths
    assert len(paths) == 4, "行 × 列のセルぶん"


def test_全種でpathsが空にならない() -> None:
    """flowchart にしか経路が無い状態を防ぐ（P1 の動機）。"""
    diagrams = [
        {
            "kind": "annotated_mock",
            "subject": "policy_certificate",
            "fields": [{"id": "f1", "badge": 1, "label": "証券番号", "x": 0, "y": 0, "w": 1, "h": 1}],
            "legend": [{"badge": 1, "title": "証券番号とは", "text": "説明"}],
        },
    ]
    for diagram in diagrams:
        assert graph_paths(build_graph(_figure(diagram))), diagram["kind"]
