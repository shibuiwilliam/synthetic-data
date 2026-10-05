"""validate：正例（付録B）＋ 1 箇所ずつ壊した負例（T1.5）。"""

import copy

from appendix_b_specs import SPECS

from contracts_calculation.spec.model import CalcSpec
from contracts_calculation.spec.validate import validate_spec


def _issues_of(raw: dict) -> list[str]:
    return [str(i) for i in validate_spec(CalcSpec.from_dict(raw))]


def _broken(key: str, mutate) -> list[str]:
    raw = copy.deepcopy(SPECS[key])
    mutate(raw)
    return _issues_of(raw)


def test_unknown_op_rejected() -> None:
    issues = _broken("k17", lambda r: r["rules"][0]["steps"][0]["expr"].update({"op": "divide"}))
    assert any("未知の演算" in i for i in issues)


def test_forward_step_reference_rejected() -> None:
    def mutate(r):
        steps = r["rules"][0]["steps"]
        steps[0]["expr"] = {"step": steps[1]["name"]}

    assert any("前方参照" in i for i in _broken("k17", mutate))


def test_missing_rounding_rejected() -> None:
    def mutate(r):
        del r["rules"][0]["steps"][1]["expr"]["rounding"]

    assert any("rounding" in i for i in _broken("k17", mutate))


def test_tiered_without_method_rejected() -> None:
    def mutate(r):
        del r["rules"][0]["steps"][0]["expr"]["method"]

    assert any("all_units / marginal" in i for i in _broken("k03", mutate))


def test_undeclared_input_rejected() -> None:
    def mutate(r):
        r["rules"][0]["steps"][0]["expr"] = {"var": "nonexistent"}

    assert any("未宣言の入力" in i for i in _broken("k03", mutate))


def test_float_rejected() -> None:
    def mutate(r):
        r["params"]["late_rate"] = {
            "type": "int",
            "value": 1,
            "unit": "DAY",
            "source": {"unit": "a1", "quote": "x"},
        }
        r["rules"][0]["steps"][1]["expr"]["args"][1] = {"lit": 0.146}

    assert any("float" in i for i in _broken("k17", mutate))


def test_param_without_source_rejected() -> None:
    def mutate(r):
        del r["params"]["late_rate"]["source"]

    assert any("根拠" in i for i in _broken("k17", mutate))


def test_money_rule_without_parties_rejected() -> None:
    def mutate(r):
        del r["rules"][0]["parties"]

    assert any("parties" in i for i in _broken("k17", mutate))


def test_tiers_not_ascending_rejected() -> None:
    def mutate(r):
        r["tables"]["unit_price"]["rows"][0]["upto"] = 600

    assert any("昇順" in i for i in _broken("k03", mutate))


def test_business_op_without_calendar_rejected() -> None:
    def mutate(r):
        r["calendar"] = None

    assert any("spec.calendar" in i for i in _broken("k14", mutate))


def test_missing_obligation_for_muldiv_rejected() -> None:
    def mutate(r):
        r["rules"][0]["obligations"] = ["parties"]

    assert any("明示性" in i for i in _broken("k17", mutate))


def test_duplicate_function_rejected() -> None:
    def mutate(r):
        r["rules"].append(copy.deepcopy(r["rules"][0]))
        r["rules"][1]["id"] = "other"

    assert any("重複" in i for i in _broken("k17", mutate))
