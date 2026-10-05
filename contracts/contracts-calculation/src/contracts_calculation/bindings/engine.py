"""バインディングの照合エンジン（DESIGN.md §6.1）。

既定の契約書の条項（文言が仕様より先にあるもの）を 4 種のバインディングで照合し、
一義に計算できるものだけを bound ルールにする。明示性が欠けるもの（on_missing=exclude）は、
何が欠けているかを記録して除外する。契約書JSONは変更しない。

4 種（v1）:
  late_interest.simple   遅延損害金（年率・日割）— 起算・分母・端数処理が明示されたものだけを含める
  payment_due.monthly    支払期日（翌月・翌々月の指定日または末日）— 一義に計算できる
  renewal_notice.deadline 更新しない旨の通知の期限 — H5 承認（2026-10-04）の読みで include
  liability_cap          損害賠償の上限（定額・契約金額・基準額入力）— 一義に計算できる
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..docmodel.index import DocumentIndex
from ..docmodel.numbers_ja import normalize, parse_day_of_month, read_value
from .raw import const_keys_in

#: 宣言しているバインディングと題名（データカードの表示と「未使用の宣言」検出に使う。
#: 実装が返す binding 名と一致することをテストで固定する）
BINDING_TITLES: dict[str, str] = {
    "late_interest.simple": "遅延損害金（年率・日割）",
    "liability_cap": "損害賠償の上限",
    "payment_due.monthly": "支払期日（翌月・翌々月の指定日または末日）",
    "renewal_notice.deadline": "更新しない旨の通知の期限",
}

#: バインディングのパターン ID（calc/answer_key.json の pattern）→ バインディング名
BINDING_PATTERNS: dict[str, str] = {
    "B-LATE": "late_interest.simple",
    "B-CAP": "liability_cap",
    "B-PAY": "payment_due.monthly",
    "B-RENEW": "renewal_notice.deadline",
}

DECLARED_BINDINGS: tuple[str, ...] = tuple(sorted(BINDING_TITLES))

_RATE_RE = re.compile(r"年[0-9０-９.．]+(?:％|%|パーセント)")
_PAY_RE = re.compile(r"(翌月|翌々月)の?(末日|[0-9]{1,2}日)までに")
_RENEW_RE = re.compile(r"満了する?[0-9０-９]+か月前までに")


@dataclass
class BoundRule:
    binding: str
    rule: dict  # CalcSpec のルール
    params: dict[str, dict]  # 追加する params（親の定数キー名）
    units: list[str]  # 根拠の単位
    inline_params: list[str] = field(default_factory=list)  # meta.constants に無い（文中の語）


@dataclass
class Excluded:
    binding: str
    unit: str
    missing: list[str]

    def to_dict(self) -> dict:
        return {"binding": self.binding, "unit": self.unit, "missing": self.missing}


def bind_document(
    idx: DocumentIndex, raw: dict[str, str], skip_units: set[str]
) -> tuple[list[BoundRule], list[Excluded]]:
    """1 文書を照合する。skip_units（追加モードで足した単位）は対象にしない。"""
    included: list[BoundRule] = []
    excluded: list[Excluded] = []
    units = [
        (uid, u)
        for uid, u in sorted(idx.units.items())
        if uid not in skip_units and "__r" not in uid and u.text
    ]

    for finder in (_bind_late_interest, _bind_payment_due, _bind_renewal, _bind_liability_cap):
        done = False
        for uid, u in units:
            if done:
                break
            result = finder(idx, raw, uid, u.text)
            if result is None:
                continue
            if isinstance(result, Excluded):
                excluded.append(result)
            else:
                included.append(result)
            done = True  # 1 バインディング 1 文書 1 件（最初の一致だけを使う）
    return included, excluded


# --- 各バインディング ---------------------------------------------------------------


def _consts_in_unit(idx: DocumentIndex, raw: dict[str, str], uid: str) -> list[tuple[str, str]]:
    keys = const_keys_in(raw.get(uid, ""))
    return [(k, idx.constants[k]) for k in keys if k in idx.constants]


def _bind_late_interest(idx, raw, uid, text):
    if not (("遅延損害金" in text or "遅延利息" in text) and _RATE_RE.search(normalize(text))):
        return None
    missing = []
    if not re.search(r"翌日から.*(?:支払|弁済).*日まで", text):
        missing.append("day_count:起算日と終算日が書かれていない")
    if not re.search(r"年[0-9０-９]+日", normalize(text)):
        missing.append("year_basis:年あたりの日数（日割の分母）が書かれていない")
    if "端数" not in text:
        missing.append("rounding:端数処理が書かれていない")
    rate = next(
        ((k, s) for k, s in _consts_in_unit(idx, raw, uid) if read_value(s, "ratio", None)),
        None,
    )
    if rate is None:
        missing.append("rate:率が定数として取れない")
    year_const = next(
        (
            (k, s)
            for k, s in _consts_in_unit(idx, raw, uid)
            if (v := read_value(s, "int", "DAY")) is not None and v >= 360
        ),
        None,
    )
    if year_const is None:
        missing.append("year_basis:年あたりの日数が定数として取れない")
    if "切り捨て" not in text:
        missing.append("rounding:端数処理の方向が書かれていない")
    if missing:
        return Excluded("late_interest.simple", uid, missing)
    key, surface = rate
    num, den = read_value(surface, "ratio", None)
    ykey, ysurface = year_const
    params = {
        key: {
            "type": "ratio",
            "num": num,
            "den": den,
            "surface": surface,
            "source": {"unit": uid, "quote": surface},
        },
        ykey: {
            "type": "int",
            "unit": "DAY",
            "value": read_value(ysurface, "int", "DAY"),
            "surface": ysurface,
            "source": {"unit": uid, "quote": ysurface},
        },
    }
    rule = {
        "id": "bound_late_interest",
        "title": "遅延損害金の額",
        "kind": "calculation",
        "origin": "bound",
        "parties": {"payer": "支払義務者", "payee": "相手方"},
        "interface": {"function": "late_payment_interest"},
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
                "max": "2032-12-31",
                "origin": "fact",
                "desc": "支払期日",
            },
            "paid_date": {
                "type": "date",
                "min": "2026-01-01",
                "max": "2033-12-31",
                "origin": "fact",
                "desc": "実際に支払った日",
            },
        },
        "steps": [
            {
                "name": "late_days",
                "label": "遅延日数",
                "expr": {
                    "op": "max",
                    "args": [
                        {"lit": 0},
                        {"op": "days_between", "args": [{"var": "due_date"}, {"var": "paid_date"}]},
                    ],
                },
            },
            {
                "name": "interest",
                "label": "遅延損害金の額",
                "expr": {
                    "op": "muldiv",
                    "rounding": "floor",
                    "args": [
                        {"op": "mul", "args": [{"var": "unpaid_amount"}, {"step": "late_days"}]},
                        {"param": key},
                        {"param": ykey},
                    ],
                },
            },
        ],
        "output": {"step": "interest", "type": "int", "unit": "JPY"},
        "obligations": [
            "day_count:next_day_to_payment_day",
            "year_basis:declared_days",
            "rounding:floor_1yen",
        ],
        "sources": [
            {"unit": uid, "quote": _quote_around(text, "遅延損害金" if "遅延損害金" in text else "遅延利息")}
        ],
        "presentation": {"pattern": "B-LATE", "placement": "bound"},
        "difficulty": {"calendar": "days", "origin": "bound"},
    }
    return BoundRule(binding="late_interest.simple", params=params, units=[uid], rule=rule)


def _bind_payment_due(idx, raw, uid, text):
    norm = normalize(text)
    if "支払" not in text:
        return None
    m = _PAY_RE.search(norm)
    if not m:
        return None
    offset = 1 if m.group(1) == "翌月" else 2
    day_text = m.group(2)
    day = "end" if day_text == "末日" else parse_day_of_month(day_text)
    if day is None:
        return Excluded("payment_due.monthly", uid, ["day:支払日の読取に失敗"])
    base_expr = {"op": "add_months", "args": [{"var": "base_date"}, {"lit": offset}]}
    due_expr = (
        {"op": "end_of_month", "args": [base_expr]}
        if day == "end"
        else {"op": "set_day", "args": [base_expr, {"lit": day}]}
    )
    rule = {
        "id": "bound_payment_due",
        "title": "支払期日",
        "kind": "calculation",
        "origin": "bound",
        "interface": {"function": "payment_due_date"},
        "inputs": {
            "base_date": {
                "type": "date",
                "origin": "fact",
                "desc": "支払の基準となる日（条項の定める締め・請求受領・対象月に属する日）",
                "min": "2026-01-01",
                "max": "2032-12-31",
            }
        },
        "steps": [{"name": "due", "label": "支払期日", "expr": due_expr}],
        "output": {"step": "due", "type": "date"},
        "obligations": ["payday:stated_in_clause"],
        "sources": [{"unit": uid, "quote": _quote_around(text, m.group(0))}],
        "presentation": {"pattern": "B-PAY", "placement": "bound"},
        "difficulty": {"calendar": "months", "origin": "bound"},
    }
    return BoundRule(binding="payment_due.monthly", params={}, units=[uid], rule=rule)


def _bind_renewal(idx, raw, uid, text):
    norm = normalize(text)
    if not (
        _RENEW_RE.search(norm) and ("申出" in text or "通知" in text) and ("更新" in text or "継続" in text)
    ):
        return None
    # 「Nか月前まで」の読みは H5 の人間判断（2026-10-04 承認）に従う：
    # 満了日の応当日とし、応当日当日を含む = add_months(満了日, -N)
    months_const = next(
        (
            (k, s)
            for k, s in _consts_in_unit(idx, raw, uid)
            if (d := read_value(s, "int", "MONTH")) is not None and 1 <= d <= 12
        ),
        None,
    )
    if months_const is None:
        return Excluded("renewal_notice.deadline", uid, ["months:予告期間が定数として取れない"])
    key, surface = months_const
    params = {
        key: {
            "type": "int",
            "unit": "MONTH",
            "value": read_value(surface, "int", "MONTH"),
            "surface": surface,
            "source": {"unit": uid, "quote": surface},
        }
    }
    rule = {
        "id": "bound_renewal_notice",
        "title": "更新しない旨の申出の期限",
        "kind": "calculation",
        "origin": "bound",
        "interface": {"function": "renewal_notice_deadline"},
        "inputs": {
            "expiry_date": {
                "type": "date",
                "min": "2026-01-01",
                "max": "2033-12-31",
                "origin": "fact",
                "desc": "期間の満了日",
            }
        },
        "steps": [
            {
                "name": "notify_by",
                "label": "申出の期限（満了日の応当日。当日を含む）",
                "expr": {
                    "op": "add_months",
                    "args": [{"var": "expiry_date"}, {"op": "sub", "args": [{"lit": 0}, {"param": key}]}],
                },
            }
        ],
        "output": {"step": "notify_by", "type": "date"},
        "obligations": ["period_count:anniversary_inclusive_h5_approved"],
        "sources": [{"unit": uid, "quote": _quote_around(text, "前までに")}],
        "presentation": {"pattern": "B-RENEW", "placement": "bound"},
        "difficulty": {"calendar": "months", "origin": "bound"},
    }
    return BoundRule(binding="renewal_notice.deadline", params=params, units=[uid], rule=rule)


def _bind_liability_cap(idx, raw, uid, text):
    if "賠償" not in text or not re.search(r"上限とする|限度とする", text):
        return None
    caps: list[dict] = []
    params: dict[str, dict] = {}
    jpy_consts = [
        (k, s) for k, s in _consts_in_unit(idx, raw, uid) if read_value(s, "int", "JPY") is not None
    ]
    for k, s in jpy_consts:
        params[k] = {
            "type": "int",
            "unit": "JPY",
            "value": read_value(s, "int", "JPY"),
            "surface": s,
            "source": {"unit": uid, "quote": s},
        }
        caps.append({"param": k})
    inputs: dict[str, dict] = {
        "damage_amount": {
            "type": "int",
            "unit": "JPY",
            "min": 0,
            "max": 100000000,
            "origin": "judgment",
            "desc": "損害の額",
        }
    }
    if "契約金額" in text and "total_price" in idx.constants and "total_price" not in params:
        s = idx.constants["total_price"]
        value = read_value(s, "int", "JPY")
        if value is not None:
            src_units = idx.find_units_containing(s)
            params["total_price"] = {
                "type": "int",
                "unit": "JPY",
                "value": value,
                "surface": s,
                "source": {"unit": src_units[0] if src_units else uid, "quote": s},
            }
            caps.append({"param": "total_price"})
    if re.search(r"個別契約|注文書", text):
        inputs["order_fee"] = {
            "type": "int",
            "unit": "JPY",
            "min": 0,
            "max": 100000000,
            "origin": "order",
            "desc": "違反の原因となった個別契約の対価（委託料）の額",
        }
        caps.append({"var": "order_fee"})
    elif re.search(r"直近|年度", text):
        inputs["paid_fees_recent"] = {
            "type": "int",
            "unit": "JPY",
            "min": 0,
            "max": 1000000000,
            "origin": "fact",
            "desc": "条項の定める対象期間に支払われた対価の合計額",
        }
        caps.append({"var": "paid_fees_recent"})
    if not caps:
        return Excluded("liability_cap", uid, ["cap:上限の額を定数にも入力にも落とせない"])
    exception = "故意" in text
    steps = []
    cap_expr = caps[0] if len(caps) == 1 else {"op": "min", "args": caps}
    steps.append({"name": "cap", "label": "賠償の上限額", "expr": cap_expr})
    steps.append(
        {
            "name": "capped",
            "label": "上限を適用した額",
            "expr": {"op": "min", "args": [{"var": "damage_amount"}, {"step": "cap"}]},
        }
    )
    out_step = "capped"
    obligations = ["cap:stated_in_clause"]
    if exception:
        inputs["willful"] = {"type": "bool", "origin": "judgment", "desc": "故意または重大な過失があるか"}
        steps.append(
            {
                "name": "payable",
                "label": "賠償すべき額",
                "expr": {
                    "op": "if",
                    "args": [{"var": "willful"}, {"var": "damage_amount"}, {"step": "capped"}],
                },
            }
        )
        out_step = "payable"
        obligations.append("cap_exception:willful_or_gross_negligence")
    rule = {
        "id": "bound_liability_cap",
        "title": "損害賠償の限度",
        "kind": "calculation",
        "origin": "bound",
        "parties": {"payer": "違反当事者", "payee": "相手方"},
        "interface": {"function": "liability_limit"},
        "inputs": inputs,
        "steps": steps,
        "output": {"step": out_step, "type": "int", "unit": "JPY"},
        "obligations": obligations,
        "sources": [{"unit": uid, "quote": _quote_around(text, "上限" if "上限" in text else "限度")}],
        "presentation": {"pattern": "B-CAP", "placement": "bound"},
        "difficulty": {"depth": 2, "origin": "bound"},
    }
    return BoundRule(binding="liability_cap", params=params, units=[uid], rule=rule)


def _quote_around(text: str, anchor: str, width: int = 14) -> str:
    i = text.find(anchor)
    if i < 0:
        return text[:20]
    start = max(0, i - width)
    return text[start : i + len(anchor)]
