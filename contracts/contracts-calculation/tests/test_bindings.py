"""付与モード：バインディングごとの固定テスト（T4.3・T4.4 の機械部分）。

本体のテンプレート（content の文言）が変わったら、ここの期待が外れて検出できる。
"""

from __future__ import annotations

from contracts_calculation import base_adapter as ba
from contracts_calculation.bindings.engine import bind_document
from contracts_calculation.bindings.raw import raw_text_map
from contracts_calculation.docmodel.index import DocumentIndex
from contracts_calculation.spec.interp import eval_rule
from contracts_calculation.spec.model import CalcSpec
from contracts_calculation.spec.validate import validate_spec


def _bind(cid: str):
    content = ba.repo_root() / "content" / cid
    idx = DocumentIndex.load(content)
    return idx, *bind_document(idx, raw_text_map(content), set())


def test_ots_0001_bindings_fixed() -> None:
    _idx, included, _excluded = _bind("ots-0001")
    by_binding = {b.binding: b for b in included}
    # 支払期日：請求書を受け取った月の翌月末日
    pay = by_binding["payment_due.monthly"]
    assert pay.units == ["a3_p2"]
    spec = CalcSpec.from_dict(
        {"spec_version": "0.1", "document": {}, "params": pay.params, "tables": {}, "rules": [pay.rule]}
    )
    assert not validate_spec(spec)
    got = eval_rule(spec, spec.rules[0], {"base_date": "2026-09-10"})
    assert got.isoformat() == "2026-10-31"  # 受領月の翌月末日
    # 賠償上限：min(損害, min(個別契約の委託料, 300万円))
    cap = by_binding["liability_cap"]
    assert cap.units == ["a11_p1"]
    spec2 = CalcSpec.from_dict(
        {"spec_version": "0.1", "document": {}, "params": cap.params, "tables": {}, "rules": [cap.rule]}
    )
    assert not validate_spec(spec2)
    assert eval_rule(spec2, spec2.rules[0], {"damage_amount": 5_000_000, "order_fee": 4_000_000}) == 3_000_000
    assert eval_rule(spec2, spec2.rules[0], {"damage_amount": 1_000_000, "order_fee": 4_000_000}) == 1_000_000
    # 遅延損害金：起算・年あたり日数・端数処理が明示され、一義に計算できる
    late = by_binding["late_interest.simple"]
    assert late.units == ["a3_p5"]
    spec3 = CalcSpec.from_dict(
        {"spec_version": "0.1", "document": {}, "params": late.params, "tables": {}, "rules": [late.rule]}
    )
    assert not validate_spec(spec3)
    assert (
        eval_rule(
            spec3,
            spec3.rules[0],
            {"unpaid_amount": 1_000_000, "due_date": "2026-11-30", "paid_date": "2026-12-25"},
        )
        == 2_054
    )


def test_csl_0001_renewal_included_with_h5_reading() -> None:
    """H5 承認（2026-10-04）の読み：「Nか月前まで」＝満了日の応当日・当日を含む。

    csl-0001 の H5 設問（qa_auth_009：満了 2027-12-14 → 期限 2027-09-14）と同じ値になる。
    """
    _, included, _excluded = _bind("csl-0001")
    renew = next(b for b in included if b.binding == "renewal_notice.deadline")
    assert renew.units == ["a8_p2"]
    spec = CalcSpec.from_dict(
        {"spec_version": "0.1", "document": {}, "params": renew.params, "tables": {}, "rules": [renew.rule]}
    )
    assert not validate_spec(spec)
    got = eval_rule(spec, spec.rules[0], {"expiry_date": "2027-12-14"})
    assert got.isoformat() == "2027-09-14"


def test_nda_0001_renewal_excluded_literal_months() -> None:
    """nda-0001 は予告期間が定数化されておらず（生テキスト直書き）、記録つきで除外される。"""
    _, _, excluded = _bind("nda-0001")
    renew = [e for e in excluded if e.binding == "renewal_notice.deadline"]
    assert renew and any("定数として取れない" in m for m in renew[0].missing)


def test_pur_0002_cap_uses_head_price_and_willful() -> None:
    _, included, _ = _bind("pur-0002")
    cap = next(b for b in included if b.binding == "liability_cap")
    assert "total_price" in cap.params
    spec = CalcSpec.from_dict(
        {"spec_version": "0.1", "document": {}, "params": cap.params, "tables": {}, "rules": [cap.rule]}
    )
    rule = spec.rules[0]
    assert "willful" in rule.inputs
    assert eval_rule(spec, rule, {"damage_amount": 99_999_999, "willful": False}) == 12_648_000
    assert eval_rule(spec, rule, {"damage_amount": 99_999_999, "willful": True}) == 99_999_999


def test_binding_counts_across_bases() -> None:
    """HC-2 で固定した v1 の 20 base に対する照合数を固定する。"""
    inc = exc = 0
    for base in ba.list_v1_base_contents():
        idx = DocumentIndex.load(base)
        included, excluded = bind_document(idx, raw_text_map(base), set())
        inc += len(included)
        exc += len(excluded)
    assert (inc, exc) == (26, 3)
