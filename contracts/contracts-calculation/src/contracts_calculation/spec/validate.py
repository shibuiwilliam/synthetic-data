"""計算仕様の検査（G1 と G3 の仕様側）。

- 構造：演算が閉じた集合に入っている、引数の数、必須属性（rounding など）。
- 参照：var → 宣言済み入力、param → params、step → それより前の手順、table → tables。
  前方参照と循環は手順の並びで構造的に禁止される。
- 型と単位：加減・比較は同じ単位どうし。float はどこにも書けない。
- 明示性：使った演算が要求する明示事項（rounding、tier_method など）が obligations にある。
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import (
    ALL_OPS,
    BUSINESS_DAY_OPS,
    INPUT_ORIGINS,
    OBLIGATION_BY_OP,
    ROUNDINGS,
    VALUE_TYPES,
    CalcSpec,
    Rule,
)


@dataclass(frozen=True)
class Issue:
    """検査の指摘。severity は error のみ（warn は使わない。落ちるか通るか）。"""

    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


def validate_spec(spec: CalcSpec) -> list[Issue]:
    """仕様全体を検査し、指摘の一覧を返す（空なら合格）。"""
    issues: list[Issue] = []
    _check_no_float(spec, issues)
    _check_params(spec, issues)
    _check_tables(spec, issues)
    seen_functions: set[str] = set()
    seen_rule_ids: set[str] = set()
    for rule in spec.rules:
        if rule.id in seen_rule_ids:
            issues.append(Issue(rule.id, "ルール ID が重複している"))
        seen_rule_ids.add(rule.id)
        fn = rule.interface.get("function")
        if not fn:
            issues.append(Issue(rule.id, "interface.function が無い"))
        elif fn in seen_functions:
            issues.append(Issue(rule.id, f"関数名 {fn} が重複している"))
        else:
            seen_functions.add(fn)
        issues.extend(_validate_rule(spec, rule))
    return issues


def assert_valid(spec: CalcSpec) -> None:
    issues = validate_spec(spec)
    if issues:
        raise ValueError("仕様の検査に失敗した:\n" + "\n".join(f"  - {i}" for i in issues))


# --- 内部 ---------------------------------------------------------------------


def _check_no_float(obj, issues: list[Issue], where: str = "spec") -> None:
    if isinstance(obj, float):
        issues.append(Issue(where, f"float が使われている: {obj}（金額は整数の円、割合は分子と分母）"))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _check_no_float(v, issues, f"{where}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _check_no_float(v, issues, f"{where}[{i}]")
    elif hasattr(obj, "__dataclass_fields__"):
        for name in obj.__dataclass_fields__:
            _check_no_float(getattr(obj, name), issues, f"{where}.{name}")


def _check_params(spec: CalcSpec, issues: list[Issue]) -> None:
    for name, p in spec.params.items():
        if p.type not in VALUE_TYPES:
            issues.append(Issue(f"params.{name}", f"未知の型: {p.type}"))
        if p.type == "ratio":
            if not (isinstance(p.num, int) and isinstance(p.den, int) and p.den > 0):
                issues.append(Issue(f"params.{name}", "ratio は整数の num と正の den を持つ"))
        elif p.type == "int":
            if not isinstance(p.value, int) or isinstance(p.value, bool):
                issues.append(Issue(f"params.{name}", "int の value が整数でない"))
        elif p.type == "date" and not isinstance(p.value, str):
            issues.append(Issue(f"params.{name}", "date の value は YYYY-MM-DD の文字列"))
        if p.source is None:
            issues.append(Issue(f"params.{name}", "根拠（source）の無い数値（契約書のどこにあるかを指す）"))


def _check_tables(spec: CalcSpec, issues: list[Issue]) -> None:
    for name, t in spec.tables.items():
        if t.kind not in ("tiers", "map"):
            issues.append(Issue(f"tables.{name}", f"未知の kind: {t.kind}"))
        if not t.rows:
            issues.append(Issue(f"tables.{name}", "行が無い"))
            continue
        if t.kind == "tiers":
            uptos = [r.upto for r in t.rows]
            if uptos[-1] is not None:
                issues.append(Issue(f"tables.{name}", "最終行の upto は null（それ以上すべて）にする"))
            finite = [u for u in uptos if u is not None]
            if any(u is None for u in uptos[:-1]):
                issues.append(Issue(f"tables.{name}", "upto=null は最終行だけに置く"))
            if finite != sorted(finite) or len(set(finite)) != len(finite):
                issues.append(Issue(f"tables.{name}", "段階の境界は昇順・重複なし"))
        if t.source is None:
            issues.append(Issue(f"tables.{name}", "根拠（source）の無い表"))


def _validate_rule(spec: CalcSpec, rule: Rule) -> list[Issue]:
    issues: list[Issue] = []
    w = f"rules.{rule.id}"
    if rule.kind not in ("calculation", "determination"):
        issues.append(Issue(w, f"未知の kind: {rule.kind}"))
    for name, decl in rule.inputs.items():
        if decl.type not in VALUE_TYPES:
            issues.append(Issue(f"{w}.inputs.{name}", f"未知の型: {decl.type}"))
        if decl.origin not in INPUT_ORIGINS:
            issues.append(Issue(f"{w}.inputs.{name}", f"未知の出どころ: {decl.origin}"))
        if decl.type == "int" and decl.min is not None and decl.max is not None and decl.min > decl.max:
            issues.append(Issue(f"{w}.inputs.{name}", "min > max"))

    step_names: set[str] = set()
    used_ops: set[str] = set()
    for step in rule.steps:
        if step.name in step_names:
            issues.append(Issue(f"{w}.steps.{step.name}", "手順名が重複している"))
        _walk_expr(
            spec,
            rule,
            step.expr,
            allowed_steps=frozenset(step_names),
            in_agg=False,
            used_ops=used_ops,
            issues=issues,
            where=f"{w}.steps.{step.name}",
        )
        step_names.add(step.name)

    out_step = rule.output.get("step")
    if out_step not in step_names:
        issues.append(Issue(f"{w}.output", f"出力の手順が無い: {out_step}"))

    # 明示性（G3 の仕様側）：使った演算が要求する明示事項が宣言されているか。
    # challenge モードで意図的に欠落させた事項（rule.challenge.aspect）はラベルで記録済みのため免除する
    obligation_keys = {o.split(":", 1)[0] for o in rule.obligations}
    challenged_aspect = (rule.challenge or {}).get("aspect")
    for op in sorted(used_ops):
        required = OBLIGATION_BY_OP.get(op)
        if required and required not in obligation_keys and required != challenged_aspect:
            issues.append(
                Issue(w, f"演算 {op} を使うなら obligations に {required}:... を宣言する（明示性）")
            )
    # 営業日の演算には暦の宣言が要る
    if used_ops & BUSINESS_DAY_OPS and spec.calendar is None:
        issues.append(Issue(w, "営業日の演算を使うなら spec.calendar を宣言する"))
    # 金銭の向き：金額を返す計算は当事者を持つ
    if rule.kind == "calculation" and rule.output.get("unit") == "JPY" and not rule.parties:
        issues.append(Issue(w, "金額を返すルールは parties（支払う側と受け取る側）を持つ"))
    return issues


def _walk_expr(
    spec: CalcSpec,
    rule: Rule,
    expr,
    *,
    allowed_steps: frozenset[str],
    in_agg: bool,
    used_ops: set[str],
    issues: list[Issue],
    where: str,
) -> None:
    if not isinstance(expr, dict):
        issues.append(Issue(where, f"式は dict で書く: {expr!r}"))
        return
    leaf_keys = {"lit", "var", "param", "step", "item"} & expr.keys()
    if leaf_keys:
        key = leaf_keys.pop()
        if key == "lit":
            v = expr["lit"]
            if isinstance(v, float):
                issues.append(Issue(where, "lit に float は書けない"))
        elif key == "var":
            if expr["var"] not in rule.inputs:
                issues.append(Issue(where, f"未宣言の入力: {expr['var']}"))
        elif key == "param":
            if expr["param"] not in spec.params:
                issues.append(Issue(where, f"未宣言の定数: {expr['param']}"))
        elif key == "step":
            if expr["step"] not in allowed_steps:
                issues.append(Issue(where, f"前方参照か未定義の手順: {expr['step']}（循環は書けない）"))
        elif key == "item":
            if not in_agg:
                issues.append(Issue(where, "item は agg の filter / map の中でだけ使える"))
        return

    op = expr.get("op")
    if op is None:
        issues.append(Issue(where, f"op が無い: {expr!r}"))
        return
    if op not in ALL_OPS:
        issues.append(Issue(where, f"未知の演算: {op}（§12.2 の閉じた集合だけが書ける）"))
        return
    used_ops.add(op)
    args = expr.get("args", [])

    arity = {
        "sub": 2,
        "muldiv": 3,
        "round_to": 1,
        "not": 1,
        "if": 3,
        "lt": 2,
        "le": 2,
        "gt": 2,
        "ge": 2,
        "eq": 2,
        "ne": 2,
        "add_days": 2,
        "add_months": 2,
        "end_of_month": 1,
        "set_day": 2,
        "period_end": 2,
        "days_between": 2,
        "days_in_month": 1,
        "is_business_day": 1,
        "next_business_day": 1,
        "prev_business_day": 1,
        "add_business_days": 2,
        "lookup": 1,
        "tiered": 1,
    }
    if op in arity and len(args) != arity[op]:
        issues.append(Issue(where, f"{op} の引数は {arity[op]} 個（{len(args)} 個ある）"))
    if op in ("add", "mul", "min", "max", "and", "or", "coalesce") and len(args) < 2:
        issues.append(Issue(where, f"{op} の引数は 2 個以上"))

    if op in ("muldiv", "round_to") and expr.get("rounding") not in ROUNDINGS:
        issues.append(Issue(where, f"{op} は rounding（floor / ceil / half_up）を必ず指定する"))
    if op == "round_to" and not (isinstance(expr.get("unit_value"), int) and expr.get("unit_value", 0) > 0):
        issues.append(Issue(where, "round_to は正の整数 unit_value を持つ"))
    if op == "period_end":
        if expr.get("unit") not in ("day", "month", "year"):
            issues.append(Issue(where, "period_end は unit（day / month / year）を持つ"))
        if not isinstance(expr.get("include_start"), bool):
            issues.append(Issue(where, "period_end は include_start（初日を数えるか）を必ず明示する"))
    if op in ("lookup", "tiered"):
        table = expr.get("table")
        if table not in spec.tables:
            issues.append(Issue(where, f"未宣言の表: {table}"))
        if op == "tiered" and expr.get("method") not in ("all_units", "marginal"):
            issues.append(Issue(where, "tiered は method（all_units / marginal）を必ず明示する"))
        if op == "lookup" and expr.get("mode") not in ("exact", "step"):
            issues.append(Issue(where, "lookup は mode（exact / step）を持つ"))
    if op == "case" and (len(args) < 3 or len(args) % 2 == 0):
        issues.append(Issue(where, "case の引数は [条件, 値]... ＋ 既定値（奇数個）"))
    if op == "agg":
        if expr.get("mode") not in ("sum", "max", "min", "count", "any", "all"):
            issues.append(Issue(where, "agg は mode（sum / max / min / count / any / all）を持つ"))
        over = expr.get("over")
        if over not in rule.inputs or rule.inputs[over].type != "list":
            issues.append(Issue(where, f"agg の over は list 型の入力を指す: {over}"))
        for sub_key in ("filter", "map"):
            if sub_key in expr:
                _walk_expr(
                    spec,
                    rule,
                    expr[sub_key],
                    allowed_steps=allowed_steps,
                    in_agg=True,
                    used_ops=used_ops,
                    issues=issues,
                    where=f"{where}.{sub_key}",
                )

    for i, a in enumerate(args):
        _walk_expr(
            spec,
            rule,
            a,
            allowed_steps=allowed_steps,
            in_agg=in_agg,
            used_ops=used_ops,
            issues=issues,
            where=f"{where}.args[{i}]",
        )
