"""K28 手続の流れ（判定）：図だけに書かれた判定の連鎖（本文は図を参照するだけ）。"""

from __future__ import annotations

from .base import PatternDef, RuleDraft, op, var

_FIG_ID = "fig_expense_flow"


def _figure() -> dict:
    nodes = [
        {"id": "n1", "label": "費用精算の申請", "shape": "start", "col": 0, "row": 0},
        {"id": "n2", "label": "期限内の申請か", "shape": "decision", "col": 0, "row": 1},
        {"id": "n3", "label": "領収書等の添付があるか", "shape": "decision", "col": 0, "row": 2},
        {"id": "n4", "label": "管理者が承認したか", "shape": "decision", "col": 0, "row": 3},
        {"id": "n5", "label": "支払（承認）", "shape": "end", "col": 0, "row": 4},
        {"id": "n6", "label": "差戻し", "shape": "end", "col": 1, "row": 2},
    ]
    edges = [
        {"from": "n1", "to": "n2"},
        {"from": "n2", "to": "n3", "label": "はい"},
        {"from": "n2", "to": "n6", "label": "いいえ"},
        {"from": "n3", "to": "n4", "label": "はい"},
        {"from": "n3", "to": "n6", "label": "いいえ"},
        {"from": "n4", "to": "n5", "label": "はい"},
        {"from": "n4", "to": "n6", "label": "いいえ"},
    ]
    return {
        "type": "figure",
        "id": _FIG_ID,
        "caption": "費用精算の承認の流れ",
        "alt": (
            "費用精算の申請から支払または差戻しまでの流れ図。期限内の申請であること、領収書等の添付が"
            "あること、管理者が承認したことの3つをすべて満たしたときに限り支払（承認）に進み、"
            "いずれかを欠くときは差戻しとなる。"
        ),
        "facts": [
            "期限内の申請でなければ差戻しとなる。",
            "領収書等の添付がなければ差戻しとなる。",
            "管理者が承認しなければ差戻しとなる。",
            "3つの条件をすべて満たしたときに限り支払（承認）となる。",
        ],
        "diagram": {"kind": "flowchart", "nodes": nodes, "edges": edges},
    }


def _sample(ctx, rng) -> RuleDraft:
    return RuleDraft(
        pattern_id="K28",
        rule_id="expense_approved",
        function="expense_approved",
        title="費用の精算",
        kind="determination",
        inputs={
            "submitted_in_time": {"type": "bool", "origin": "fact", "desc": "期限内の申請か"},
            "has_receipts": {"type": "bool", "origin": "fact", "desc": "領収書等の添付があるか"},
            "manager_approved": {"type": "bool", "origin": "judgment", "desc": "管理者が承認したか"},
        },
        steps=[
            {
                "name": "approved",
                "label": "支払（承認）となるか",
                "expr": op("and", var("submitted_in_time"), var("has_receipts"), var("manager_approved")),
            },
        ],
        output={"step": "approved", "type": "bool"},
        obligations=["procedure:figure_normative"],
        paragraphs=[
            f"本件業務に要した費用の精算の承認の可否は、{{ref:{_FIG_ID}}}のとおり判定する。",
        ],
        figure_blocks=[(0, _figure())],
        difficulty={"modality": "figure_only", "condition": "and", "unknown": True},
    )


PATTERN = PatternDef(
    id="K28",
    title="手続の流れ（図だけが規範）",
    genres=frozenset({"outsourcing", "delegation", "consulting", "sysdev"}),
    topics=("費用精算の承認",),
    sampler=_sample,
)
