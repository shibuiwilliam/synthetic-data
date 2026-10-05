"""challenge モード（DESIGN.md §9.3）。通常モードの正しさを壊さないことを固定する。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import BASE_CONTENT, needs_base

from insurance_contracts_calculation.config import Settings
from insurance_contracts_calculation.generate import generate


def _gen(out: Path, seed: int, challenge: bool):
    return generate(
        BASE_CONTENT, out, seed, Settings.of("standard", render=False, png=False, challenge=challenge)
    )


@needs_base
def test_normal_mode_has_no_traps(tmp_path: Path) -> None:
    """通常モードの文書に難所が混ざらない。"""
    for seed in (1, 2, 3):
        m = _gen(tmp_path / f"n{seed}", seed, False).manifest
        assert m["challenge"] == []
        answer = json.loads(
            (tmp_path / f"n{seed}" / m["content_id"] / "calc" / "answer_key.json").read_text("utf-8")
        )
        assert not [a for a in answer if "trap" in a]


@needs_base
@pytest.mark.parametrize("seed", [2, 3, 4])
def test_challenge_mode_labels_what_it_hid(tmp_path: Path, seed: int) -> None:
    """難所にはラベルが付き、何を指摘できれば正解かが書いてある。"""
    result = _gen(tmp_path, seed, True)
    traps = result.manifest["challenge"]
    assert traps, "challenge モードなのに難所が 1 つも入っていない"
    answer = json.loads((result.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    labelled = {a["rule"]: a["trap"] for a in answer if "trap" in a}
    for tr in traps:
        assert tr["rule"] in labelled
        assert labelled[tr["rule"]]["expect"]


@needs_base
def test_challenge_cases_do_not_depend_on_the_reading(tmp_path: Path) -> None:
    """欠落を入れたルールのテストは、2 通りの読みで同じ結果になるケースだけを使う。"""
    from insurance_contracts_calculation.core.docindex import Doc
    from insurance_contracts_calculation.spec import interp
    from insurance_contracts_calculation.spec.validate import RuleSet
    from insurance_contracts_calculation.testgen import mutation

    result = _gen(tmp_path, 2, True)
    traps = [t for t in result.manifest["challenge"] if t["kind"] == "omission"]
    assert traps
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    spec = json.loads((result.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    rs = RuleSet(spec, Doc.from_dict(policy))
    cases = [
        json.loads(line)
        for line in (result.out_dir / "calc" / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    for tr in traps:
        alt = next(
            (e for name, e in mutation.mutants(rs, tr["rule"]) if "端数処理" in name or "→gt" in name), None
        )
        if alt is None:
            continue
        base = rs.full_expr(tr["rule"])
        for c in cases:
            if c["rule_id"] != tr["rule"] or c["kind"] == "example":
                continue
            got = interp._ev(rs, base, c["inputs"], None)
            assert got == interp._ev(rs, alt, c["inputs"], None), f"{c['case_id']} は読みによって結果が変わる"


@needs_base
def test_purpose_index_gets_a_row(tmp_path: Path) -> None:
    """足した条が目的別もくじに載り、`{ref:}` が解決する（S3-5）。"""
    result = _gen(tmp_path, 1, False)
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    table = policy["front_matter"].get("purpose_index")
    if table is None:
        pytest.skip("この文書には目的別もくじが無い")
    # もくじが指すのは「読む条」。特約に置いたルールは特約の中の条を指す
    spec = json.loads((result.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    sources = {s["unit"] for r in spec["rules"] for s in r["sources"]}
    refs = {c["text"] for row in table["grid"] for c in row if c.get("text", "").startswith("{ref:")}
    assert refs, "目的別もくじに行が足されていない"
    for ref in refs:
        nid = ref[len("{ref:") : -1]
        if not any(s.startswith(nid) for s in sources):
            continue
        assert nid in result.manifest["added"]["nodes"] or any(s.startswith(nid) for s in sources), (
            f"{nid} は足した条ではない"
        )
    plain = policy["derived"]["plain_text"]
    last = table["grid"][-1][-1]["id"]
    assert "{ref:" not in plain[last]["without_label"]
