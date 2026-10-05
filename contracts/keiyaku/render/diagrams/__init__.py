"""Diagram → SVG（docs/rendering.md §6.7）。

`render_diagram()` が種別ごとのモジュールへ振り分け、SVG 文字列と
`figure_layout`（ノード id → viewBox 内 bbox）を返す。
"""

from __future__ import annotations

from keiyaku.models import Diagram
from keiyaku.render.diagrams import flowchart, matrix, mock, steps, timeline, tree
from keiyaku.render.diagrams.base import Box, DiagramStyle, SvgResult

__all__ = ["Box", "DiagramStyle", "SvgResult", "render_diagram"]

_RENDERERS = {
    "flowchart": flowchart.render,
    "tree": tree.render,
    "steps": steps.render,
    "timeline": timeline.render,
    "annotated_mock": mock.render,
    "matrix": matrix.render,
}


def render_diagram(diagram: Diagram, style: DiagramStyle, figure_id: str) -> SvgResult:
    renderer = _RENDERERS.get(diagram.kind)
    if renderer is None:  # pragma: no cover - Literal で守られている
        raise ValueError(f"未対応の図種別: {diagram.kind}")
    return renderer(diagram, style, figure_id)
