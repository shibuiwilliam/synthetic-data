"""カタログの全パターンが生成できること（M6 DoD）。

出現は抽選に依存するため、ここでは「各パターンが適用できる base で下書きを作れ、
その仕様が validate を通り、interp と生成 Python が一致する」ことをパターン単位で固定する。
"""

from __future__ import annotations

import random
import types
from datetime import date

import pytest

from contracts_calculation import base_adapter as ba
from contracts_calculation.codegen.python import generate_module
from contracts_calculation.patterns.registry import all_patterns
from contracts_calculation.planning.context import Context
from contracts_calculation.spec.interp import eval_rule
from contracts_calculation.spec.model import CalcSpec
from contracts_calculation.spec.validate import validate_spec
from contracts_calculation.verify.gates import _sample_inputs, _to_kwargs, _uses_calendar

_CAL = {
    "weekend": ["SAT", "SUN"],
    "closed": [["12-29", "01-03"]],
    "holidays": "input",
    "source": {"unit": "x", "quote": "営業日"},
}


def _draft_spec(ctx, draft) -> CalcSpec:
    spec_dict = {
        "spec_version": "0.1",
        "document": {"content_id": "coverage", "doctype": ctx.doctype, "calc_seed": 0},
        "calendar": _CAL if draft.needs_calendar else None,
        "params": {n: pd.to_spec({"unit": "x", "quote": pd.surface}) for n, pd in draft.params.items()},
        "tables": {
            n: {
                "kind": "tiers",
                "unit": td.unit,
                "rows": td.to_spec_rows(),
                "source": {"unit": "x", "quote": "x"},
            }
            for n, td in draft.tables.items()
        },
        "rules": [
            {
                "id": draft.rule_id,
                "title": draft.title,
                "kind": draft.kind,
                "origin": "added",
                **({"parties": draft.parties} if draft.parties else {}),
                "interface": {"function": draft.function},
                "inputs": draft.inputs,
                "steps": draft.steps,
                "output": draft.output,
                "obligations": draft.obligations,
            }
        ],
    }
    return CalcSpec.from_dict(spec_dict)


@pytest.fixture(scope="module")
def contexts() -> dict:
    out = {}
    for base in ba.list_base_contents():
        ctx = Context.load(base)
        out.setdefault(ctx.doctype, ctx)
    return out


@pytest.mark.parametrize("pattern", all_patterns(), ids=lambda p: p.id)
def test_every_pattern_generates(contexts, pattern) -> None:
    ctx = next((c for d, c in contexts.items() if d in pattern.genres), None)
    assert ctx is not None, f"{pattern.id}: genres に該当する doctype が無い"
    draft = pattern.sample(ctx, random.Random(f"coverage:{pattern.id}"))
    spec = _draft_spec(ctx, draft)
    issues = validate_spec(spec)
    assert not issues, f"{pattern.id}: " + "; ".join(str(i) for i in issues)
    rule = spec.rules[0]
    mod = types.ModuleType(f"cov_{pattern.id}")
    exec(compile(generate_module(spec), "<cov>", "exec"), mod.__dict__)  # noqa: S102 — 生成コードの検査
    fn = getattr(mod, rule.function)
    rng = random.Random(1)
    base = _sample_inputs(rule, rng)
    for _ in range(30):
        inputs = _sample_inputs(rule, rng)
        kwargs = _to_kwargs(rule, inputs)
        if _uses_calendar(rule):
            kwargs["holidays"] = frozenset()
        assert fn(**kwargs) == eval_rule(spec, rule, dict(inputs)), (pattern.id, inputs)
    # 不明値：入力を 1 つずつ None にしても interp と一致する（三値の意味論）
    for name in rule.inputs:
        inputs = {**base, name: None}
        kwargs = _to_kwargs(rule, inputs)
        if _uses_calendar(rule):
            kwargs["holidays"] = frozenset()
        assert fn(**kwargs) == eval_rule(spec, rule, dict(inputs)), (pattern.id, name)


def test_reviewed_patterns_have_unambiguous_wording_and_edge_semantics(contexts) -> None:
    patterns = {pattern.id: pattern for pattern in all_patterns()}

    def sample(pattern_id: str):
        pattern = patterns[pattern_id]
        ctx = next(c for d, c in contexts.items() if d in pattern.genres)
        return ctx, pattern.sample(ctx, random.Random(f"review:{pattern_id}"))

    ctx05, k05 = sample("K05")
    spec05 = _draft_spec(ctx05, k05)
    assert eval_rule(spec05, spec05.rules[0], {"work_hours": 0}) >= 0
    assert k05.steps[-1]["expr"]["op"] == "max"
    assert any("下回るとき" in paragraph and "円" in paragraph for paragraph in k05.paragraphs)

    _, k10 = sample("K10")
    assert k10.inputs["index_old"]["unit"] == "INDEX"
    assert k10.inputs["index_new"]["unit"] == "INDEX"
    assert "個別契約に定める資材価格指数" in k10.paragraphs[0]

    _, k16 = sample("K16")
    assert "応当する日がない月" in k16.paragraphs[0]

    _, k24 = sample("K24")
    assert "これに該当した当事者" in k24.paragraphs[0]["text"]

    ctx26, k26 = sample("K26")
    spec26 = _draft_spec(ctx26, k26)
    assert (
        eval_rule(
            spec26,
            spec26.rules[0],
            {"force_event": True, "event_date": date(2028, 2, 2), "notice_date": date(2028, 2, 1)},
        )
        is False
    )
