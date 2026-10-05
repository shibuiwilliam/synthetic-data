"""codegen：生成した Python が付録Bの設例で正しく、interp と一致する（T1.8・T1.9）。"""

import random
from datetime import date, timedelta

import pytest
from appendix_b_specs import SPECS

from contracts_calculation.codegen.python import generate_module
from contracts_calculation.spec.interp import eval_rule
from contracts_calculation.spec.model import CalcSpec


def _load_module(src: str, name: str):
    import types

    mod = types.ModuleType(name)
    exec(compile(src, f"<generated {name}>", "exec"), mod.__dict__)  # noqa: S102 — 生成した正解プログラムの検査に必要
    return mod


@pytest.fixture(scope="module")
def modules() -> dict:
    out = {}
    for key, raw in SPECS.items():
        spec = CalcSpec.from_dict(raw)
        out[key] = (spec, _load_module(generate_module(spec), f"gen_{key}"))
    return out


def _all_examples():
    for key, raw in SPECS.items():
        spec = CalcSpec.from_dict(raw)
        for rule in spec.rules:
            for i, ex in enumerate(rule.examples):
                yield pytest.param(key, rule.id, i, id=f"{key}:{rule.id}:ex{i}")


@pytest.mark.parametrize("key,rule_id,ex_i", list(_all_examples()))
def test_generated_matches_examples(modules, key, rule_id, ex_i) -> None:
    spec, mod = modules[key]
    rule = spec.rule(rule_id)
    ex = rule.examples[ex_i]
    fn = getattr(mod, rule.function)
    kwargs = _to_kwargs(rule, ex.inputs)
    if _uses_calendar(rule):
        kwargs["holidays"] = frozenset(date.fromisoformat(h) for h in ex.holidays)
    got = fn(**kwargs)
    expect = ex.expect
    if rule.output.get("type") == "date":
        expect = date.fromisoformat(expect)
    assert got == expect


@pytest.mark.parametrize("key", list(SPECS.keys()))
def test_generated_matches_interp_on_random_inputs(modules, key) -> None:
    """宣言した値域からの乱数入力で、参照インタプリタと生成 Python が一致する。"""
    spec, mod = modules[key]
    rng = random.Random(20261003)
    for rule in spec.rules:
        fn = getattr(mod, rule.function)
        for _ in range(50):
            inputs = _sample_inputs(rule, rng)
            kwargs = _to_kwargs(rule, inputs)
            holidays = frozenset()
            if _uses_calendar(rule):
                kwargs["holidays"] = holidays
            assert fn(**kwargs) == eval_rule(spec, rule, dict(inputs), holidays), (rule.id, inputs)


@pytest.mark.parametrize("key", list(SPECS.keys()))
def test_generated_returns_none_on_unknown_input(modules, key) -> None:
    """必須入力を 1 つずつ None にすると None が返る（interp と一致）。"""
    spec, mod = modules[key]
    rng = random.Random(1)
    for rule in spec.rules:
        fn = getattr(mod, rule.function)
        base = _sample_inputs(rule, rng)
        for name, decl in rule.inputs.items():
            if decl.optional:
                continue
            inputs = dict(base)
            inputs[name] = None
            kwargs = _to_kwargs(rule, inputs)
            if _uses_calendar(rule):
                kwargs["holidays"] = frozenset()
            assert fn(**kwargs) is None
            assert eval_rule(spec, rule, dict(inputs)) is None


def test_generated_module_is_deterministic() -> None:
    spec = CalcSpec.from_dict(SPECS["k17"])
    assert generate_module(spec) == generate_module(spec)


def test_generated_module_mentions_sources() -> None:
    spec = CalcSpec.from_dict(SPECS["k17"])
    src = generate_module(spec)
    assert "P_LATE_RATE = (146, 1000)" in src
    assert "年14.6%" in src and "根拠:" in src
    assert "def late_interest(*, " in src


# --- helpers ------------------------------------------------------------------


def _uses_calendar(rule) -> bool:
    from contracts_calculation.codegen.python import _collect_ops
    from contracts_calculation.spec.model import BUSINESS_DAY_OPS

    ops: set[str] = set()
    _collect_ops(rule, ops)
    return bool(ops & BUSINESS_DAY_OPS)


def _to_kwargs(rule, inputs: dict) -> dict:
    out = {}
    for name, decl in rule.inputs.items():
        v = inputs.get(name)
        if v is not None and decl.type == "date":
            v = date.fromisoformat(v) if isinstance(v, str) else v
        out[name] = v
    return out


def _sample_inputs(rule, rng: random.Random) -> dict:
    inputs = {}
    for name, decl in rule.inputs.items():
        if decl.type == "int":
            lo = decl.min if decl.min is not None else 0
            hi = decl.max if decl.max is not None else 1000
            inputs[name] = rng.randint(lo, hi)
        elif decl.type == "bool":
            inputs[name] = rng.choice([True, False])
        elif decl.type == "date":
            lo = date.fromisoformat(decl.min or "2026-01-01")
            hi = date.fromisoformat(decl.max or "2029-12-31")
            span = (hi - lo).days
            inputs[name] = (lo + timedelta(days=rng.randint(0, span))).isoformat()
        elif decl.type == "list":
            inputs[name] = [rng.randint(0, 2_000_000) for _ in range(rng.randint(0, 6))]
        elif decl.type == "enum":
            inputs[name] = rng.choice(list(decl.values))
    return inputs
