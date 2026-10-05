"""P12 判定（原則と除外）。`条件 ∧ ¬(除外1 ∨ 除外2 …)`（号の表で列挙する）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from ..realize.figures import MatrixSpec
from .base import EnumerationDraft, FigureDraft, PatternBase, RuleDraft, StepDraft, V, op


class P12Decision(PatternBase):
    id = "P12"
    title = "判定（原則と除外）"
    needs_inputs = ("competition", "doctor")
    needs_params = ()

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        ex1_arg, ex1_spec = self.input_of(ctx, subject, "competition")
        ok_arg, ok_spec = self.input_of(ctx, subject, "doctor")
        fn = self.func(subject, "eligible")
        items = [
            ctx.resolve_tokens(ctx.pack.word("exclusion_competition", subject)),
            ctx.resolve_tokens(ctx.pack.word("exclusion_no_claim", subject)),
        ]
        steps = [
            StepDraft(
                fn,
                op("and", op("not", V(ex1_arg)), V(ok_arg)),
                "decide",
                {"shape": "decision", "label": f"{subject.benefit}を支払うかどうかの判定"},
            )
        ]
        # 変種: 号の表で列挙するか、判定マトリクスで示すか
        use_matrix = rng.random() < 0.5
        yes, no = ctx.pack.word("mark_pay", subject), ctx.pack.word("mark_nopay", subject)
        # 行は「除外に当たるか」、列は「請求の形」。本体 lint L06 は 4 行 3 列以上を求める
        rows = [ctx.pack.word(f"matrix_row{i}", subject) for i in range(1, 5)]
        cols = [ctx.pack.word(f"matrix_col{i}", subject) for i in range(1, 4)]
        excluded = (True, True, False, False)  # 行ごとの「除外に当たるか」
        claimed = (True, False, False)  # 列ごとの「書面による請求があったか」
        matrix = MatrixSpec(
            rows=[ctx.resolve_tokens(r) for r in rows],
            cols=[ctx.resolve_tokens(c) for c in cols],
            marks=[[yes if (not ex and cl) else no for cl in claimed] for ex in excluded],
            legend=[
                (yes, ctx.pack.word("legend_pay", subject)),
                (no, ctx.pack.word("legend_nopay", subject)),
            ],
            caption=f"{subject.benefit}の支払の判定",
            row_title=ctx.resolve_tokens(ctx.pack.word("matrix_row_title", subject)),
            col_title=ctx.resolve_tokens(ctx.pack.word("matrix_col_title", subject)),
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
                inputs={ex1_arg: ex1_spec, ok_arg: ok_spec},
                output={"step": fn, "type": "bool"},
                consts=[],
                obligations=[],
                properties=[],
                enumeration=None
                if use_matrix
                else EnumerationDraft(
                    mode="exclude", items=items, semantic_type="exclusions", item_inputs=[ex1_arg, ok_arg]
                ),
                figure=FigureDraft("matrix", matrix, normative=True) if use_matrix else None,
                example_sets=[],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                group=subject.key,
                difficulty={"figure_only": use_matrix},
            )
        ]
