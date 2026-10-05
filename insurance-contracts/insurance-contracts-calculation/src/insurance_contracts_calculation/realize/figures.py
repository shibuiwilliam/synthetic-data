"""図（フローチャート・時間軸・判定マトリクス・ツリー・手順）の組立。

`alt` と `facts` は**図の構造から機械的に**作る。図と食い違わせないためである。
図だけに書く規定の根拠は、図のノード単位（`<図のID>__<ノードID>`）を指す。

大きさの上限は本体のコードには書かれていないので、実測した上限を `packs/limits.yaml`
に持ち、ここで超過を弾く（S3-1 の実測結果）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: 実測した実用上限（S3-1。2026-10-03、`nl-a4-2col-mincho` で測定）。
#:
#: 本体の `verify_dataset` は図の大きさを見ない（16 ノードの図でも指摘 0 だった）ので、
#: **ここで止めないと崩れたまま出る**。測り方と結果は `docs/figure_limits.md` に書いた。
#:
#: | 図 | 測定 | 現象 |
#: |---|---|---|
#: | flowchart | 12 ノード（判定 9）まで可、16 ノードで崩れ | 図が段の高さを超え、caption が次の段に離れる |
#: | timeline | 6 区間まで描けるが 5 区間までが読みやすい | 区間が増えるとラベルが小さくなる |
#: | matrix | 7 行 × 5 列まで可 | それ以上は未測定 |
LIMITS = {
    "flowchart_nodes": 12,
    "flowchart_depth": 11,
    "timeline_spans": 5,
    "timeline_events": 5,
    "matrix_rows": 7,
    "matrix_cols": 5,
    "tree_nodes": 12,
    "steps": 5,
    "label_chars": 28,
}


#: 本体 lint L06 が求める最小の複雑さ（`yakkan/lint/rules.py`）。これを下回る図は作らない
MINIMUMS = {
    "flowchart_nodes": 5,
    "timeline_items": 4,
    "matrix_rows": 4,
    "matrix_cols": 3,
    "steps": 4,
    "tree_depth": 3,
}


class FigureTooBig(ValueError):
    """図が実用上限を超えている（描画で崩れるので生成を止める）。"""


class FigureTooSmall(ValueError):
    """図が本体 lint の最小複雑度（L06）に届かない。"""


def _check_min(name: str, n: int) -> None:
    if n < MINIMUMS[name]:
        raise FigureTooSmall(f"{name} が本体 lint の下限 {MINIMUMS[name]} に届かない（{n}）")


def _check(name: str, n: int) -> None:
    if n > LIMITS[name]:
        raise FigureTooBig(f"{name} が実用上限 {LIMITS[name]} を超えている（{n}）")


#: `{term:...}` などのトークン 1 つを、表示したときの見込み字数に置き換えて数える
_TOKEN = re.compile(r"\{[a-z]+:[^}]+\}")


def visible_len(text: str) -> int:
    """描かれたときの字数の見込み（トークンは 7 字として数える）。"""
    return len(_TOKEN.sub("X" * 7, text))


def _check_labels(labels: list[str]) -> None:
    for text in labels:
        n = visible_len(text)
        if n > LIMITS["label_chars"]:
            raise FigureTooBig(f"図のラベルが長すぎる（{n}字）: {text[:20]}…")


# --------------------------------------------------------------- フローチャート
@dataclass
class Decision:
    """判定 1 段。`node_id` は根拠として指せる単位になる。"""

    node_id: str
    question: str
    #: 「はい」のときに支払いへ進むか（False なら「はい」で不払いへ）
    yes_continues: bool = True


@dataclass
class FlowSpec:
    decisions: list[Decision]
    start_label: str
    pay_label: str
    nopay_label: str
    caption: str
    #: 「はい」「いいえ」の文字（図の辺のラベル）
    yes: str = "はい"
    no: str = "いいえ"


def flowchart(fid: str, spec: FlowSpec) -> dict:
    """上から下へ判定を重ね、最後に支払・不払のどちらかに着く図。"""
    _check("flowchart_nodes", len(spec.decisions) + 3)
    _check_min("flowchart_nodes", len(spec.decisions) + 3)
    _check("flowchart_depth", len(spec.decisions) + 2)
    _check_labels([d.question for d in spec.decisions] + [spec.start_label, spec.pay_label, spec.nopay_label])
    nodes = [{"id": "n0", "label": spec.start_label, "shape": "start", "col": 0, "row": 0}]
    pay = f"n{len(spec.decisions) + 1}"
    nopay = f"n{len(spec.decisions) + 2}"
    for i, d in enumerate(spec.decisions, start=1):
        nodes.append({"id": f"n{i}", "label": d.question, "shape": "decision", "col": 0, "row": i})
    nodes.append(
        {"id": pay, "label": spec.pay_label, "shape": "end", "col": 0, "row": len(spec.decisions) + 1}
    )
    nodes.append(
        {"id": nopay, "label": spec.nopay_label, "shape": "end", "col": 1, "row": len(spec.decisions) + 1}
    )
    edges = [{"from": "n0", "to": "n1", "label": None, "style": "solid"}]
    for i, d in enumerate(spec.decisions, start=1):
        nid = f"n{i}"
        nxt = f"n{i + 1}" if i < len(spec.decisions) else pay
        go_on, go_out = (spec.yes, spec.no) if d.yes_continues else (spec.no, spec.yes)
        edges.append({"from": nid, "to": nxt, "label": go_on, "style": "solid"})
        edges.append({"from": nid, "to": nopay, "label": go_out, "style": "dashed"})
    by_id = {n["id"]: n["label"] for n in nodes}
    facts = _flow_facts(spec, by_id, pay, nopay, edges)
    alt = _flow_alt(spec)
    return {
        "type": "figure",
        "id": fid,
        "caption": spec.caption,
        "alt": alt,
        "facts": facts,
        "diagram": {"kind": "flowchart", "direction": "TB", "nodes": nodes, "edges": edges},
        "size": "column",
    }


def _label(spec: FlowSpec, d: Decision) -> str:
    return spec.yes if d.yes_continues else spec.no


def _flow_facts(spec: FlowSpec, by_id, pay, nopay, edges) -> list[str]:
    facts = []
    for e in edges:
        if e.get("label") is None:
            continue
        facts.append(f"「{by_id[e['from']]}」が「{e['label']}」の場合は「{by_id[e['to']]}」に進む。")
    order = "、".join(f"「{_label(spec, d)}」" for d in spec.decisions)
    # 件数（「3つ」など）は書かない。既定の約款の定数の表記とぶつかることがある（本体 lint L11）
    facts.append(f"「{spec.pay_label}」に進むのは、判定が順に{order}となる場合だけである。")
    return facts


def _flow_alt(spec: FlowSpec) -> str:
    qs = "、".join(d.question for d in spec.decisions)
    return (
        f"{spec.caption}の流れを上から下へ示した図。{qs}を順に判定し、"
        f"いずれかが図の分岐に従わない場合は「{spec.nopay_label}」に進む。"
    )


def decision_units(fid: str, spec: FlowSpec) -> list[str]:
    """図の中で根拠として指せる単位（判定の問い）。"""
    return [f"{fid}__n{i}" for i in range(1, len(spec.decisions) + 1)]


# ------------------------------------------------------------------- 時間軸
@dataclass
class Span:
    id: str
    frm: str
    to: str
    label: str
    lane: int = 0


@dataclass
class Event:
    id: str
    at: str
    label: str


@dataclass
class TimelineSpec:
    start: str
    end: str
    ticks: list[str] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    caption: str = ""
    unit: str = "label"


def timeline(fid: str, spec: TimelineSpec) -> dict:
    # 区間の端点が目盛に無いと、本体 lint L06 が「軸の左端に寄せて描かれる」と警告する
    ticks = list(spec.ticks)
    for point in [spec.start, *[s.frm for s in spec.spans], *[s.to for s in spec.spans], spec.end]:
        if point not in ticks:
            ticks.append(point)
    for e in spec.events:
        if e.at not in ticks:
            ticks.append(e.at)
    spec = TimelineSpec(
        start=spec.start,
        end=spec.end,
        ticks=ticks,
        spans=spec.spans,
        events=spec.events,
        caption=spec.caption,
        unit=spec.unit,
    )
    _check("timeline_spans", len(spec.spans))
    _check("timeline_events", len(spec.events))
    _check_min("timeline_items", len(spec.spans) + len(spec.events))
    _check_labels([s.label for s in spec.spans] + [e.label for e in spec.events] + [spec.start, spec.end])
    diagram = {
        "kind": "timeline",
        "unit": spec.unit,
        "axis": {"start": spec.start, "end": spec.end, "ticks": list(spec.ticks)},
        "spans": [
            {"id": s.id, "from": s.frm, "to": s.to, "label": s.label, "lane": s.lane} for s in spec.spans
        ],
        "events": [{"id": e.id, "at": e.at, "label": e.label} for e in spec.events],
    }
    facts = [f"「{s.label}」は{s.frm}から{s.to}までの区間である。" for s in spec.spans]
    facts += [f"「{e.label}」は{e.at}の時点である。" for e in spec.events]
    alt = f"{spec.caption}を{spec.start}から{spec.end}までの時間軸で示した図。" + "".join(
        f"{s.frm}から{s.to}までが{s.label}。" for s in spec.spans
    )
    return {
        "type": "figure",
        "id": fid,
        "caption": spec.caption,
        "alt": alt,
        "facts": facts,
        "diagram": diagram,
        "size": "column",
    }


# --------------------------------------------------------------- 判定マトリクス
@dataclass
class MatrixSpec:
    rows: list[str]
    cols: list[str]
    marks: list[list[str]]
    legend: list[tuple[str, str]]
    caption: str
    row_title: str = ""
    col_title: str = ""


def matrix(fid: str, spec: MatrixSpec) -> dict:
    _check("matrix_rows", len(spec.rows))
    _check("matrix_cols", len(spec.cols))
    _check_min("matrix_rows", len(spec.rows))
    _check_min("matrix_cols", len(spec.cols))
    _check_labels(spec.rows + spec.cols)
    if len(spec.marks) != len(spec.rows) or any(len(r) != len(spec.cols) for r in spec.marks):
        raise ValueError("判定マトリクスの印の数が行列と合わない")
    legend = dict(spec.legend)
    facts = [
        f"{spec.row_title or '行'}が「{r}」で{spec.col_title or '列'}が「{c}」のときは"
        f"{legend.get(spec.marks[i][j], spec.marks[i][j])}。"
        for i, r in enumerate(spec.rows)
        for j, c in enumerate(spec.cols)
    ]
    alt = (
        f"{spec.caption}を、{spec.row_title or '行'}{len(spec.rows)}通り×"
        f"{spec.col_title or '列'}{len(spec.cols)}通りの表の形で示した図。"
        + "".join(f"{m}は{meaning}。" for m, meaning in spec.legend)
    )
    return {
        "type": "figure",
        "id": fid,
        "caption": spec.caption,
        "alt": alt,
        "facts": facts,
        "diagram": {
            "kind": "matrix",
            "rows": list(spec.rows),
            "cols": list(spec.cols),
            "marks": [list(r) for r in spec.marks],
            "legend": [{"mark": m, "meaning": meaning} for m, meaning in spec.legend],
        },
        "size": "column",
    }


def matrix_units(fid: str, spec: MatrixSpec) -> list[str]:
    """マトリクスで根拠として指せる単位（`facts` の各行）。"""
    return [f"{fid}__fact{i}" for i in range(len(spec.rows) * len(spec.cols))]
