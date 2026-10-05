"""P18 待機・不担保期間の判定。日付の比較による支払可否"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from ..realize.figures import Event, Span, TimelineSpec
from .base import FigureDraft, P, PatternBase, RuleDraft, S, StepDraft, V, op


class P18Waiting(PatternBase):
    id = "P18"
    title = "待機期間の判定"
    needs_inputs = ("start_date", "event_date")
    needs_params = ("waiting_days",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        start_arg, start_spec = self.input_of(ctx, subject, "start_date")
        event_arg, event_spec = self.input_of(ctx, subject, "event_date")
        waiting = self.const(ctx, subject, "waiting_days", rng)
        fn = self.func(subject, "eligible")
        steps = [
            StepDraft(
                "elapsed",
                op("days_between", V(start_arg), V(event_arg)),
                "core",
                {"shape": "elapsed", "no_formula": True},
            ),
            StepDraft(
                fn,
                op("ge", S("elapsed"), P(waiting.name)),
                "sentence",
                {
                    "shape": "waiting_rule",
                    "start_phrase": ctx.resolve_tokens(ctx.pack.word("waiting_start", subject)),
                    "label": f"{subject.benefit}を支払うかどうかの判定",
                },
            ),
        ]
        start_phrase = ctx.resolve_tokens(ctx.pack.word("waiting_start", subject))
        timeline = TimelineSpec(
            start=start_phrase,
            end=ctx.pack.word("period_end", subject),
            ticks=[start_phrase, f"{{const:{waiting.name}}}後"],
            spans=[
                Span(
                    "s1", start_phrase, f"{{const:{waiting.name}}}後", ctx.pack.word("waiting_span", subject)
                ),
                Span(
                    "s2",
                    f"{{const:{waiting.name}}}後",
                    ctx.pack.word("period_end", subject),
                    ctx.pack.word("payable_span", subject),
                ),
            ],
            events=[
                Event("e1", start_phrase, ctx.pack.word("waiting_event", subject)),
                Event("e2", f"{{const:{waiting.name}}}後", ctx.pack.word("payable_event", subject)),
            ],
            caption=f"{subject.benefit}の支払の対象となる期間",
        )
        return [
            RuleDraft(
                pattern=self.id,
                subject_key=subject.key,
                rule_id=self.rule_id(subject, "eligible"),
                function=fn,
                title=f"{subject.benefit}の支払の判定",
                kind="decision",
                benefit=subject.benefit,
                trigger=subject.trigger,
                steps=steps,
                inputs={start_arg: start_spec, event_arg: event_spec},
                output={"step": fn, "type": "bool"},
                consts=[waiting],
                obligations=["threshold:ge", "waiting:excluded"],
                properties=[],
                figure=FigureDraft("timeline", timeline, normative=False),
                example_sets=[],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"time": True},
            )
        ]
