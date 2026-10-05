"""K10 価格改定：指数の変動率に連動。改定幅の上限つき。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    concept,
    fw,
    lit,
    op,
    param,
    pct_surface,
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K10")
    cap = rng.choice(v["cap_permille"])
    ds = ctx.digit_style
    n_cap = ctx.free_const_name("reprice_cap")
    return RuleDraft(
        pattern_id="K10",
        rule_id="revised_unit_price",
        function="revised_unit_price",
        title="単価の改定",
        kind="calculation",
        params={n_cap: ParamDraft(n_cap, "int", pct_surface(cap, ds), value=cap, unit="PERMILLE")},
        inputs={
            "unit_price": concept("unit_price"),
            "index_old": concept("index_old"),
            "index_new": concept("index_new"),
        },
        steps=[
            {
                "name": "delta_permille",
                "label": "指数の変動率（千分率）",
                "expr": op(
                    "muldiv",
                    op("sub", var("index_new"), var("index_old")),
                    lit(1000),
                    var("index_old"),
                    rounding="floor",
                ),
            },
            {
                "name": "capped_delta",
                "label": "上限を適用した変動率",
                "expr": op(
                    "min", op("max", step("delta_permille"), op("sub", lit(0), param(n_cap))), param(n_cap)
                ),
            },
            {
                "name": "revised",
                "label": "改定後の単価",
                "expr": op(
                    "muldiv",
                    var("unit_price"),
                    op("add", lit(1000), step("capped_delta")),
                    lit(1000),
                    rounding="floor",
                ),
            },
        ],
        output={"step": "revised", "type": "int", "unit": "JPY"},
        obligations=["index:declared_source", "cap:both_directions", "rounding:floor_1yen"],
        paragraphs=[
            (
                "個別契約に定める単価は、毎年の応当日に、個別契約に定める資材価格指数の変動率に応じて改定する。"
                "変動率は、改定時点の指数から直前の改定時の指数を差し引いた値の、直前の指数に対する割合"
                "（千分率の整数とし、端数は切り捨てる）とする。"
            ),
            (
                f"変動率は、上下とも{{const:{n_cap}}}を限度とする。改定後の単価は、改定前の単価に"
                f"変動率を加味して算出し、{fw('1円', ds)}未満の端数は切り捨てる。"
            ),
        ],
        parties={"payer": ctx.alias(ctx.payer_key), "payee": ctx.alias(ctx.payee_key)},
        difficulty={"depth": 3, "value_location": "order"},
    )


PATTERN = PatternDef(
    id="K10",
    title="価格改定",
    genres=frozenset({"purchase", "contracting"}),
    topics=("価格の改定", "指数"),
    sampler=_sample,
)
