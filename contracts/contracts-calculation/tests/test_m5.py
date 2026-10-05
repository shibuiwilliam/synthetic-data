"""M5：プロファイル・別紙分離・計算例の箱・図・challenge・datasheet の常設テスト。"""

from __future__ import annotations

import json
import shutil

import pytest

from contracts_calculation import base_adapter as ba
from contracts_calculation.export.datasheet import write_datasheet
from contracts_calculation.generate import generate_one

OUT = ba.calc_root() / "data" / "_test_m5"


def _gen(base: str, profile: str, sub: str):
    return generate_one(
        ba.repo_root() / "content" / base, calc_seed=1, out_root=OUT / sub, profile=profile, render=False
    )


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    if OUT.exists():
        shutil.rmtree(OUT)
    yield
    shutil.rmtree(OUT, ignore_errors=True)


def test_hard_profile_separates_table_to_appendix() -> None:
    """hard では段階表が別紙に分離されうる。分離された文書では別紙 ID が本文から参照される。"""
    found = False
    for base in ("dlg-0002", "ots-0001", "pur-0001", "sys-0002"):
        r = _gen(base, "hard", "hard")
        assert r.ok, [g.gate for g in r.gates if not g.passed]
        ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
        for a in ak:
            if "appendix_table" in a.get("modalities", []):
                found = True
                contract = json.loads((r.out_dir / "contract.json").read_text(encoding="utf-8"))
                appendix_ids = [n["id"] for n in contract.get("appendices", [])]
                assert any(i.startswith("sch") for i in appendix_ids)
    assert found, "hard プロファイルで別紙分離が一度も起きなかった"


def test_example_box_is_verified_by_g5() -> None:
    """計算例の箱を持つルールは、仕様の設例として G5 で検算される。"""
    for base in ("dlg-0001", "csl-0001", "ots-0001"):
        r = _gen(base, "hard", "box")
        assert r.ok
        spec = json.loads((r.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
        ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
        boxed = [a for a in ak if any(u.startswith("box_") for u in a.get("explanatory_units", []))]
        if boxed:
            rule = next(x for x in spec["rules"] if x["id"] == boxed[0]["rule"])
            assert rule.get("examples"), "箱の計算例が仕様の設例として残っていない"
            g5 = next(g for g in r.gates if g.gate == "G5")
            assert "仕様内設例 1 件を検算" in g5.detail
            return
    pytest.skip("箱が一度も選ばれなかった（重みの変更時はテストを見直す）")


def test_challenge_profile_labels_and_cases() -> None:
    r = _gen("ots-0001", "challenge", "challenge")
    assert r.ok
    manifest = json.loads((r.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))
    ch = manifest.get("challenge")
    assert ch, "challenge プロファイルなのに難所が無い"
    ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    labeled = [a for a in ak if a.get("challenge")]
    assert len(labeled) == 1 and labeled[0]["rule"] == ch["rule"]
    if ch["aspect"] == "rounding":
        # 読みが割れないケースだけが残る：floor/ceil で同じ結果になることを抜き取りで確認
        import copy

        from contracts_calculation.spec.interp import eval_rule
        from contracts_calculation.spec.model import CalcSpec

        spec_dict = json.loads((r.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
        cases = [
            json.loads(line)
            for line in (r.out_dir / "calc" / "cases.jsonl").open(encoding="utf-8")
            if json.loads(line)["function"]
            == next(x for x in spec_dict["rules"] if x["id"] == ch["rule"])["interface"]["function"]
        ]
        variant = copy.deepcopy(spec_dict)
        rule_m = next(x for x in variant["rules"] if x["id"] == ch["rule"])

        def flip(e):
            if isinstance(e, dict):
                if e.get("op") in ("muldiv", "round_to"):
                    e["rounding"] = "ceil"
                for a in e.get("args", []):
                    flip(a)

        for st in rule_m["steps"]:
            flip(st["expr"])
        vspec = CalcSpec.from_dict(variant)
        vrule = vspec.rule(ch["rule"])
        for c in cases:
            if c["kind"] == "unknown":
                continue
            got = eval_rule(vspec, vrule, dict(c["inputs"]))
            assert got == c["expected"], f"{c['case_id']} が丸めの読みに依存している"


def test_normal_profiles_have_no_challenge() -> None:
    r = _gen("nda-0001", "standard", "normal")
    assert r.ok
    ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    assert not any(a.get("challenge") for a in ak)
    manifest = json.loads((r.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))
    assert "challenge" not in manifest


def test_basic_profile_keeps_tables_in_body() -> None:
    r = _gen("dlg-0002", "basic", "basic")
    assert r.ok
    ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    assert not any("appendix_table" in a.get("modalities", []) for a in ak)


def test_datasheet_written_from_measurements() -> None:
    _gen("nda-0001", "standard", "sheet")
    out = write_datasheet(OUT / "sheet")
    text = out.read_text(encoding="utf-8")
    assert "文書数: 1" in text and "パターン別のルール数" in text
