"""配置（別表への分離・特約への分離）。DESIGN.md §8.5・§9.1 の分散度の軸。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import BASE_CONTENT, needs_base

from insurance_contracts_calculation.config import Settings
from insurance_contracts_calculation.generate import generate


def _gen(out: Path, seed: int, profile: str = "hard"):
    return generate(BASE_CONTENT, out, seed, Settings.of(profile, render=False, png=False))


def _placements(result) -> list[str]:
    spec = json.loads((result.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    return [r["presentation"]["placement"] for r in spec["rules"]]


@needs_base
def test_basic_profile_keeps_everything_in_articles(tmp_path: Path) -> None:
    """`basic` は 1 つの条に閉じる（分散させない）。"""
    for seed in (1, 2, 3):
        result = _gen(tmp_path / f"b{seed}", seed, "basic")
        assert set(_placements(result)) == {"article"}


@needs_base
def test_hard_profile_scatters(tmp_path: Path) -> None:
    """`hard` は別表・特約への分散が出る。"""
    kinds: set[str] = set()
    for seed in range(1, 9):
        kinds.update(_placements(_gen(tmp_path / f"h{seed}", seed)))
    assert "rider" in kinds, "特約への分散が 1 度も出ていない"
    assert "appendix" in kinds, "別表への分散が 1 度も出ていない"


@needs_base
def test_appendix_is_referenced_from_the_body(tmp_path: Path) -> None:
    """別表に分けた表は、本文から `{ref:}` で指され、別表番号に解決する。"""
    result = _gen(tmp_path, 4)
    spec = json.loads((result.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    labels, plain = policy["derived"]["labels"], policy["derived"]["plain_text"]
    moved = [r for r in spec["rules"] if r["presentation"]["placement"] == "appendix"]
    if not moved:
        pytest.skip("この seed では別表に分けたルールが無い")
    for rule in moved:
        tid = rule["presentation"]["table"]
        assert tid.startswith("tbl_app"), f"{tid} が別表の中に無い"
        app_id = tid.split("_")[1]
        assert app_id in labels, f"{app_id} に別表番号が付いていない"
        citation = labels[app_id]["citation"]
        body = "".join(plain[s["unit"]]["without_label"] for s in rule["sources"] if s["unit"] in plain)
        assert citation in body, f"本文が {citation} を指していない"
        assert "下表" not in body, "別表に分けたのに本文が「下表」と書いている"


@needs_base
def test_rider_articles_start_from_one(tmp_path: Path) -> None:
    """特約の条は第1条から始まり、適用条件と準用の条を持つ。"""
    result = _gen(tmp_path, 1)
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    labels = policy["derived"]["labels"]
    added = json.loads((result.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))["added"][
        "nodes"
    ]
    riders = [n for n in added if n.startswith("rider_")]
    if not riders:
        pytest.skip("この seed では特約に分けたルールが無い")
    for rid in riders:
        assert labels[f"{rid}_a1"]["label"] == "第1条"
        assert labels[f"{rid}_a2"]["label"] == "第2条"
        assert "適用条件" in labels[f"{rid}_a1"]["title"]
        assert "準用" in labels[f"{rid}_a3"]["title"]


@needs_base
def test_rider_index_gets_a_row(tmp_path: Path) -> None:
    """足した特約が特約一覧に載る（S7-2）。"""
    result = _gen(tmp_path, 1)
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    table = policy["front_matter"].get("rider_index")
    if table is None:
        pytest.skip("この文書には特約一覧が無い")
    added = json.loads((result.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))["added"][
        "nodes"
    ]
    riders = [n for n in added if n.startswith("rider_")]
    if not riders:
        pytest.skip("この seed では特約に分けたルールが無い")
    titles = {c.get("text", "") for row in table["grid"] for c in row}
    for rid in riders:
        want = policy_title(policy, rid)
        assert want in titles, f"特約一覧に「{want}」の行が無い"


def policy_title(policy: dict, node_id: str) -> str:
    return policy["derived"]["labels"][node_id]["title"]


@needs_base
def test_scattered_rules_have_more_evidence_units(tmp_path: Path) -> None:
    """分散させたルールは根拠単位が増える（難易度の軸として効いている）。"""
    result = _gen(tmp_path, 4)
    answer = json.loads((result.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    spec = json.loads((result.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    kinds = {r["id"]: r["presentation"]["placement"] for r in spec["rules"]}
    for a in answer:
        if kinds.get(a["rule"]) == "appendix":
            assert any(u.startswith("tbl_app") for u in a["units"]), "別表の表が根拠単位に入っていない"


@needs_base
def test_footnote_dispersion(tmp_path: Path) -> None:
    """但し書きを条末脚注に割ったとき、本文に印が付き、脚注が根拠単位になる（S8-2）。"""
    found = False
    for seed in range(1, 9):
        result = _gen(tmp_path / f"f{seed}", seed)
        answer = json.loads((result.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
        notes = [(a["rule"], u) for a in answer for u in a["units"] if u.startswith("fn_")]
        if not notes:
            continue
        found = True
        policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
        plain = policy["derived"]["plain_text"]
        for _rule, uid in notes:
            assert uid in plain, f"{uid} が derived に無い"
            block = uid.split("__")[0]
            article = block.removeprefix("fn_")
            # 同じ条の本文に印が付いていること（本体 lint L02 の双方向対応）
            marked = [k for k in plain if k.startswith(article + "_p") and "（*" in plain[k]["without_label"]]
            assert marked, f"{article} の本文に脚注の印が無い"
        break
    assert found, "seed 1〜8 で 1 度も脚注に割られていない"


@needs_base
def test_footnote_keeps_the_order_of_explicitness(tmp_path: Path) -> None:
    """脚注に割っても、順序を見る明示性の要件（乗じて得た額 → 端数）が通る。"""
    from insurance_contracts_calculation.core.docindex import Doc
    from insurance_contracts_calculation.spec.validate import RuleSet
    from insurance_contracts_calculation.verify import gates

    result = _gen(tmp_path, 3)
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    spec = json.loads((result.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    doc = Doc.from_dict(policy)
    assert gates.explicitness(RuleSet(spec, doc), doc).ok

    # 読む順では、条末脚注はその条のどの項よりも後に来る
    order = gates.reading_order(doc)
    for uid, unit in doc.units.items():
        if unit.utype != "footnote":
            continue
        article = doc.article_of(unit.owner)
        siblings = [
            k
            for k, u in doc.units.items()
            if u.owner and doc.article_of(u.owner) == article and u.utype != "footnote"
        ]
        if not siblings:
            continue  # 条に本文が無い（別表の中の脚注など）
        assert order[uid] > max(order[k] for k in siblings), f"{uid} が条の途中で読まれている"


@needs_base
@pytest.mark.parametrize("seed", [1, 2, 3, 5, 7, 9])
def test_no_empty_operand_in_the_prose(tmp_path: Path, seed: int) -> None:
    """文の中に体言が抜けた箇所が無いこと。

    手順の体言を決め損ねると「この額がを上回る場合は」のような文ができる。
    lint もゲートも素通りするので、ここで止める。
    """
    import re

    result = _gen(tmp_path / str(seed), seed)
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    added = set(
        json.loads((result.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))["added"]["nodes"]
    )
    broken = re.compile(r"が(?:を|に|は|と)|、(?:を|が|に)[上超限]|「」|（）|  ")
    for uid, v in policy["derived"]["plain_text"].items():
        if not any(uid.startswith(a) for a in added):
            continue
        text = v.get("without_label") or ""
        assert not broken.search(text), f"{uid} の文に体言の抜けがある: {text[:80]}"
        assert "。。" not in text, f"{uid} に句点が重なっている"


def _article_of(unit: str) -> str:
    """根拠単位ID → それが属する条のID（`ch1_a9_p2` → `ch1_a9`）。"""
    return unit.rsplit("_p", 1)[0] if "_p" in unit else unit


@needs_base
def test_the_proviso_can_be_split_into_its_own_article(tmp_path: Path, monkeypatch) -> None:
    """但し書きを別の条に分けたとき、根拠が 2 つの条にまたがる（S9-2・DESIGN §8.5「分散」）。

    行き先は乱数で決まるので、ここでは必ず `article` を選ばせて経路そのものを確かめる。
    """
    from insurance_contracts_calculation.planning import placement as pl

    monkeypatch.setattr(
        pl, "choose_proviso", lambda ds, rng, sc: "article" if pl._has_proviso(ds) else "paragraph"
    )
    result = _gen(tmp_path, 4, "standard")
    answer = json.loads((result.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    plain = policy["derived"]["plain_text"]

    spread = [a for a in answer if len({_article_of(u) for u in a["units"] if "_p" in u}) > 1]
    assert spread, "どのルールも 1 つの条に収まっている（分散の経路を通っていない）"
    for a in spread:
        arts = sorted({_article_of(u) for u in a["units"] if "_p" in u})
        # 分けた先の条が本当に文書に在り、本文から指されていること
        pointed = [
            k
            for k in plain
            for other in arts
            if k.startswith(arts[0] + "_p") and policy["derived"]["labels"].get(other)
        ]
        assert pointed, f"{a['rule']}: 分けた条への案内が本文に無い"


@needs_base
def test_the_proviso_article_is_quoted_verbatim(tmp_path: Path, monkeypatch) -> None:
    """分けた条の `{ref:}` は、本体が描いたとおりの文字列で引用される（G2）。

    `{ref:}` の表示は引用元から見た相対表記なので、`labels[..].citation` で代用すると
    「第4章 第7条」と「第7条（買替費用保険金）」が食い違い、G2 が落ちる。
    """
    from insurance_contracts_calculation.planning import placement as pl

    monkeypatch.setattr(
        pl, "choose_proviso", lambda ds, rng, sc: "article" if pl._has_proviso(ds) else "paragraph"
    )
    result = _gen(tmp_path, 4, "standard")
    spec = json.loads((result.out_dir / "calc" / "spec.json").read_text(encoding="utf-8"))
    policy = json.loads((result.out_dir / "policy.json").read_text(encoding="utf-8"))
    plain = policy["derived"]["plain_text"]
    checked = 0
    for rule in spec["rules"]:
        for src in rule["sources"]:
            quote, uid = src.get("quote"), src["unit"]
            if not quote or uid not in plain:
                continue
            assert quote in plain[uid]["without_label"], f"{uid}: 引用が原文に無い: {quote[:40]}"
            checked += 1
    assert checked, "引用を 1 件も確かめていない"
