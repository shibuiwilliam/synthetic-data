"""表現手段と文型の割当（DESIGN.md §8.4・§9）。

同じルールを、文・算式・表・図のどれで表すかを seed から決める。難易度の主な軸になる。
割合はプロファイル（`config.py`）で指定する。
"""

from __future__ import annotations

import random

from ..patterns.base import RuleDraft

#: 算式にできる手順の形（`realize/discourse.py` と同じ一覧）
FORMULA_SHAPES = ("sub", "sum", "mul", "table_rate", "proration")


def assign(draft: RuleDraft, rng: random.Random, weights: dict[str, float]) -> dict[str, list[str]]:
    """手順ごとの表現手段を決める。返すのは `手順名 → ["prose", "formula", ...]`。"""
    from ..realize.discourse import infer_shape

    out: dict[str, list[str]] = {}
    formula_budget = 1  # 1 条に算式は 1 つまで（段幅に収めるため）
    for step in draft.steps:
        shape = step.hint.get("shape") or infer_shape(step.expr)
        mods = ["prose"]
        if (
            formula_budget > 0
            and step.role == "core"
            and shape in FORMULA_SHAPES
            and not step.hint.get("no_formula")
            and rng.random() < weights.get("formula", 0.5)
        ):
            mods.append("formula")
            formula_budget -= 1
        out[step.name] = mods
    return out


def scatter(draft: RuleDraft, answer_units: list[str]) -> int:
    """根拠単位の散らばり（難易度の軸）。"""
    return len(set(answer_units))


def difficulty_vector(draft: RuleDraft, modalities: dict[str, list[str]], units: list[str]) -> dict:
    """正解表に載せる難易度のベクトル（DESIGN.md §9.1）。"""
    mods = sorted({m for v in modalities.values() for m in v})
    return {
        "modality": "+".join(mods),
        "scatter": len(set(units)),
        "depth": len(draft.steps),
        "figure_only": draft.figure is not None and draft.figure.normative and draft.kind == "decision",
        "table_lookup": draft.table.mode if draft.table else None,
        "boundaries": sum(
            1 for s in draft.steps if (s.hint.get("shape") or "") in ("cap", "case", "decision")
        ),
        "time": any(
            (s.hint.get("shape") or "") in ("deadline", "elapsed", "ceil_period") for s in draft.steps
        ),
        "unknown": any(i["type"] == "bool" for i in draft.inputs.values()),
        "override": any(s.hint.get("override") for s in draft.steps),
        **draft.difficulty,
    }
