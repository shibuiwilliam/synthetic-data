"""検証ゲートが「落ちるべきときに落ちる」こと。

ゲートを無効化していないことを固定する（`CLAUDE.md` 守ること 9）。
"""

from __future__ import annotations

import pytest
from helpers import build_ruleset, minimal_policy

from insurance_contracts_calculation.core.docindex import Doc
from insurance_contracts_calculation.realize import figures as fg
from insurance_contracts_calculation.realize import patch as patch_ops
from insurance_contracts_calculation.spec import obligations as ob
from insurance_contracts_calculation.verify import gates


def test_g3_fails_when_the_sentence_is_missing() -> None:
    """宣言した明示性の要件に当たる文が無ければ G3 が落ちる。"""
    expr = {"op": "min", "args": [{"var": "a"}, {"lit": 100, "note": "検査用"}]}
    text_with = "この額が10万円を超えるときは、10万円とします。"
    text_without = "この額を支払います。"
    for text, want_ok in ((text_with, True), (text_without, False)):
        rs = build_ruleset(expr, {"a": 1}, obligations=["limit"], text=text)
        result = gates.explicitness(rs, rs.doc)
        assert result.ok is want_ok, f"{text}: G3 の結果が想定と違う"


def test_g3_rejects_unknown_obligation() -> None:
    with pytest.raises(ValueError):
        ob.build("そんな要件は無い")


@pytest.mark.parametrize("oid", ob.FAMILIES)
def test_every_obligation_builds(oid: str) -> None:
    assert ob.build(oid).patterns


def test_g8_detects_surface_clash() -> None:
    """定数の表記が素の文字列で書かれていたら G8 が落ちる（本体 lint L11 と同じ判定）。"""

    class Ctx:
        constants = {"deductible": "5万円"}
        const_surfaces = {"5万円"}
        node_ids: set[str] = set()
        block_ids: set[str] = set()
        benefits: set[str] = set()

    ok = gates.no_clash({}, {}, set(), set(), set(), ["修理費が375万円のときは"], Ctx())
    assert not ok.ok, "「375万円」は定数「5万円」を含むので落ちるべき"
    fine = gates.no_clash({}, {}, set(), set(), set(), ["修理費が{const:deductible}のときは"], Ctx())
    assert fine.ok


def test_g7_reports_survivors() -> None:
    stats = {"r": {"mutants": 3, "killed": 2, "survivors": ["0: ge→gt"]}}
    assert not gates.test_sufficiency(stats).ok
    assert gates.test_sufficiency({"r": {"mutants": 3, "killed": 3, "survivors": []}}).ok


def test_g9_blocks_on_lint_warnings() -> None:
    from insurance_contracts_calculation.base_adapter import Finding

    assert not gates.base_lint([Finding("L11", "warn", "直書き")]).ok
    assert gates.base_lint([Finding("L10", "warn", "文体")]).ok


def test_g9b_stops_over_the_page_limit() -> None:
    assert gates.page_budget(16.0, 18.0, 18, 20).ok
    assert not gates.page_budget(16.0, 19.5, 19, 20).ok
    assert not gates.page_budget(16.0, 17.0, 21, 20).ok


def test_figure_limits_are_enforced() -> None:
    spec = fg.FlowSpec(
        decisions=[fg.Decision(f"n{i}", f"判定{i}") for i in range(12)],
        start_label="事故の発生",
        pay_label="支払う",
        nopay_label="支払わない",
        caption="判定",
    )
    with pytest.raises(fg.FigureTooBig):
        fg.flowchart("fig_x", spec)


def test_figure_label_length_counts_tokens_as_displayed() -> None:
    assert fg.visible_len("{term:insured_car}が自力で走行できないか") < len(
        "{term:insured_car}が自力で走行できないか"
    )


def test_patch_refuses_to_overwrite() -> None:
    data = minimal_policy()
    with pytest.raises(patch_ops.PatchError):
        patch_ops.apply(data, [patch_ops.add_constant("t_limit", "20万円")])
    with pytest.raises(patch_ops.PatchError):
        patch_ops.apply(data, [patch_ops.add_node("ch1", {"id": "ch1_a1", "kind": "article"})])


def test_patch_adds_article_with_fresh_id() -> None:
    data = minimal_policy()
    chapter = patch_ops.find_node(data, "ch1")
    aid, n = patch_ops.next_article_id(chapter)
    assert (aid, n) == ("ch1_a2", 2)
    out = patch_ops.apply(
        data, [patch_ops.add_node("ch1", {"id": aid, "kind": "article", "title": "新しい条"})]
    )
    assert patch_ops.find_node(out, aid) is not None
    assert patch_ops.find_node(data, aid) is None, "元の辞書は変えない"


def test_doc_reads_added_table() -> None:
    doc = Doc.from_dict(minimal_policy())
    assert doc.units["tbl_t1__r1c1"].text == "30%"


def test_g5_recheck_restores_dates_from_jsonl() -> None:
    """`icc verify` の G5 は、保存した設例の日付を型に戻してから照合する。

    `cases.jsonl` の日付は ISO の文字列である。戻さずに渡すと、日付を返す規定で
    `surface_of` が `int("2026-04-12")` に落ちて、落第ではなく例外になる（実測で 50 文書中 12 件）。
    """
    import datetime as dt

    from insurance_contracts_calculation.core import numbers_ja as nj
    from insurance_contracts_calculation.verify import recheck

    start, want = dt.date(2026, 3, 13), dt.date(2026, 4, 12)
    expr = {"op": "add_days", "args": [{"var": "d"}, {"lit": 30, "note": "検査用の日数"}]}
    rs = build_ruleset(expr, {"d": start}, text=f"支払期日は{nj.date_ja(want)}とします。")
    case = {
        "kind": "example",
        "rule_id": "t.rule",
        "inputs": {"d": start.isoformat()},
        "expected": want.isoformat(),
        "expected_type": "date",
    }
    answer = [{"rule": "t.rule", "explanatory_units": ["ch1_a1_p1"]}]

    result = recheck._examples(rs, rs.doc, answer, [case])
    assert result.ok, result.detail

    # 文に日付が出てこなければ落第する（検査が空回りしていないこと）
    rs_bad = build_ruleset(expr, {"d": start}, text="支払期日は別に定めます。")
    assert not recheck._examples(rs_bad, rs_bad.doc, answer, [case]).ok
