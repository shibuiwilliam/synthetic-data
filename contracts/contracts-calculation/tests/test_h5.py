"""H5：apply 型 QA 47 問の機械検算の回帰テスト（TH5.6）。

親の qa_authored.json の答えと、仕様（contracts_calculation.h5.specs）から interp で算出した値が
全問一致し続けることを固定する。親の content か仕様が変わって食い違えばここで落ちる。
"""

import pytest

from contracts_calculation.h5 import verify as verify_h5


@pytest.fixture(scope="module")
def results() -> list[dict]:
    return verify_h5.run()


def test_all_47_processed(results) -> None:
    assert len(results) == 47
    cids = {r["cid"] for r in results}
    assert len(cids) == 20, "20 content すべてを覆う"


def test_no_check_failures(results) -> None:
    """G1（仕様）・G2（逐語照合）・G4（数値の往復）・契約日の突合がすべて通る。"""
    failures = [(r["cid"], r["qid"], r["problems"]) for r in results if r["problems"]]
    assert not failures, failures


def test_all_computations_match_answers(results) -> None:
    """47 問すべてで、算出値が親の答えと一致する。"""
    mismatch = [
        (r["cid"], r["qid"], r["computed"], r["expected"]) for r in results if r["computed"] != r["expected"]
    ]
    assert not mismatch, mismatch


def test_verdict_counts_fixed(results) -> None:
    """判定の内訳を固定する（読み幅の付け外しは意図的な変更としてここを更新する）。"""
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    assert counts == {"一致": 32, "読み幅あり（計算は一致）": 15}


def test_reading_flags_are_the_known_set(results) -> None:
    """人間判断に残す問（読み幅あり）の集合を固定する。"""
    flagged = sorted(f"{r['cid']}:{r['qid']}" for r in results if r["verdict"].startswith("読み幅"))
    assert flagged == [
        "con-0001:qa_auth_010",
        "csl-0001:qa_auth_009",
        "dlg-0001:qa_auth_009",
        "emp-0001:qa_auth_009",
        "emp-0001:qa_auth_010",
        "emp-0002:qa_auth_009",
        "lea-0001:qa_auth_009",
        "nda-0001:qa_auth_008",
        "nda-0001:qa_auth_009",
        "nda-0002:qa_auth_010",
        "ots-0001:qa_auth_009",
        "ots-0001:qa_auth_010",
        "pur-0001:qa_auth_009",
        "sys-0001:qa_auth_009",
        "sys-0001:qa_auth_010",
    ]
