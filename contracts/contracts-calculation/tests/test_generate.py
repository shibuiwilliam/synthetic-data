"""M2 の常設テスト（CLAUDE.md「変更したら必ず確かめること」）。

- 本体の 20 content すべてから生成し、検証ゲートをすべて通る（G7/G8/G11 は明示 skip）。
- 同じ seed で 2 回生成し、全ファイル（描画物を除く）が一致する。
- 仕様を 1 箇所だけ誤らせた実装が、検査で不合格になる。
- examples/ の基準と一致する（意図した変更なら scripts/update_examples.py で基準を作り直す）。
"""

from __future__ import annotations

import copy
import json
import random
import shutil
import types

import pytest

from contracts_calculation import base_adapter as ba
from contracts_calculation.codegen.python import generate_module
from contracts_calculation.generate import generate_one
from contracts_calculation.spec.interp import eval_rule
from contracts_calculation.spec.model import CalcSpec
from contracts_calculation.verify.gates import _sample_inputs, _to_kwargs, _uses_calendar

OUT = ba.calc_root() / "data" / "_test_run"


@pytest.fixture(scope="session")
def all_results() -> dict:
    if OUT.exists():
        shutil.rmtree(OUT)
    results = {}
    for base in ba.list_v1_base_contents():
        results[base.name] = generate_one(base, calc_seed=1, out_root=OUT, render=False)
    yield results
    shutil.rmtree(OUT, ignore_errors=True)


def test_all_bases_pass_gates(all_results) -> None:
    assert len(all_results) >= 20
    bad = {cid: [g.gate for g in r.gates if not g.passed] for cid, r in all_results.items() if not r.ok}
    assert not bad, bad


def test_skipped_gates_are_explicit(all_results) -> None:
    """全ゲートが実装済みで、skipped が無い（G7・G8 は M3、G11 は M5 で実装）。"""
    r = next(iter(all_results.values()))
    skipped = {g.gate for g in r.gates if g.skipped}
    assert skipped == set()
    real = {g.gate for g in r.gates if not g.skipped}
    assert {"G7", "G8", "G11"} <= real


def test_determinism_same_seed_twice(all_results) -> None:
    out2 = ba.calc_root() / "data" / "_test_run2"
    if out2.exists():
        shutil.rmtree(out2)
    try:
        r2 = generate_one(ba.repo_root() / "content" / "nda-0001", calc_seed=1, out_root=out2, render=False)
        r1 = all_results["nda-0001"]
        for rel in (
            "contract.json",
            "calc/spec.json",
            "calc/answer_key.json",
            "calc/patch.json",
            "calc/manifest.json",
        ):
            b1 = (r1.out_dir / rel).read_bytes()
            b2 = (r2.out_dir / rel).read_bytes()
            assert b1 == b2, f"{rel} が一致しない"
        p1 = min((r1.out_dir / "calc" / "programs").glob("*.py")).read_bytes()
        p2 = min((r2.out_dir / "calc" / "programs").glob("*.py")).read_bytes()
        assert p1 == p2
    finally:
        shutil.rmtree(out2, ignore_errors=True)


def test_broken_implementation_fails(all_results) -> None:
    """仕様の定数を 1 箇所だけ誤らせた実装は、参照インタプリタとの突合で検出される。"""
    r = all_results["nda-0001"]
    spec_dict = json.loads((r.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    broken_dict = copy.deepcopy(spec_dict)
    _name, p = next((k, v) for k, v in broken_dict["params"].items() if v["type"] == "int")
    p["value"] += 1  # 仕様を 1 箇所だけ壊す
    spec = CalcSpec.from_dict(spec_dict)
    broken = CalcSpec.from_dict(broken_dict)
    src = generate_module(broken)
    mod = types.ModuleType("broken")
    exec(compile(src, "<broken>", "exec"), mod.__dict__)  # noqa: S102 — 生成した正解プログラムの検査に必要
    detected = False
    for rule in spec.rules:
        fn = getattr(mod, rule.function)
        rng = random.Random(7)
        for _ in range(50):
            inputs = _sample_inputs(rule, rng)
            kwargs = _to_kwargs(rule, inputs)
            if _uses_calendar(rule):
                kwargs["holidays"] = frozenset()
            if fn(**kwargs) != eval_rule(spec, rule, dict(inputs)):
                detected = True
                break
        if detected:
            break
    assert detected, "壊した実装が検出されない（テストの十分性に問題がある）"


def test_matches_examples(all_results) -> None:
    """examples/ の基準と一致する（描画に依存しないファイルのみ）。"""
    examples = ba.calc_root() / "examples"
    if not examples.exists():
        pytest.skip("examples/ が未作成（scripts/update_examples.py で作る）")
    for ex_dir in sorted(examples.iterdir()):
        cid = ex_dir.name
        base = cid.replace("-01", "-00", 1)
        r = all_results[base]
        for path in sorted(ex_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ex_dir)
            got = (r.out_dir / rel).read_bytes()
            assert got == path.read_bytes(), f"{cid}/{rel} が examples と一致しない"


def test_render_smoke(all_results) -> None:
    """1 文書だけ PDF 描画まで通す（全文書の描画は CLI の全量生成で行う）。"""
    out = ba.calc_root() / "data" / "_test_render"
    if out.exists():
        shutil.rmtree(out)
    try:
        r = generate_one(ba.repo_root() / "content" / "ots-0001", calc_seed=1, out_root=out, render=True)
        assert r.ok
        assert list(r.out_dir.glob("*.pdf")), "PDF が出ていない"
    finally:
        shutil.rmtree(out, ignore_errors=True)
