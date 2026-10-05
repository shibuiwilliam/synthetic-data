"""evalkit：隔離実行・オラクル満点・壊した提出の不合格・発見の採点（T3.4〜T3.6）。"""

from __future__ import annotations

import json
import shutil

import pytest

from contracts_calculation import base_adapter as ba
from contracts_calculation.evalkit.discovery import score_discovery
from contracts_calculation.evalkit.report import aggregate
from contracts_calculation.evalkit.runner import run_submission
from contracts_calculation.generate import generate_one

OUT = ba.calc_root() / "data" / "_test_eval"


@pytest.fixture(scope="module")
def pack():
    if OUT.exists():
        shutil.rmtree(OUT)
    result = generate_one(ba.repo_root() / "content" / "csl-0001", calc_seed=1, out_root=OUT, render=False)
    assert result.ok
    yield result
    shutil.rmtree(OUT, ignore_errors=True)


def test_oracle_is_perfect(pack) -> None:
    """正解プログラムを提出とみなすと満点（オラクル検査）。"""
    calc = pack.out_dir / "calc"
    module = min((calc / "programs").glob("calc_*.py"))
    rows = run_submission(calc, module)
    assert rows and all(r["ok"] for r in rows), [r for r in rows if not r["ok"]][:3]
    answer_key = json.loads((calc / "answer_key.json").read_text(encoding="utf-8"))
    agg = aggregate({pack.content_id: {"cases": rows, "answer_key": answer_key}})
    assert agg["functions_passed"] == agg["functions_total"] > 0


def test_broken_submission_fails(pack, tmp_path) -> None:
    """定数を 1 箇所壊した提出は不合格になり、採点を緩めない。"""
    calc = pack.out_dir / "calc"
    module = min((calc / "programs").glob("calc_*.py"))
    src = module.read_text(encoding="utf-8")
    import re

    m = re.search(r"^(P_[A-Z0-9_]+) = (\d+)(\s*#.*)$", src, re.MULTILINE)
    assert m, "壊せる整数定数が無い"
    broken = src.replace(m.group(0), f"{m.group(1)} = {int(m.group(2)) + 1}{m.group(3)}", 1)
    sub = tmp_path / f"{pack.content_id}.py"
    sub.write_text(broken, encoding="utf-8")
    rows = run_submission(calc, sub)
    assert any(not r["ok"] for r in rows), "壊した提出が満点になっている"


def test_crashing_submission_is_recorded(pack, tmp_path) -> None:
    sub = tmp_path / "bad.py"
    sub.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    rows = run_submission(pack.out_dir / "calc", sub)
    assert rows and not rows[0]["ok"]


def test_discovery_scoring(pack) -> None:
    answer_key = json.loads((pack.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    perfect = [{"units": a["units"] + a.get("definition_units", [])} for a in answer_key]
    s = score_discovery(perfect, answer_key)
    assert s["precision"] == 1.0 and s["recall"] == 1.0
    partial = [{"units": answer_key[0]["units"][:1]}]
    s2 = score_discovery(partial, answer_key)
    assert s2["precision"] == 1.0 and 0 < s2["recall"] < 1.0
    noisy = [{"units": ["zzz_not_a_unit"]}]
    s3 = score_discovery(noisy, answer_key)
    assert s3["precision"] == 0.0 and s3["recall"] == 0.0
