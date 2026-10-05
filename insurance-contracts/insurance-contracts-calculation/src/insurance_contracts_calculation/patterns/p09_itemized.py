"""P09 明細の集計。`min(Σ min(損害ᵢ, 種類別限度) − D, L)`（付表と文）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import ITEM, LIT, P, PatternBase, RuleDraft, S, StepDraft, op


class P09Itemized(PatternBase):
    id = "P09"
    title = "明細の集計"
    needs_inputs = ("items",)
    needs_params = ("deductible", "limit", "sub_limit")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        from ..core.packs import concepts

        spec = subject.inputs["items"]
        concept = concepts()[spec["concept"]]
        coll_name = spec.get("arg", "items")
        item_field = concept.arg
        max_items = 4
        per_item = self.const(ctx, subject, "sub_limit", rng)
        ded = self.const(ctx, subject, "deductible", rng, below=per_item.value)
        # 限度額は「明細を上限まで積んでも届かない額」にしない。届かない限度は規定として空振りし、
        # 取り違えても結果が変わらない（G7 の変異が残る）。
        reachable = max_items * per_item.value - ded.value
        limit = self.const(ctx, subject, "limit", rng, above=per_item.value, below=reachable)
        fn = self.func(subject, "payout")
        item_phrase = ctx.resolve_tokens(spec.get("desc") or concept.desc)
        steps = [
            StepDraft(
                "summed",
                op(
                    "agg",
                    op("min", ITEM(item_field), P(per_item.name)),
                    func="sum",
                    over=coll_name,
                ),
                "core",
                {"shape": "aggregate", "item_phrase": item_phrase, "no_formula": True},
            ),
            StepDraft("after_deductible", op("sub", S("summed"), P(ded.name)), "core", {"shape": "sub"}),
            StepDraft("capped", op("min", S("after_deductible"), P(limit.name)), "qualify", {"shape": "cap"}),
            StepDraft(
                fn, op("max", LIT(0), S("capped")), "qualify", {"shape": "floor_zero", "own_paragraph": True}
            ),
        ]
        return [
            RuleDraft(
                pattern=self.id,
                subject_key=subject.key,
                rule_id=self.rule_id(subject, "payout"),
                function=fn,
                title=f"{subject.benefit}の額",
                kind="calculation",
                benefit=subject.benefit,
                trigger=subject.trigger,
                steps=steps,
                inputs={},
                collections={
                    coll_name: {
                        "fields": {item_field: concept.as_input(item_phrase)},
                        "min_items": 0,
                        "max_items": max_items,
                    }
                },
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[per_item, ded, limit],
                obligations=["order:deductible_then_limit", "floor:zero", "limit"],
                properties=[{"type": "range", "min": 0, "max_param": limit.name}],
                example_sets=[],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"itemized": True},
            )
        ]
