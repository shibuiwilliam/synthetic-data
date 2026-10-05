"""付録Bの設例を CalcSpec にしたフィクスチャ（テスト用。生成物ではない）。

期待値は DESIGN.md 付録Bの値をそのまま書く（計算し直さない）。
test_appendix_b.py（interp での検算）と test_codegen.py（生成 Python との一致）が使う。
"""

from __future__ import annotations


def _src(unit: str, quote: str) -> dict:
    return {"unit": unit, "quote": quote}


def lit(v) -> dict:
    return {"lit": v}


def var(n: str) -> dict:
    return {"var": n}


def param(n: str) -> dict:
    return {"param": n}


def step(n: str) -> dict:
    return {"step": n}


def op(name: str, *args, **attrs) -> dict:
    d = {"op": name, "args": list(args)}
    d.update(attrs)
    return d


_PARTIES = {"payer": "乙", "payee": "甲"}

_TIER_TABLE = {
    "kind": "tiers",
    "unit": "JPY/COUNT",
    "rows": [
        {"upto": 100, "value": 500},
        {"upto": 500, "value": 400},
        {"upto": None, "value": 300},
    ],
    "source": _src("sch1_tbl__r1c1", "1件以上100件以下 500円"),
}

_CAL = {
    "weekend": ["SAT", "SUN"],
    "closed": [["12-29", "01-03"]],
    "holidays": "input",
    "source": _src("a2_i5", "土曜日、日曜日、国民の祝日及び12月29日から翌年1月3日までの日を除いた日"),
}


def _spec(
    rules: list[dict], params: dict | None = None, tables: dict | None = None, calendar: dict | None = None
) -> dict:
    return {
        "spec_version": "0.1",
        "document": {"content_id": "fixture-0001", "doctype": "outsourcing", "calc_seed": 1},
        "calendar": calendar,
        "params": params or {},
        "tables": tables or {},
        "rules": rules,
    }


def _int_param(value: int, unit: str, surface: str, src_unit: str = "a1_p1") -> dict:
    return {
        "type": "int",
        "unit": unit,
        "value": value,
        "surface": surface,
        "source": _src(src_unit, surface),
    }


def _ratio_param(num: int, den: int, surface: str, src_unit: str = "a1_p1") -> dict:
    return {"type": "ratio", "num": num, "den": den, "surface": surface, "source": _src(src_unit, surface)}


def _ex(inputs: dict, expect, holidays: list[str] | None = None) -> dict:
    d = {"oracle": "manual", "inputs": inputs, "expect": expect}
    if holidays:
        d["holidays"] = holidays
    return d


SPECS: dict[str, dict] = {}

# --- K03 段階料金（全量方式） ---------------------------------------------------

SPECS["k03"] = _spec(
    tables={"unit_price": _TIER_TABLE},
    rules=[
        {
            "id": "fee_all_units",
            "title": "段階料金（全量方式）",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "fee_all_units"},
            "inputs": {
                "qty": {
                    "type": "int",
                    "unit": "COUNT",
                    "min": 0,
                    "max": 10000,
                    "origin": "fact",
                    "desc": "当月の件数",
                }
            },
            "steps": [
                {
                    "name": "fee",
                    "label": "委託料",
                    "expr": op("tiered", var("qty"), table="unit_price", method="all_units"),
                }
            ],
            "output": {"step": "fee", "type": "int", "unit": "JPY"},
            "obligations": ["tier_method:all_units", "parties"],
            "examples": [
                _ex({"qty": 100}, 50000),
                _ex({"qty": 101}, 40400),
                _ex({"qty": 250}, 100000),
                _ex({"qty": 600}, 180000),
            ],
        }
    ],
)

# --- K04 段階料金（超過分方式） --------------------------------------------------

SPECS["k04"] = _spec(
    tables={"unit_price": _TIER_TABLE},
    rules=[
        {
            "id": "fee_marginal",
            "title": "段階料金（超過分方式）",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "fee_marginal"},
            "inputs": {
                "qty": {
                    "type": "int",
                    "unit": "COUNT",
                    "min": 0,
                    "max": 10000,
                    "origin": "fact",
                    "desc": "当月の件数",
                }
            },
            "steps": [
                {
                    "name": "fee",
                    "label": "委託料",
                    "expr": op("tiered", var("qty"), table="unit_price", method="marginal"),
                }
            ],
            "output": {"step": "fee", "type": "int", "unit": "JPY"},
            "obligations": ["tier_method:marginal", "parties"],
            "examples": [
                _ex({"qty": 100}, 50000),
                _ex({"qty": 101}, 50400),
                _ex({"qty": 250}, 110000),
                _ex({"qty": 600}, 240000),
            ],
        }
    ],
)

# --- K05 精算幅つき月額 ----------------------------------------------------------

SPECS["k05"] = _spec(
    params={
        "monthly_fee": _int_param(800000, "JPY", "月額80万円"),
        "lower_hours": _int_param(140, "HOUR", "140時間"),
        "upper_hours": _int_param(180, "HOUR", "180時間"),
        "excess_rate": _int_param(4440, "JPY/HOUR", "超過単価4,440円"),
        "deduct_rate": _int_param(5710, "JPY/HOUR", "控除単価5,710円"),
    },
    rules=[
        {
            "id": "band_settlement",
            "title": "精算幅つき月額",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "band_settlement"},
            "inputs": {
                "hours": {
                    "type": "int",
                    "unit": "HOUR",
                    "min": 0,
                    "max": 300,
                    "origin": "fact",
                    "desc": "当月の稼働時間",
                }
            },
            "steps": [
                {
                    "name": "shortage",
                    "label": "不足時間",
                    "expr": op("max", lit(0), op("sub", param("lower_hours"), var("hours"))),
                },
                {
                    "name": "excess",
                    "label": "超過時間",
                    "expr": op("max", lit(0), op("sub", var("hours"), param("upper_hours"))),
                },
                {
                    "name": "fee",
                    "label": "精算後の委託料",
                    "expr": op(
                        "add",
                        op("sub", param("monthly_fee"), op("mul", step("shortage"), param("deduct_rate"))),
                        op("mul", step("excess"), param("excess_rate")),
                    ),
                },
            ],
            "output": {"step": "fee", "type": "int", "unit": "JPY"},
            "obligations": ["band:deduct_below_lower_add_above_upper", "parties"],
            "examples": [
                _ex({"hours": 130}, 742900),
                _ex({"hours": 139}, 794290),
                _ex({"hours": 140}, 800000),
                _ex({"hours": 180}, 800000),
                _ex({"hours": 181}, 804440),
                _ex({"hours": 190}, 844400),
            ],
        }
    ],
)

# --- K07 日割 -------------------------------------------------------------------

SPECS["k07"] = _spec(
    params={"monthly_fee": _int_param(300000, "JPY", "月額30万円")},
    rules=[
        {
            "id": "prorate_actual",
            "title": "日割（当月の日数）",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "prorate_actual"},
            "inputs": {
                "usage_days": {
                    "type": "int",
                    "unit": "DAY",
                    "min": 0,
                    "max": 31,
                    "origin": "fact",
                    "desc": "利用日数",
                },
                "month_days": {
                    "type": "int",
                    "unit": "DAY",
                    "min": 28,
                    "max": 31,
                    "origin": "fact",
                    "desc": "当月の日数",
                },
            },
            "steps": [
                {
                    "name": "fee",
                    "label": "日割後の月額",
                    "expr": op(
                        "muldiv", param("monthly_fee"), var("usage_days"), var("month_days"), rounding="floor"
                    ),
                }
            ],
            "output": {"step": "fee", "type": "int", "unit": "JPY"},
            "obligations": ["proration_basis:actual_days_in_month", "rounding:floor_1yen", "parties"],
            "examples": [_ex({"usage_days": 17, "month_days": 31}, 164516)],
        },
        {
            "id": "prorate_30",
            "title": "日割（30日）",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "prorate_30"},
            "inputs": {
                "usage_days": {
                    "type": "int",
                    "unit": "DAY",
                    "min": 0,
                    "max": 31,
                    "origin": "fact",
                    "desc": "利用日数",
                }
            },
            "steps": [
                {
                    "name": "fee",
                    "label": "日割後の月額",
                    "expr": op("muldiv", param("monthly_fee"), var("usage_days"), lit(30), rounding="floor"),
                }
            ],
            "output": {"step": "fee", "type": "int", "unit": "JPY"},
            "obligations": ["proration_basis:30days", "rounding:floor_1yen", "parties"],
            "examples": [_ex({"usage_days": 17}, 170000)],
        },
    ],
)

# --- K11 締日と支払期日（月末締め・翌月末日払い・休業日は前営業日） -----------------

SPECS["k11"] = _spec(
    calendar=_CAL,
    rules=[
        {
            "id": "payment_due",
            "title": "支払期日",
            "kind": "calculation",
            "origin": "added",
            "interface": {"function": "payment_due_date"},
            "inputs": {
                "closing_date": {
                    "type": "date",
                    "min": "2026-01-01",
                    "max": "2029-12-31",
                    "origin": "fact",
                    "desc": "締日",
                }
            },
            "steps": [
                {
                    "name": "due_raw",
                    "label": "翌月末日",
                    "expr": op("end_of_month", op("add_months", var("closing_date"), lit(1))),
                },
                {"name": "due", "label": "支払期日", "expr": op("prev_business_day", step("due_raw"))},
            ],
            "output": {"step": "due", "type": "date"},
            "obligations": ["business_days:weekend_and_newyear", "holiday_adjust:prev_business_day"],
            "examples": [
                _ex({"closing_date": "2026-09-30"}, "2026-10-30"),
                _ex({"closing_date": "2026-10-31"}, "2026-11-30"),
            ],
        }
    ],
)

# --- K14 検査期限（納入日の翌日から10営業日） --------------------------------------

SPECS["k14"] = _spec(
    calendar=_CAL,
    params={"inspect_bdays": _int_param(10, "DAY", "10営業日", "a4_p2")},
    rules=[
        {
            "id": "inspect_deadline",
            "title": "検査期限",
            "kind": "calculation",
            "origin": "added",
            "interface": {"function": "inspect_deadline"},
            "inputs": {
                "delivery_date": {
                    "type": "date",
                    "min": "2026-01-01",
                    "max": "2029-12-31",
                    "origin": "fact",
                    "desc": "納入日",
                }
            },
            "steps": [
                {
                    "name": "deadline",
                    "label": "検査期限",
                    "expr": op("add_business_days", var("delivery_date"), param("inspect_bdays")),
                }
            ],
            "output": {"step": "deadline", "type": "date"},
            "obligations": ["business_days:weekend_and_newyear", "day_count:from_next_day"],
            "examples": [
                _ex({"delivery_date": "2026-12-22"}, "2027-01-11"),
                _ex({"delivery_date": "2026-12-22"}, "2027-01-12", holidays=["2027-01-11"]),
            ],
        }
    ],
)

# --- K17 遅延損害金 --------------------------------------------------------------

SPECS["k17"] = _spec(
    params={
        "late_rate": _ratio_param(146, 1000, "年14.6%", "a12_p1"),
        "year_days": _int_param(365, "DAY", "年365日", "a12_p1"),
    },
    rules=[
        {
            "id": "late_interest",
            "title": "遅延損害金の額",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "late_interest"},
            "inputs": {
                "unpaid_amount": {
                    "type": "int",
                    "unit": "JPY",
                    "min": 0,
                    "max": 100000000,
                    "origin": "fact",
                    "desc": "支払期日までに支払われなかった金額",
                },
                "due_date": {
                    "type": "date",
                    "min": "2026-01-01",
                    "max": "2029-12-31",
                    "origin": "fact",
                    "desc": "支払期日",
                },
                "paid_date": {
                    "type": "date",
                    "min": "2026-01-01",
                    "max": "2029-12-31",
                    "origin": "fact",
                    "desc": "実際に支払った日",
                },
            },
            "steps": [
                {
                    "name": "late_days",
                    "label": "遅延日数",
                    "expr": op("max", lit(0), op("days_between", var("due_date"), var("paid_date"))),
                },
                {
                    "name": "interest",
                    "label": "遅延損害金の額",
                    "expr": op(
                        "muldiv",
                        op("mul", var("unpaid_amount"), step("late_days")),
                        param("late_rate"),
                        param("year_days"),
                        rounding="floor",
                    ),
                },
            ],
            "output": {"step": "interest", "type": "int", "unit": "JPY"},
            "obligations": [
                "day_count:next_day_to_payment_day",
                "year_basis:365",
                "rounding:floor_1yen",
                "parties",
            ],
            "examples": [
                _ex({"unpaid_amount": 1000000, "due_date": "2026-11-30", "paid_date": "2026-12-25"}, 10000),
                _ex({"unpaid_amount": 1000000, "due_date": "2026-11-30", "paid_date": "2026-11-30"}, 0),
                _ex({"unpaid_amount": 1000000, "due_date": "2026-11-30", "paid_date": "2026-12-01"}, 400),
                _ex({"unpaid_amount": 1000000, "due_date": "2028-02-20", "paid_date": "2028-03-05"}, 5600),
            ],
        }
    ],
)

# --- K18 納期遅延の違約金 --------------------------------------------------------

SPECS["k18"] = _spec(
    params={
        "contract_price": _int_param(12000000, "JPY", "契約金額1,200万円"),
        "daily_rate": _ratio_param(1, 1000, "1日につき0.1%"),
        "cap_rate": _ratio_param(10, 100, "10%"),
    },
    rules=[
        {
            "id": "delay_penalty",
            "title": "納期遅延の違約金",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "delay_penalty"},
            "inputs": {
                "delay_days": {
                    "type": "int",
                    "unit": "DAY",
                    "min": 0,
                    "max": 365,
                    "origin": "fact",
                    "desc": "遅延日数",
                }
            },
            "steps": [
                {
                    "name": "raw",
                    "label": "違約金の額",
                    "expr": op(
                        "muldiv",
                        op("mul", param("contract_price"), var("delay_days")),
                        param("daily_rate"),
                        lit(1),
                        rounding="floor",
                    ),
                },
                {
                    "name": "cap",
                    "label": "違約金の上限",
                    "expr": op(
                        "muldiv", param("contract_price"), param("cap_rate"), lit(1), rounding="floor"
                    ),
                },
                {"name": "penalty", "label": "支払う違約金", "expr": op("min", step("raw"), step("cap"))},
            ],
            "output": {"step": "penalty", "type": "int", "unit": "JPY"},
            "obligations": ["rounding:floor_1yen", "cap:10_percent_of_price", "parties"],
            "examples": [
                _ex({"delay_days": 30}, 360000),
                _ex({"delay_days": 100}, 1200000),
                _ex({"delay_days": 150}, 1200000),
            ],
        }
    ],
)

# --- K20 損害賠償の上限と除外 -----------------------------------------------------

SPECS["k20"] = _spec(
    params={
        "monthly_fee": _int_param(300000, "JPY", "月額30万円"),
        "cap_months": _int_param(12, "MONTH", "12か月"),
    },
    rules=[
        {
            "id": "liability_cap",
            "title": "損害賠償の上限",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "liability_cap"},
            "inputs": {
                "damage": {
                    "type": "int",
                    "unit": "JPY",
                    "min": 0,
                    "max": 100000000,
                    "origin": "judgment",
                    "desc": "損害の額",
                },
                "willful": {"type": "bool", "origin": "judgment", "desc": "故意または重過失があるか"},
            },
            "steps": [
                {
                    "name": "cap",
                    "label": "賠償の上限額",
                    "expr": op("mul", param("monthly_fee"), param("cap_months")),
                },
                {
                    "name": "capped",
                    "label": "上限を適用した額",
                    "expr": op("min", var("damage"), step("cap")),
                },
                {
                    "name": "payable",
                    "label": "賠償額",
                    "expr": op("if", var("willful"), var("damage"), step("capped")),
                },
            ],
            "output": {"step": "payable", "type": "int", "unit": "JPY"},
            "obligations": ["cap_period:recent_12m", "cap_exception:willful_or_gross_negligence", "parties"],
            "examples": [
                _ex({"damage": 5000000, "willful": False}, 3600000),
                _ex({"damage": 5000000, "willful": True}, 5000000),
            ],
        }
    ],
)

# --- K21 補償の下限・バスケット・上限 ----------------------------------------------

_K21_PARAMS = {
    "de_minimis": _int_param(100000, "JPY", "個別の下限10万円"),
    "threshold": _int_param(1000000, "JPY", "しきい値100万円"),
    "cap": _int_param(10000000, "JPY", "上限1,000万円"),
}
_K21_INPUTS = {
    "damages": {"type": "list", "item_unit": "JPY", "origin": "judgment", "desc": "対象となる損害の一覧"}
}
_K21_ELIGIBLE_STEP = {
    "name": "eligible",
    "label": "対象損害の合計",
    "expr": {
        "op": "agg",
        "mode": "sum",
        "over": "damages",
        "filter": op("ge", {"item": True}, param("de_minimis")),
        "args": [],
    },
}

SPECS["k21"] = _spec(
    params=_K21_PARAMS,
    rules=[
        {
            "id": "indemnity_full",
            "title": "補償（全額方式）",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "indemnity_full"},
            "inputs": _K21_INPUTS,
            "steps": [
                _K21_ELIGIBLE_STEP,
                {
                    "name": "basket",
                    "label": "しきい値の判定",
                    "expr": op(
                        "if", op("ge", step("eligible"), param("threshold")), step("eligible"), lit(0)
                    ),
                },
                {"name": "paid", "label": "補償額", "expr": op("min", step("basket"), param("cap"))},
            ],
            "output": {"step": "paid", "type": "int", "unit": "JPY"},
            "obligations": ["basket:full_amount", "de_minimis:per_item", "parties"],
            "examples": [_ex({"damages": [80000, 600000, 700000]}, 1300000)],
        },
        {
            "id": "indemnity_excess",
            "title": "補償（超過額方式）",
            "kind": "calculation",
            "origin": "added",
            "parties": _PARTIES,
            "interface": {"function": "indemnity_excess"},
            "inputs": _K21_INPUTS,
            "steps": [
                _K21_ELIGIBLE_STEP,
                {
                    "name": "excess",
                    "label": "しきい値を超える部分",
                    "expr": op("max", lit(0), op("sub", step("eligible"), param("threshold"))),
                },
                {"name": "paid", "label": "補償額", "expr": op("min", step("excess"), param("cap"))},
            ],
            "output": {"step": "paid", "type": "int", "unit": "JPY"},
            "obligations": ["basket:excess_only", "de_minimis:per_item", "parties"],
            "examples": [_ex({"damages": [80000, 600000, 700000]}, 300000)],
        },
    ],
)

# --- K22 サービスレベルの返金 -----------------------------------------------------

SPECS["k22"] = _spec(
    params={
        "monthly_fee": _int_param(500000, "JPY", "月額50万円"),
        "refund_mid": _ratio_param(10, 100, "10%"),
        "refund_low": _ratio_param(20, 100, "20%"),
    },
    rules=[
        {
            "id": "sla_refund",
            "title": "サービスレベルの返金",
            "kind": "calculation",
            "origin": "added",
            "parties": {"payer": "甲", "payee": "乙"},
            "interface": {"function": "sla_refund"},
            "inputs": {
                "month_minutes": {
                    "type": "int",
                    "unit": "MIN",
                    "min": 40320,
                    "max": 44640,
                    "origin": "fact",
                    "desc": "当月の総時間（分）",
                },
                "planned_stop": {
                    "type": "int",
                    "unit": "MIN",
                    "min": 0,
                    "max": 10000,
                    "origin": "fact",
                    "desc": "計画停止時間（分）",
                },
                "downtime": {
                    "type": "int",
                    "unit": "MIN",
                    "min": 0,
                    "max": 44640,
                    "origin": "fact",
                    "desc": "障害による停止時間（分）",
                },
            },
            "steps": [
                {
                    "name": "target",
                    "label": "対象時間",
                    "expr": op("sub", var("month_minutes"), var("planned_stop")),
                },
                {"name": "uptime", "label": "稼働時間", "expr": op("sub", step("target"), var("downtime"))},
                {
                    "name": "ok999",
                    "label": "99.9%以上か",
                    "expr": op(
                        "ge", op("mul", step("uptime"), lit(1000)), op("mul", lit(999), step("target"))
                    ),
                },
                {
                    "name": "ok990",
                    "label": "99.0%以上か",
                    "expr": op("ge", op("mul", step("uptime"), lit(100)), op("mul", lit(99), step("target"))),
                },
                {
                    "name": "refund",
                    "label": "返金額",
                    "expr": op(
                        "if",
                        step("ok999"),
                        lit(0),
                        op(
                            "if",
                            step("ok990"),
                            op("muldiv", param("monthly_fee"), param("refund_mid"), lit(1), rounding="floor"),
                            op("muldiv", param("monthly_fee"), param("refund_low"), lit(1), rounding="floor"),
                        ),
                    ),
                },
            ],
            "output": {"step": "refund", "type": "int", "unit": "JPY"},
            "obligations": [
                "uptime:planned_stop_excluded_both",
                "ratio_compare:by_multiplication",
                "rounding:floor_1yen",
                "parties",
            ],
            "examples": [_ex({"month_minutes": 43200, "planned_stop": 120, "downtime": 50}, 50000)],
        }
    ],
)
