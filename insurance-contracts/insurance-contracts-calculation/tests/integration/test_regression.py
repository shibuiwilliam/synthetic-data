"""回帰の基準（`examples/`）と決定性。

「変更したら必ず確かめること」を人手の手順から pytest に移したもの（TASK.md S0-2）。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import BASE_CONTENT, EXAMPLE_DOC, EXAMPLE_SEED, needs_base

from insurance_contracts_calculation.config import Settings
from insurance_contracts_calculation.export.layout import file_hashes

#: 回帰で突き合わせるファイル（PDF・PNG は描画器の版でバイトが変わりうるので外す）
COMPARED = (
    "policy.json",
    "calc/spec.json",
    "calc/patch.json",
    "calc/answer_key.json",
    "calc/cases.jsonl",
    "calc/tasks.jsonl",
    "calc/tasks_H1.jsonl",
    "calc/tasks_H2.jsonl",
)


def _generate(out: Path, seed: int = EXAMPLE_SEED, **kw):
    from insurance_contracts_calculation.generate import generate

    return generate(BASE_CONTENT, out, seed, Settings.of("standard", render=False, png=False, **kw))


@needs_base
def test_baseline_seed_matches_examples(tmp_path: Path) -> None:
    """基準の seed の生成が `examples/` と一致する。"""
    result = _generate(tmp_path)
    assert result.content_id == EXAMPLE_DOC.name
    for rel in COMPARED:
        got = (result.out_dir / rel).read_text(encoding="utf-8")
        want = (EXAMPLE_DOC / rel).read_text(encoding="utf-8")
        assert got == want, f"{rel} が examples/ と違う（意図した変更なら GENERATOR_VERSION を上げる）"
    got_program = next((result.out_dir / "calc" / "programs").glob("*.py")).read_text(encoding="utf-8")
    want_program = next((EXAMPLE_DOC / "calc" / "programs").glob("*.py")).read_text(encoding="utf-8")
    assert got_program == want_program


@needs_base
def test_same_seed_gives_the_same_bytes(tmp_path: Path) -> None:
    """同じ seed で 2 回生成し、ハッシュが一致する（G11）。"""
    a = _generate(tmp_path / "a", 7).out_dir
    b = _generate(tmp_path / "b", 7).out_dir
    ha, hb = file_hashes(a), file_hashes(b)
    assert ha == hb, "同じ seed なのに出力が違う"
    assert ha, "出力が空"


@needs_base
def test_gates_all_pass_on_the_example() -> None:
    manifest = json.loads((EXAMPLE_DOC / "calc" / "manifest.json").read_text(encoding="utf-8"))
    bad = {code: g for code, g in manifest["gates"].items() if not g["ok"]}
    assert not bad, f"examples/ のゲートが通っていない: {bad}"
    assert manifest["gates"]["G7"]["survivors"] == {}, "見分けられない変異が残っている"


def test_the_correct_program_passes_every_case() -> None:
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", str(EXAMPLE_DOC / "calc" / "tests"), "-q"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]


def test_the_wrong_program_is_caught() -> None:
    """わざと誤らせた実装では不合格が出る（出なければテストが誤りを見分けられていない）。"""
    wrong = EXAMPLE_DOC.parent / "wrong_impl.py"
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", str(EXAMPLE_DOC / "calc" / "tests"), "--impl", str(wrong), "-q"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, "誤った実装なのに全件合格している"
    assert "FAILED" in proc.stdout, proc.stdout[-600:]


@needs_base
@pytest.mark.slow
@pytest.mark.parametrize("seed", range(1, 21))
def test_sweep_of_seeds(tmp_path: Path, seed: int) -> None:
    """seed 1〜20 で生成でき、生成したテストが全件合格する。"""
    result = _generate(tmp_path, seed)
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", str(result.out_dir / "calc" / "tests"), "-q"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout[-2000:]
    assert result.manifest["gates"]["G7"]["survivors"] == {}
