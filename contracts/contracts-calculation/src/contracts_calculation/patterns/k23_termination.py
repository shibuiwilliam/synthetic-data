"""K23 解除権の発生（判定）：無催告事由のいずれか、または違反＋催告＋期間経過＋未是正。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, fw, op, param, step, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K23")
    cure = rng.choice(v["cure_days"])
    ds = ctx.digit_style
    n_cure = ctx.free_const_name("cure_period_days")
    return RuleDraft(
        pattern_id="K23",
        rule_id="may_terminate",
        function="may_terminate",
        title="契約の解除",
        kind="determination",
        params={n_cure: ParamDraft(n_cure, "int", fw(f"{cure}日", ds), value=cure, unit="DAY")},
        inputs={
            "insolvency": {"type": "bool", "origin": "judgment", "desc": "支払停止または支払不能に陥ったか"},
            "attachment": {
                "type": "bool",
                "origin": "judgment",
                "desc": "差押えまたは競売の申立てを受けたか",
            },
            "material_breach": {"type": "bool", "origin": "judgment", "desc": "重大な義務違反があるか"},
            "demanded": {"type": "bool", "origin": "notice", "desc": "書面による催告をしたか"},
            "elapsed_days": {
                "type": "int",
                "unit": "DAY",
                "origin": "fact",
                "min": 0,
                "max": 365,
                "desc": "催告の到達から経過した日数",
            },
            "cured": {"type": "bool", "origin": "judgment", "desc": "違反が是正されたか"},
        },
        steps=[
            {
                "name": "no_demand_event",
                "label": "無催告解除の事由",
                "expr": op("or", var("insolvency"), var("attachment")),
            },
            {
                "name": "demand_route",
                "label": "催告解除の要件",
                "expr": op(
                    "and",
                    var("material_breach"),
                    var("demanded"),
                    op("ge", var("elapsed_days"), param(n_cure)),
                    op("not", var("cured")),
                ),
            },
            {
                "name": "may_terminate",
                "label": "解除できるか",
                "expr": op("or", step("no_demand_event"), step("demand_route")),
            },
        ],
        output={"step": "may_terminate", "type": "bool"},
        obligations=["demand:written", "cure_period:from_arrival"],
        paragraphs=[
            {
                "text": "当事者の一方に次の各号のいずれかに該当する事由が生じたときは、"
                "相手方は、催告をしないで直ちに本契約を解除することができる。",
                "items": ["支払を停止し、または支払不能に陥ったとき", "差押えまたは競売の申立てを受けたとき"],
            },
            (
                f"当事者の一方に本契約上の重大な義務違反があるときは、相手方は、書面により催告し、"
                f"催告が到達した日から{{const:{n_cure}}}を経過してもなお是正されないときに限り、"
                "本契約を解除することができる。"
            ),
        ],
        difficulty={"condition": "items_and_route", "unknown": True},
    )


PATTERN = PatternDef(
    id="K23",
    title="解除権の発生",
    genres=frozenset(
        {
            "outsourcing",
            "delegation",
            "consulting",
            "sysdev",
            "license",
            "lease",
            "purchase",
            "contracting",
            "nda",
            "employment",
        }
    ),
    topics=("解除",),
    sampler=_sample,
)
