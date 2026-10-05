"""データカード（`dataset/data-card.md`）の生成のテスト。仕様は `docs/data_card.md`。

本体（`yakkan`）も PDF も要らないように、**最小のデータセットをその場で組む**。
PDF が無ければフォントの実測は空になるだけで、ほかの数値は測れる（`docs/data_card.md` §4.1）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from insurance_contracts_calculation.export import datacard as dc


def _policy(content_id: str, *, text: str = "この保険金の額は、5万円を限度とします。") -> dict:
    """`Doc` が読める最小の約款JSON（`derived` 込み）。"""
    return {
        "schema_version": "1.0",
        "content_id": content_id,
        "genre": "auto",
        "seed": 1,
        "meta": {
            "title": "検査用約款",
            "constants": {"t_limit": "5万円"},
            "disclaimer": "本冊子は検証用の架空の約款です。",
            "digit_style": "halfwidth",
            "numbering_scheme": "nonlife",
            "footnote_style": "inline",
        },
        "front_matter": {},
        "defined_terms": [],
        "body": [
            {
                "id": "ch1",
                "kind": "chapter",
                "title": "補償",
                "children": [
                    {
                        "id": "ch1_a1",
                        "kind": "article",
                        "title": "検査用の条",
                        "children": [
                            {"id": "ch1_a1_p1", "kind": "paragraph", "text": text, "blocks": []},
                        ],
                        "blocks": [],
                    }
                ],
            }
        ],
        "appendices": [],
        "back_matter": {},
        "derived": {
            "labels": {},
            "refs": [],
            "term_uses": [],
            "footnote_index": {},
            "plain_text": {"ch1_a1_p1": {"with_label": text, "without_label": text}},
            "tables": {},
            "figures": {},
            "formulas": {},
            "enumerations": [],
            "toc": [],
        },
    }


def _spec(content_id: str) -> dict:
    return {
        "spec_version": "0.2",
        "document": {"content_id": content_id, "genre": "auto", "calc_seed": 1},
        "params": {"t_limit": {"unit": "JPY", "from_const": "t_limit"}},
        "tables": {},
        "rules": [
            {
                "id": "t.payout",
                "title": "検査用の保険金の額",
                "kind": "calculation",
                "interface": {"function": "t_payout"},
                "inputs": {"amount": {"type": "int", "origin": "claim_fact", "unit": "JPY"}},
                "collections": {},
                "steps": [
                    {
                        "name": "t_payout",
                        "label": "額",
                        "expr": {"op": "min", "args": [{"var": "amount"}, {"param": "t_limit"}]},
                        "role": "core",
                    }
                ],
                "output": {"step": "t_payout", "type": "int", "unit": "JPY"},
                "obligations": ["limit"],
                "sources": [{"unit": "ch1_a1_p1", "quote": "この保険金の額は、5万円を限度とします。"}],
                "properties": [],
                "preconditions": [],
                "presentation": {
                    "pattern": "P01",
                    "placement": "article",
                    "subject": "t",
                    "table": None,
                    "figure": None,
                    "formula": None,
                    "explanatory_units": [],
                },
                "difficulty": {},
            }
        ],
    }


def make_dataset(root: Path, doc_ids: tuple[str, ...] = ("auto-0001-c1",)) -> Path:
    """最小のデータセットを組む（描画結果は無し）。"""
    for doc_id in doc_ids:
        base = doc_id.rsplit("-c", 1)[0]
        calc = root / doc_id / "calc"
        (calc / "programs").mkdir(parents=True, exist_ok=True)
        (calc / "tests").mkdir(parents=True, exist_ok=True)
        (root / doc_id / "policy.json").write_text(
            json.dumps(_policy(doc_id), ensure_ascii=False), encoding="utf-8"
        )
        (calc / "spec.json").write_text(json.dumps(_spec(doc_id), ensure_ascii=False), encoding="utf-8")
        (calc / "answer_key.json").write_text(
            json.dumps(
                [
                    {
                        "rule": "t.payout",
                        "function": "t_payout",
                        "pattern": "P01",
                        "units": ["ch1_a1_p1"],
                        "explanatory_units": [],
                        "constants": ["t_limit"],
                        "modalities": ["prose"],
                        "difficulty": {},
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (calc / "cases.jsonl").write_text(
            "".join(
                json.dumps(row, ensure_ascii=False) + "\n"
                for row in (
                    {"case_id": f"{doc_id}:t_payout:b001", "kind": "boundary", "rule_id": "t.payout"},
                    {"case_id": f"{doc_id}:t_payout:e001", "kind": "example", "rule_id": "t.payout"},
                )
            ),
            encoding="utf-8",
        )
        for name in ("tasks.jsonl", "tasks_H1.jsonl", "tasks_H2.jsonl"):
            (calc / name).write_text(
                json.dumps({"task_id": f"{doc_id}:t_payout", "function": "t_payout"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
        (calc / "patch.json").write_text(
            json.dumps([{"op": "add_constant", "key": "t_limit", "value": "5万円"}], ensure_ascii=False),
            encoding="utf-8",
        )
        (calc / "programs" / f"calc_{doc_id.replace('-', '_')}.py").write_text(
            "def t_payout(*, amount):\n    return min(amount, 50000)\n", encoding="utf-8"
        )
        (calc / "manifest.json").write_text(
            json.dumps(
                {
                    "content_id": doc_id,
                    "base_content_id": base,
                    "genre": "auto",
                    "seed": 1,
                    "generator_version": "0.7.0",
                    "spec_version": "0.2",
                    "profile": "basic",
                    "plan": {"rules": ["t.payout"], "patterns": ["P01"], "skipped": []},
                    "added": {"add_constant": 1, "add_node": 0},
                    "pages": {"before": 10.0, "after": 10.5, "rendered": None},
                    "renders": [],
                    "counts": {"rules": 1, "cases": 2, "cases_by_kind": {"boundary": 1, "example": 1}},
                    "challenge": [],
                    "gates": {
                        "G1": {"ok": True},
                        "G7": {"ok": True, "mutants": 3, "survivors": {}},
                        "G10": {"ok": True, "found": 1, "need": 1, "missing": []},
                    },
                    "files": {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return root


def test_collect_measures_the_real_files(tmp_path: Path) -> None:
    stats = dc.collect(make_dataset(tmp_path, ("auto-0001-c1", "auto-0001-c2")))
    assert stats.scale.documents == 2
    assert stats.scale.bases == 1  # 同じ既定の約款の 1 本目と 2 本目
    assert stats.scale.rules == 2
    assert stats.scale.cases == 4
    assert stats.scale.taskcards == 6  # H0・H1・H2 × 2 文書
    assert stats.scale.programs == 2
    assert stats.scale.mutants == 6
    assert [row.name for row in stats.patterns] == ["P01"]
    assert stats.scale.layouts == 0  # 描画結果を置いていない
    assert [d.variant for d in stats.documents] == [1, 2]


def test_card_has_no_baked_in_numbers(tmp_path: Path) -> None:
    """固定文に数値を焼き込んでいない：**文書を増やすと本文の数が変わる**。

    1 文書のカードに出てくる 3 桁以上の数と、2 文書のカードの数が一致したら、
    どこかに固定値が焼き込まれている疑いがある。
    """
    one = dc.render_card(dc.collect(make_dataset(tmp_path / "a", ("auto-0001-c1",))))
    two = dc.render_card(dc.collect(make_dataset(tmp_path / "b", ("auto-0001-c1", "auto-0001-c2"))))
    assert one != two
    # 本文の文字数（約款を 2 件数えた値）が倍になっている
    assert dc._n(2 * _chars(one)) == f"{_chars(two):,}"


def _chars(card: str) -> int:
    m = re.search(r"^\| 約款の本文の文字数[^|]*\| ([0-9,]+) \|", card, re.MULTILINE)
    assert m is not None
    return int(m.group(1).replace(",", ""))


def test_deterministic(tmp_path: Path) -> None:
    """同じ `dataset/` なら同じカードが出る（時刻を混ぜていない）。"""
    root = make_dataset(tmp_path, ("auto-0001-c1", "auto-0002-c1"))
    assert dc.render_card(dc.collect(root)) == dc.render_card(dc.collect(root))


def test_write_and_check_roundtrip(tmp_path: Path) -> None:
    root = make_dataset(tmp_path, ("auto-0001-c1",))
    path = dc.write_card(root)
    assert path.name == dc.CARD_NAME
    assert dc.check(root) == []


def test_check_detects_staleness(tmp_path: Path) -> None:
    """文書を足したらカードが古くなり、`check` がそれを言う。"""
    root = make_dataset(tmp_path, ("auto-0001-c1",))
    dc.write_card(root)
    make_dataset(root, ("auto-0002-c1",))
    problems = dc.check(root)
    assert problems, "文書が増えたのに古さを検出していない"
    assert any("一致しない" in p for p in problems)
    dc.write_card(root)
    assert dc.check(root) == []


def test_check_reports_missing_card(tmp_path: Path) -> None:
    root = make_dataset(tmp_path, ("auto-0001-c1",))
    assert any("が無い" in p for p in dc.check(root))


def test_card_itself_is_not_counted_in_size(tmp_path: Path) -> None:
    """自分自身を容量に数えない（数えると鮮度検査が収束しない）。"""
    root = make_dataset(tmp_path, ("auto-0001-c1",))
    dc.write_card(root)
    first = dc.collect(root).scale.bytes_total
    dc.write_card(root)
    assert dc.collect(root).scale.bytes_total == first


def test_thin_and_unused_coverage(tmp_path: Path) -> None:
    """母数の小さい観点と、宣言はあるが使用 0 の観点を挙げる。"""
    stats = dc.collect(make_dataset(tmp_path, ("auto-0001-c1",)))
    thin = {(c.group, c.name) for c in stats.thin}
    unused = {(c.group, c.name) for c in stats.unused}
    assert ("パターン", "P01") in thin, "1 文書しか覆っていないパターンは母数不足に挙げる"
    assert ("パターン", "P02") in unused, "使っていないパターンは未使用に挙げる"
    assert ("宣言", "種目: quake") in unused
    assert thin & unused == set(), "母数不足と未使用は排他である"


def test_refresh_only_when_card_exists(tmp_path: Path) -> None:
    """カードの無い出力先（`examples/` など）を汚さない。"""
    root = make_dataset(tmp_path, ("auto-0001-c1",))
    assert dc.refresh_if_present(root) is None
    assert not (root / dc.CARD_NAME).exists()
    dc.write_card(root)
    assert dc.refresh_if_present(root) is not None


def test_empty_dataset_is_not_an_error(tmp_path: Path) -> None:
    stats = dc.collect(tmp_path)
    assert stats.scale.documents == 0
    assert "文書が無い" in dc.render_card(stats)
    assert any("文書が無い" in p for p in dc.check(tmp_path))


def test_run_report_is_only_used_for_not_generated(tmp_path: Path) -> None:
    """作れなかった組だけを `_run_report.json` から読み、ほかは実ファイルから測る。"""
    root = make_dataset(tmp_path, ("auto-0001-c1",))
    (root / dc.RUN_REPORT).write_text(
        json.dumps(
            {
                "documents_total": 999,  # 嘘の値。カードはこれを信じない
                "not_generated": {"count": 2, "entries": {"a#1": "gate: …", "b#2": "RuntimeError: …"}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    stats = dc.collect(root)
    assert stats.scale.documents == 1, "`_run_report.json` の自己申告を数に使ってはいけない"
    assert stats.not_generated.available
    assert stats.not_generated.count == 2
    assert {r.name for r in stats.not_generated.reasons} == {"gate", "RuntimeError"}
    card = dc.render_card(stats)
    assert "999" not in card


def test_gate_titles_come_from_the_registry() -> None:
    """ゲートの題は `verify/gates.py` の `GATE_TITLES` が唯一の正。"""
    from insurance_contracts_calculation.verify.gates import GATE_TITLES

    assert GATE_TITLES["G1"] and GATE_TITLES["G12"]


@pytest.mark.parametrize("doc_id,expected", [("auto-0001-c1", 1), ("auto-0001-c2", 2), ("auto-0001", 1)])
def test_variant_of(doc_id: str, expected: int) -> None:
    assert dc.variant_of(doc_id) == expected
