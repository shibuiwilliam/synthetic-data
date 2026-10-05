"""DESIGN 完全化の常設テスト：頭書分離（add_header_row）・challenge 矛盾・bind_only。"""

from __future__ import annotations

import copy
import json
import shutil

import pytest

from contracts_calculation import base_adapter as ba
from contracts_calculation.generate import generate_one
from contracts_calculation.spec.interp import eval_rule
from contracts_calculation.spec.model import CalcSpec

OUT = ba.calc_root() / "data" / "_test_m7"


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    if OUT.exists():
        shutil.rmtree(OUT)
    yield
    shutil.rmtree(OUT, ignore_errors=True)


def test_header_sheet_placement_on_head_matter_docs() -> None:
    """頭書を持つ文書（lea・pur）では、hard プロファイルで定数が頭書の項目に分離される。"""
    found = 0
    for base in ("lea-0001", "lea-0002", "pur-0001", "pur-0002"):
        r = generate_one(ba.repo_root() / "content" / base, 1, OUT / "head", profile="hard", render=False)
        assert r.ok, (base, [g.gate for g in r.gates if not g.passed])
        ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
        for a in ak:
            header_params = [n for n, loc in a.get("value_locations", {}).items() if loc == "header_sheet"]
            if not header_params:
                continue
            found += 1
            # 値の単位は頭書の項目（head_i*/head_s* の段落）で、仕様の根拠もそこを指す
            spec = json.loads((r.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
            for name in header_params:
                unit = spec["params"][name]["source"]["unit"]
                assert unit.startswith("head_"), (base, name, unit)
                assert unit in a["units"], "頭書の単位が正解表の units に入っていない"
    assert found >= 2, "頭書分離が一度も起きなかった（重みの変更時はテストを見直す）"


def test_contradiction_challenge() -> None:
    """矛盾（本文と別紙の単価が食い違い、優先順位の条項が無い）の challenge。

    - 正解表にラベルが付く。
    - ケースは「どちらの読みでも同じ結果」のものだけが残る。
    - 優先順位の文は本文から消えている。
    """
    r = generate_one(
        ba.repo_root() / "content" / "ots-0001", 2, OUT / "conflict", profile="challenge", render=False
    )
    assert r.ok, [g.gate for g in r.gates if not g.passed]
    manifest = json.loads((r.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))
    ch = manifest.get("challenge")
    assert ch and ch["type"] == "contradiction", ch
    spec_dict = json.loads((r.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    rule_dict = next(x for x in spec_dict["rules"] if x["id"] == ch["rule"])
    assert rule_dict["challenge"]["aspect"] == "value_conflict"
    # 優先順位の文が本文に無い
    contract = json.loads((r.out_dir / "contract.json").read_text(encoding="utf-8"))
    plain = json.dumps(contract.get("derived", {}).get("plain_text", {}), ensure_ascii=False)
    assert "別紙の定めによる" not in plain
    # どちらの読みでも同じ結果になるケースだけが残っている
    body_param = rule_dict["challenge"]["body_param"]
    table = rule_dict["challenge"]["conflict_table"]
    variant_dict = copy.deepcopy(spec_dict)
    for row in variant_dict["tables"][table]["rows"]:
        row["value"] = spec_dict["params"][body_param]["value"]
    base_spec = CalcSpec.from_dict(spec_dict)
    variant = CalcSpec.from_dict(variant_dict)
    fn = rule_dict["interface"]["function"]
    for line in (r.out_dir / "calc" / "cases.jsonl").open(encoding="utf-8"):
        c = json.loads(line)
        if c["function"] != fn or c["kind"] == "unknown":
            continue
        a = eval_rule(base_spec, base_spec.rule(ch["rule"]), dict(c["inputs"]))
        b = eval_rule(variant, variant.rule(ch["rule"]), dict(c["inputs"]))
        assert a == b == c["expected"], f"{c['case_id']} が読みに依存している"


def test_bind_only_pack() -> None:
    """bind_only は追加せず、content_id を変えず、bound ルールだけの計算パックを出す。"""
    r = generate_one(ba.repo_root() / "content" / "ots-0001", 1, OUT / "bind", render=False, bind_only=True)
    assert r.ok and r.content_id == "ots-0001"
    ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    assert ak and all(a["origin"] == "bound" for a in ak)
    patch = json.loads((r.out_dir / "calc" / "patch.json").read_text(encoding="utf-8"))
    assert patch["ops"] == [], "bind_only なのに追加操作がある"
    # 契約書の中身が base と同一（derived を除いた内容が変わっていない）
    base_src = json.loads(
        (ba.repo_root() / "content" / "ots-0001" / "source.json").read_text(encoding="utf-8")
    )
    out_src = json.loads((r.out_dir / "contract.json").read_text(encoding="utf-8"))
    for key in ("meta", "body", "appendices", "defined_terms"):
        assert base_src[key] == out_src[key], f"bind_only で {key} が変わっている"
