"""テストケースの生成（DESIGN.md §13.3・§13.4 の手順 1〜3・6）。

- 境界値：定数・表の境界の ±1、同じ単位の入力どうしの等しい場合、値域の端。
- 日付の境界（§10.3）：月末（28・29・30・31日）、うるう年の 2 月 29 日、年末年始、
  土日の前後。営業日を使うルールには、祝日なしと「結果の日が祝日」の両方。
- 不明値：入力を 1 つずつ None にする。
- 乱数：宣言した値域から。
期待値はすべて参照インタプリタで計算する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from random import Random

from ..spec.interp import eval_rule
from ..spec.model import BUSINESS_DAY_OPS, OPS_DATE, CalcSpec, Rule


@dataclass
class Case:
    case_id: str
    function: str
    kind: str  # example / boundary / unknown / random
    inputs: dict
    expected: object
    holidays: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "case_id": self.case_id,
            "function": self.function,
            "kind": self.kind,
            "inputs": self.inputs,
            "expected": self.expected,
        }
        if self.holidays:
            d["holidays"] = self.holidays
        if self.tags:
            d["tags"] = self.tags
        return d


#: §10.3 の日付の境界（タグ → 日付）。2027-10-31 は日曜、2026-10-31 は土曜。
_DATE_PROBES: tuple[tuple[str, str], ...] = (
    ("month_end_31", "2027-01-31"),
    ("month_end_30", "2027-04-30"),
    ("month_end_28", "2027-02-28"),
    ("leap_feb_29", "2028-02-29"),
    ("year_end", "2026-12-28"),
    ("saturday", "2026-10-31"),
    ("friday", "2026-10-30"),
)


def rule_params(rule: Rule) -> set[str]:
    """このルールの式が参照する定数名。"""
    out: set[str] = set()

    def walk(e) -> None:
        if not isinstance(e, dict):
            return
        if "param" in e:
            out.add(e["param"])
        for a in e.get("args", []):
            walk(a)
        for k in ("filter", "map"):
            if k in e:
                walk(e[k])

    for s in rule.steps:
        walk(s.expr)
    return out


def rule_ops(rule: Rule) -> set[str]:
    ops: set[str] = set()

    def walk(e) -> None:
        if not isinstance(e, dict):
            return
        if "op" in e:
            ops.add(e["op"])
        for a in e.get("args", []):
            walk(a)
        for k in ("filter", "map"):
            if k in e:
                walk(e[k])

    for s in rule.steps:
        walk(s.expr)
    return ops


def build_cases(
    spec: CalcSpec, rule: Rule, rng: Random, n_random: int = 12, hints: list[dict] | None = None
) -> list[Case]:
    cases: list[Case] = []
    counter = {"n": 0}

    def add(
        kind: str, inputs: dict, holidays: list[str] | None = None, tags: list[str] | None = None
    ) -> None:
        hol = frozenset(date.fromisoformat(h) for h in (holidays or []))
        expected = eval_rule(spec, rule, dict(inputs), hol)
        counter["n"] += 1
        cases.append(
            Case(
                case_id=f"{rule.id}:{kind[0]}{counter['n']:03d}",
                function=rule.function,
                kind=kind,
                inputs=dict(inputs),
                expected=_jsonable(expected),
                holidays=list(holidays or []),
                tags=list(tags or []),
            )
        )

    base = _default_inputs(rule, rng)
    ops = rule_ops(rule)
    uses_business = bool(ops & BUSINESS_DAY_OPS)
    uses_dates = bool(ops & OPS_DATE) or any(d.type == "date" for d in rule.inputs.values())

    # --- 1 境界値（定数・表キーの ±1、同じ単位の入力どうし、値域の端） -------------------
    int_inputs = {n: d for n, d in rule.inputs.items() if d.type == "int"}
    anchors: dict[str, list[int]] = {n: [] for n in int_inputs}
    used = rule_params(rule)
    for pname, p in spec.params.items():
        if p.type != "int" or pname not in used:
            continue
        for n, decl in int_inputs.items():
            if decl.unit == p.unit:
                anchors[n].append(p.value)
    for t in spec.tables.values():
        for row in t.rows:
            if row.upto is None:
                continue
            for n, decl in int_inputs.items():
                if decl.unit in ("COUNT", "JPY"):
                    anchors[n].append(row.upto)
    lows = {n: (d.min if d.min is not None else 0) for n, d in int_inputs.items()}
    for n, decl in int_inputs.items():
        lo = lows[n]
        hi = decl.max if decl.max is not None else 10**6
        values = {lo, hi}
        for a in anchors[n]:
            values.update({a - 1, a, a + 1})
        others_lo = {m: lows[m] for m in int_inputs if m != n}
        for v in sorted(v for v in values if lo <= v <= hi):
            add("boundary", {**base, n: v}, tags=[f"anchor:{n}"])
            if others_lo:
                # 他の同種の入力に埋もれて境界が見えなくなるのを防ぐ（他入力を下限に置いた変種）
                add("boundary", {**base, **others_lo, n: v}, tags=[f"anchor:{n}", "others_lo"])
    # 明細（list）の境界：ルールが使う同じ単位の定数から 1 要素・2 要素の明細を作る
    for n, decl in rule.inputs.items():
        if decl.type != "list":
            continue
        jpy_params = [
            p.value
            for pname, p in spec.params.items()
            if pname in used and p.type == "int" and p.unit == (decl.item_unit or "JPY")
        ]
        for a in jpy_params:
            for v in (a - 1, a, a + 1):
                add("boundary", {**base, n: [v]}, tags=[f"list_anchor:{n}"])
        for i, a in enumerate(jpy_params):
            for b in jpy_params[i + 1 :]:
                for delta in (-1, 0, 1):
                    add("boundary", {**base, n: [a + delta, b]}, tags=[f"list_anchor:{n}"])
                # 和の境界（累計の上限・しきい値を単独の要素で踏むため）
                for delta in (-1, 0, 1):
                    add("boundary", {**base, n: [a + b + delta]}, tags=[f"list_anchor:{n}", "sum"])
        add("boundary", {**base, n: []}, tags=[f"list_anchor:{n}", "empty"])

    # 同じ単位の int 入力どうし：等しい場合
    names = list(int_inputs)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            if int_inputs[a].unit == int_inputs[b].unit:
                add("boundary", {**base, b: base[a]}, tags=[f"equal:{a}={b}"])
    # bool / enum の全列挙（判定ルール。入力 6 個までに制限）
    bool_names = [n for n, d in rule.inputs.items() if d.type == "bool"]
    if bool_names and len(bool_names) <= 6:
        int_probe_values = _int_anchor_probe(spec, rule, base)
        for mask in range(2 ** len(bool_names)):
            combo = {n: bool(mask >> i & 1) for i, n in enumerate(bool_names)}
            for probe in int_probe_values:
                add("boundary", {**base, **combo, **probe}, tags=["bool_combo"])

    # --- 2 日付の境界 -------------------------------------------------------------
    date_inputs = [n for n, d in rule.inputs.items() if d.type == "date"]
    if uses_dates and date_inputs:
        for n in date_inputs:
            for tag, probe in _DATE_PROBES:
                inputs = {**base, n: probe}
                add("boundary", inputs, tags=[f"date:{tag}"])
                if uses_business:
                    # 結果の日を祝日にして、営業日の調整が 1 日ずれることを確かめる
                    got = eval_rule(spec, rule, dict(inputs))
                    if isinstance(got, date):
                        add("boundary", inputs, holidays=[got.isoformat()], tags=[f"date:{tag}", "holiday"])
        # 日付の入力どうし：同じ日・前後 1 日と、ルールが使う日数の定数の ±1
        if len(date_inputs) >= 2:
            a, b = date_inputs[0], date_inputs[1]
            d0 = date.fromisoformat(base[a])
            deltas: set[int] = {0, 1, -1}
            for pname, p in spec.params.items():
                if pname in used and p.type == "int" and p.unit == "DAY":
                    deltas.update({p.value - 1, p.value, p.value + 1})
            bool_names_all = [n for n, d in rule.inputs.items() if d.type == "bool"]
            all_true = {n: True for n in bool_names_all}
            for delta in sorted(deltas):
                inputs = {**base, b: (d0 + timedelta(days=delta)).isoformat()}
                add("boundary", inputs, tags=[f"date:delta{delta}"])
                if all_true:
                    # 真偽の既定（偽）に判定が隠れないよう、すべて真にした変種も置く
                    add("boundary", {**inputs, **all_true}, tags=[f"date:delta{delta}", "bools_true"])

    # --- パターンが指定した境界入力（しきい値を正確に踏むためのヒント） -----------------
    for hint in hints or ():
        add("boundary", {**base, **hint}, tags=["hint"])

    # --- 3 不明値 -----------------------------------------------------------------
    for n in rule.inputs:
        add("unknown", {**base, n: None}, tags=[f"none:{n}"])

    # --- 6 乱数 -------------------------------------------------------------------
    for _ in range(n_random):
        add("random", _sample_inputs(rule, rng))

    return cases


def _int_anchor_probe(spec: CalcSpec, rule: Rule, base: dict) -> list[dict]:
    """bool 全列挙に添える int 入力の揺らし（このルールが使う定数の ±1。なければ既定のみ）。"""
    used = rule_params(rule)
    for n, decl in rule.inputs.items():
        if decl.type != "int":
            continue
        lo = decl.min if decl.min is not None else 0
        hi = decl.max if decl.max is not None else 10**6
        for pname, p in spec.params.items():
            if pname in used and p.type == "int" and p.unit == decl.unit:
                vals = [max(lo, p.value - 1), p.value, min(hi, p.value + 1)]
                return [{n: v} for v in vals]
    return [{}]


def _default_inputs(rule: Rule, rng: Random) -> dict:
    """境界値ケースの土台（中庸の値。決定的）。"""
    out: dict = {}
    for name, decl in rule.inputs.items():
        if decl.type == "int":
            lo = decl.min if decl.min is not None else 0
            hi = decl.max if decl.max is not None else 10**6
            out[name] = (lo + hi) // 2
        elif decl.type == "bool":
            out[name] = False
        elif decl.type == "date":
            out[name] = "2027-06-15"  # 平日（火曜）・月中
        elif decl.type == "list":
            out[name] = [200_000, 1_200_000]
        elif decl.type == "enum":
            out[name] = decl.values[0]
    return out


def _sample_inputs(rule: Rule, rng: Random) -> dict:
    out = {}
    for name, decl in rule.inputs.items():
        if decl.type == "int":
            lo = decl.min if decl.min is not None else 0
            hi = decl.max if decl.max is not None else 10**6
            out[name] = rng.randint(lo, hi)
        elif decl.type == "bool":
            out[name] = rng.choice([True, False])
        elif decl.type == "date":
            lo = date.fromisoformat(decl.min or "2026-01-01")
            hi = date.fromisoformat(decl.max or "2031-12-31")
            out[name] = (lo + timedelta(days=rng.randint(0, (hi - lo).days))).isoformat()
        elif decl.type == "list":
            out[name] = [rng.randint(0, 2_000_000) for _ in range(rng.randint(0, 6))]
        elif decl.type == "enum":
            out[name] = rng.choice(list(decl.values))
    return out


def _jsonable(v):
    return v.isoformat() if isinstance(v, date) else v
