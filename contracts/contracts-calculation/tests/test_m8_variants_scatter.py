"""§9.3 文型の変種と §11.1 分散（営業日の定義条）・definition_units の常設テスト。"""

from __future__ import annotations

import json
import re
import shutil
from random import Random

import pytest

from contracts_calculation import base_adapter as ba
from contracts_calculation.generate import generate_one
from contracts_calculation.patterns.base import sentence_rounding
from contracts_calculation.patterns.registry import by_id
from contracts_calculation.planning.context import Context
from contracts_calculation.verify.gates import OBLIGATION_PHRASES

OUT = ba.calc_root() / "data" / "_test_m8"


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    if OUT.exists():
        shutil.rmtree(OUT)
    yield
    shutil.rmtree(OUT, ignore_errors=True)


def test_rounding_sentence_variants_match_g3_phrases() -> None:
    """変種は同じ意味で、G3 の検査語に両方とも一致する（§9.3）。"""
    pat = re.compile(OBLIGATION_PHRASES["rounding"])
    for rounding in ("floor", "ceil", "half_up"):
        a = sentence_rounding(rounding, "halfwidth", 0)
        b = sentence_rounding(rounding, "halfwidth", 1)
        assert a != b
        assert pat.search(a) and pat.search(b)


def test_variants_change_text_but_not_semantics() -> None:
    """K17 の変種：文面は変わるが、仕様（手順の構造）は変わらない。"""
    ctx = Context.load(ba.repo_root() / "content" / "ots-0001")
    k17 = by_id("K17")
    openings = set()
    step_shapes = set()
    for seed in range(12):
        d = k17.sample(ctx, Random(f"v:{seed}"))
        openings.add(d.paragraphs[0][:40])
        step_shapes.add(json.dumps(d.steps, ensure_ascii=False, sort_keys=True))
    assert len(openings) >= 2, "書き出しの変種が現れない"
    assert len(step_shapes) == 1, "変種が仕様（手順）を変えてしまっている"


def test_scatter_definition_article() -> None:
    """分散：営業日の定義が独立の条に置かれ、definition_units と calendar.source がそこを指す。"""
    r = generate_one(ba.repo_root() / "content" / "dlg-0001", 1, OUT / "sc", profile="standard", render=False)
    assert r.ok
    ak = json.loads((r.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    spec = json.loads((r.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    cal_rules = [a for a in ak if a.get("definition_units")]
    assert cal_rules, "definition_units を持つルールが無い（重みの変更時はテストを見直す）"
    def_unit = cal_rules[0]["definition_units"][0]
    assert spec["calendar"]["source"]["unit"] == def_unit
    contract = json.loads((r.out_dir / "contract.json").read_text(encoding="utf-8"))
    plain = contract["derived"]["plain_text"]
    assert "「営業日」とは" in plain[def_unit]["without_label"]
    # 定義は文書内に 1 回だけ
    hits = [uid for uid, t in plain.items() if "「営業日」とは" in t["without_label"]]
    assert hits == [def_unit]
    # 使う側の条には定義文が無く、difficulty に分散が記録される
    rule = next(x for x in spec["rules"] if x["id"] == cal_rules[0]["rule"])
    assert rule["difficulty"].get("scatter") == 2


def test_no_duplicate_business_day_definition() -> None:
    """営業日を使うルールが複数でも、定義は必ず 1 箇所（二重掲載しない）。"""
    for base, seed in (("dlg-0001", 1), ("csl-0001", 1), ("csl-0002", 1)):
        r = generate_one(
            ba.repo_root() / "content" / base, seed, OUT / f"dup{seed}", profile="hard", render=False
        )
        assert r.ok
        contract = json.loads((r.out_dir / "contract.json").read_text(encoding="utf-8"))
        hits = [
            uid
            for uid, t in contract["derived"]["plain_text"].items()
            if "「営業日」とは" in t["without_label"]
        ]
        assert len(hits) <= 1, (base, hits)
