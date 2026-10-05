"""図（6 種）を **共通の有向グラフ**に落とす（docs/eval_dataset_plan.md P1）。

図の正解は種別ごとに形が違う（flowchart は edges を宣言し、tree は入れ子、
timeline は軸と区間、matrix は行列）。そのままでは読み取り側の予測と機械的に
突き合わせられないので、6 種すべてを `nodes` / `edges` の 1 つの形に正規化する。

- `FigureNode.role` は種別ごとの意味（`start` `process` `decision` … / `tree` /
  `step` / `tick` / `span` / `event` / `field` / `legend` / `row` / `col` / `cell`）。
- `FigureEdge.relation` は関係の種類。**経路（`paths`）を数えるのは `FLOW_RELATIONS` だけ**で、
  補足的な関係（手順の詳細、区間の端点、凡例の対応）は経路に混ぜない。
"""

from __future__ import annotations

from keiyaku.models import Figure, FigureEdge, FigureGraph, FigureNode

#: 経路をたどる関係（入次数 0 → 出次数 0 の道を数える対象）
FLOW_RELATIONS: frozenset[str] = frozenset({"flow", "child", "next", "cell", "explains"})


def build_graph(figure: Figure) -> FigureGraph:
    """図を正規化グラフにする。ノード id は図の中で一意（元の id をそのまま使う）。"""
    diagram = figure.diagram
    nodes: list[FigureNode] = []
    edges: list[FigureEdge] = []

    def node(nid: str, label: str, role: str) -> None:
        nodes.append(FigureNode(id=nid, label=label, role=role))

    def edge(src: str, dst: str, relation: str, label: str | None = None) -> None:
        payload = {"from": src, "to": dst, "relation": relation, "label": label}
        edges.append(FigureEdge.model_validate(payload))

    match diagram.kind:
        case "flowchart":
            for n in diagram.nodes:
                node(n.id, n.label, n.shape)
            for e in diagram.edges:
                edge(e.from_, e.to, "flow", e.label)

        case "tree":
            stack = [(diagram.root, None)]
            while stack:
                current, parent = stack.pop(0)
                node(current.id, current.label, "tree")
                if current.note:
                    note_id = f"{current.id}__note"
                    node(note_id, current.note, "note")
                    edge(current.id, note_id, "note")
                if parent is not None:
                    edge(parent, current.id, "child")
                stack = [(c, current.id) for c in current.children] + stack

        case "steps":
            previous: str | None = None
            for step in diagram.steps:
                node(step.id, step.title, "step")
                if previous is not None:
                    edge(previous, step.id, "next")
                previous = step.id
                for group, role in ((step.detail, "detail"), (step.asks, "ask"), (step.docs, "doc")):
                    for i, line in enumerate(group):
                        sub = f"{step.id}__{role}{i}"
                        node(sub, line, role)
                        edge(step.id, sub, role)

        case "timeline":
            ticks = list(diagram.axis.ticks) or [diagram.axis.start, diagram.axis.end]
            tick_ids: dict[str, str] = {}
            previous = None
            for i, tick in enumerate(ticks):
                tid = f"tick{i}"
                tick_ids[tick] = tid
                node(tid, tick, "tick")
                if previous is not None:
                    edge(previous, tid, "next")
                previous = tid
            for span in diagram.spans:
                node(span.id, span.label, "span")
                for end, relation in ((span.from_, "from"), (span.to, "to")):
                    target = tick_ids.get(str(end))
                    if target:
                        edge(span.id, target, relation)
            for event in diagram.events:
                node(event.id, event.label, "event")
                target = tick_ids.get(str(event.at))
                if target:
                    edge(event.id, target, "at")

        case "annotated_mock":
            legend_by_badge = {legend.badge: legend for legend in diagram.legend}
            for legend in diagram.legend:
                node(f"legend{legend.badge}", legend.title, "legend")
            for field in diagram.fields:
                label = f"{field.label}：{field.value}" if field.value else field.label
                node(field.id, label, "field")
                if field.badge in legend_by_badge:
                    edge(field.id, f"legend{field.badge}", "explains")

        case "matrix":
            for i, row in enumerate(diagram.rows):
                node(f"row{i}", row, "row")
            for j, col in enumerate(diagram.cols):
                node(f"col{j}", col, "col")
            for i, marks in enumerate(diagram.marks):
                for j, mark in enumerate(marks):
                    cell = f"cell{i}_{j}"
                    node(cell, mark, "cell")
                    edge(f"row{i}", cell, "cell")
                    edge(cell, f"col{j}", "cell")
            for legend in diagram.legend:
                node(f"legend_{legend.mark}", f"{legend.mark}：{legend.meaning}", "legend")

    return FigureGraph(nodes=nodes, edges=edges)


def graph_paths(graph: FigureGraph, *, limit: int = 64) -> list[list[str]]:
    """入次数 0 のノードから出次数 0 のノードまでの全経路を、**ラベルの列**で返す。

    数えるのは `FLOW_RELATIONS` の辺だけ。循環は打ち切る。
    経路が `limit` を超える図（組合せが爆発する matrix など）は先頭 `limit` 本で止める。
    """
    labels = {n.id: n.label for n in graph.nodes}
    flow = [e for e in graph.edges if e.relation in FLOW_RELATIONS]
    if not flow:
        return []
    out_edges: dict[str, list[str]] = {}
    indegree: dict[str, int] = {}
    for e in flow:
        out_edges.setdefault(e.from_, []).append(e.to)
        indegree[e.to] = indegree.get(e.to, 0) + 1
        indegree.setdefault(e.from_, indegree.get(e.from_, 0))
    starts = [nid for nid in out_edges if not indegree.get(nid)]
    if not starts:  # すべてのノードに入次数がある（循環）。最初のノードから始める
        starts = [flow[0].from_]

    paths: list[list[str]] = []

    def walk(current: str, seen: tuple[str, ...]) -> None:
        if len(paths) >= limit:
            return
        nexts = [n for n in out_edges.get(current, []) if n not in seen]
        if not nexts:
            paths.append([labels.get(n, n) for n in (*seen, current)])
            return
        for nxt in nexts:
            walk(nxt, (*seen, current))

    for start in starts:
        walk(start, ())
    return paths
