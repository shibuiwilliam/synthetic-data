"""検証ゲート G1〜G12 の実装（DESIGN.md §14）。

G7（テストの十分性）と G8（暦の網羅）は、変異の測定結果とケースが渡されたときに判定する。
渡されていなければ黙って通さず skipped と明記する。G13（解答可能性）は任意で、`eval` CLI で測る。
"""

from __future__ import annotations

import random
import re
import types
from dataclasses import dataclass
from datetime import date, timedelta

from ..docmodel.index import DocumentIndex
from ..docmodel.numbers_ja import read_value
from ..spec.interp import eval_rule
from ..spec.model import BUSINESS_DAY_OPS, CalcSpec
from ..spec.validate import validate_spec


@dataclass
class GateResult:
    gate: str
    passed: bool
    skipped: bool = False
    detail: str = ""

    def to_dict(self) -> dict:
        return {"gate": self.gate, "passed": self.passed, "skipped": self.skipped, "detail": self.detail}


#: 明示事項のキー → 追加した文言に現れるべき言い回し（G3）
OBLIGATION_PHRASES: dict[str, str] = {
    "rounding": r"切り捨て|切り上げ|四捨五入",
    "tier_method": r"全件数に乗じて|全件数を乗じて|合計",
    "tier_boundary": r"下位の区分",
    "business_days": r"「営業日」とは",
    "holiday_adjust": r"営業日でないとき",
    "day_count": r"翌日から|前日まで|までの日数",
    "proration_basis": r"日割|割合",
    "period_count": r"初日を含む|応当日|前まで",
    "free_quota": r"超える部分|超えたとき",
    "band": r"満たないとき.*控除",
    "cap": r"超えない|限度とする|上限",
    "cap_period": r"前日までの",
    "cap_exception": r"故意(?:または重大な過失|または重過失|により|による|の場合)",
    "floor_then_cap": r"下回らず",
    "beyond_penalty": r"妨げない",
    "value_location": r"個別契約に定める",
    "deemed": r"みなす",
    "notice": r"到達",
    "tax": r"含まない",
    "year_basis": r"1年を|１年を|年[0-9０-９]+日の日割(?:り|計算)",
    "included": r"含む定額|までを含む",
    "over_hours": r"超える",
    "cure_period": r"経過して",
    "demand": r"書面により(?:催告|請求)|書面による請求",
    "definition": r"」とは",
    "exclusions": r"含まれない",
    "share": r"負担",
    "scenario": r".",
    "worst_case": r".",
    "source": r".",
    "crosscheck": r".",
    "payday": r"までに",
    "loss_cap": r"負担",
    "minimum": r"満たないとき|満たない場合",
    "basket": r"超える部分に限り|全額",
    "de_minimis": r"満たない損害を除き|満たないものを除き",
    "uptime": r"双方から除く|除いた時間",
    "ratio_compare": r"乗算|乗じて比較",
    "index": r"指数",
    "survival": r"存続",
    "min_purchase": r"最低|下回ったとき",
    "settlement": r"差し引いた|控除した",
    "priority": r"優先|別紙による|別紙の定めによる",
    "procedure": r"のとおり",
    "forfeiture": r"期限の利益",
    "force_majeure": r"不可抗力",
    "notice_deadline": r"以内に.*通知",
    "rebate": r"割戻",
    "warranty": r"保証",
    "discount": r"値引|割り引",
    "floor_zero": r"負となるとき|返還は要しない|[0０]円を下回る",
}


def run_gates(
    spec_dict: dict,
    idx: DocumentIndex,
    added_units: set[str],
    module_src: str,
    toolchain: dict[str, bool],
    cases_by_rule: dict[str, list] | None = None,
    mutation_by_rule: dict[str, dict] | None = None,
    units_by_rule: dict[str, list[str]] | None = None,
) -> list[GateResult]:
    """生成済みの 1 文書についてゲートを実行する。toolchain は G10 の実行結果（lint/build/render）。"""
    spec = CalcSpec.from_dict(spec_dict)
    results: list[GateResult] = []
    added_text = "\n".join(idx.units[u].text for u in sorted(added_units) if u in idx.units)

    # G1 仕様の検査
    issues = validate_spec(spec)
    results.append(GateResult("G1", not issues, detail="; ".join(str(i) for i in issues)[:500]))

    # G2 根拠の照合（引用が単位に逐語で存在する）
    bad: list[str] = []
    for name, p in spec.params.items():
        if p.source and not idx.quote_in_unit(p.source.unit, p.source.quote):
            bad.append(f"params.{name}@{p.source.unit}")
    for name, t in spec.tables.items():
        if t.source and not idx.quote_in_unit(t.source.unit, t.source.quote):
            bad.append(f"tables.{name}@{t.source.unit}")
    if (
        spec.calendar
        and spec.calendar.source
        and not idx.quote_in_unit(spec.calendar.source.unit, spec.calendar.source.quote)
    ):
        bad.append(f"calendar@{spec.calendar.source.unit}")
    for rule in spec.rules:
        for s in rule.sources:
            if not idx.quote_in_unit(s.unit, s.quote):
                bad.append(f"{rule.id}@{s.unit}")
    results.append(GateResult("G2", not bad, detail=", ".join(bad)[:500]))

    # G3 明示性（明示事項に対応する文が、そのルールの根拠単位にある）
    missing: list[str] = []
    for rule in spec.rules:
        if units_by_rule and rule.id in units_by_rule:
            scope_text = "\n".join(idx.units[u].text for u in units_by_rule[rule.id] if u in idx.units)
        else:
            scope_text = added_text
        for ob in rule.obligations:
            key = ob.split(":", 1)[0]
            pattern = OBLIGATION_PHRASES.get(key)
            if pattern is None:
                missing.append(f"{rule.id}:{ob}（検査語未定義）")
            elif not re.search(pattern, scope_text):
                missing.append(f"{rule.id}:{ob}")
    results.append(GateResult("G3", not missing, detail=", ".join(missing)[:500]))

    # G4 数値の往復（表記 → 値、meta.constants の宣言）
    bad4: list[str] = []
    for name, p in spec.params.items():
        meta_surface = idx.constants.get(name)
        if meta_surface is None:
            # inline（文中の語そのもの）。根拠単位に表記があり、値に読み戻せること
            if p.source and idx.quote_in_unit(p.source.unit, p.surface or ""):
                got = read_value(p.surface or "", p.type, p.unit)
                ok = bool(got and got[0] * p.den == p.num * got[1]) if p.type == "ratio" else got == p.value
                if not ok:
                    bad4.append(f"{name}: inline 表記 {p.surface!r} が値に読み戻せない")
            else:
                bad4.append(f"{name}: meta.constants にも根拠単位にも無い")
            continue
        if p.surface != meta_surface:
            bad4.append(f"{name}: 表記が一致しない（{p.surface!r} ≠ {meta_surface!r}）")
            continue
        got = read_value(p.surface, p.type, p.unit)
        if p.type == "ratio":
            if not (got and got[0] * p.den == p.num * got[1]):
                bad4.append(f"{name}: {p.surface!r} → {got} ≠ {p.num}/{p.den}")
        elif got != p.value:
            bad4.append(f"{name}: {p.surface!r} → {got} ≠ {p.value}")
    for tname, t in spec.tables.items():
        for i, row in enumerate(t.rows):
            cell_id = t.source.unit.rsplit("__", 1)[0] + f"__r{i + 1}c1" if t.source else None
            if cell_id and cell_id in idx.units:
                cell_unit = "PERMILLE" if (t.unit or "").startswith("PERMILLE") else "JPY"
                got = read_value(idx.units[cell_id].text, "int", cell_unit)
                if got != row.value:
                    bad4.append(f"{tname}[{i}]: セル {cell_id} → {got} ≠ {row.value}")
    results.append(GateResult("G4", not bad4, detail=", ".join(bad4)[:500]))

    # G5 設例の一致（仕様内の設例があれば interp で検算）
    bad5: list[str] = []
    example_count = 0
    for rule in spec.rules:
        for i, ex in enumerate(rule.examples):
            example_count += 1
            holidays = frozenset(date.fromisoformat(h) for h in ex.holidays)
            got = eval_rule(spec, rule, dict(ex.inputs), holidays)
            expect = ex.expect
            if rule.output.get("type") == "date" and isinstance(expect, str):
                expect = date.fromisoformat(expect)
            if got != expect:
                bad5.append(f"{rule.id}:ex{i}")
    results.append(
        GateResult("G5", not bad5, detail=", ".join(bad5) or f"仕様内設例 {example_count} 件を検算")
    )

    # G6 実装の一致（参照インタプリタと生成した Python が一致する）
    mod = types.ModuleType("generated_check")
    exec(compile(module_src, "<generated>", "exec"), mod.__dict__)  # noqa: S102 — 生成した正解プログラムの検査に必要
    bad6: list[str] = []
    for rule in spec.rules:
        fn = getattr(mod, rule.function, None)
        if fn is None:
            bad6.append(f"{rule.id}: 関数が無い")
            continue
        rng = random.Random(f"g6:{rule.id}")
        uses_cal = _uses_calendar(rule)
        for _ in range(20):
            inputs = _sample_inputs(rule, rng)
            kwargs = _to_kwargs(rule, inputs)
            if uses_cal:
                kwargs["holidays"] = frozenset()
            if fn(**kwargs) != eval_rule(spec, rule, dict(inputs)):
                bad6.append(f"{rule.id}: {inputs}")
                break
    results.append(GateResult("G6", not bad6, detail=", ".join(bad6)[:500]))

    # G7 テストの十分性（変異をすべて検出する。検出できない変異は理由つきで記録される）
    if mutation_by_rule is None:
        results.append(GateResult("G7", True, skipped=True, detail="変異の測定が渡されていない"))
    else:
        bad7: list[str] = []
        total = detected = 0
        for rid, rep in mutation_by_rule.items():
            total += rep["total"]
            detected += rep["detected"]
            for u in rep["undetected"]:
                bad7.append(f"{rid}:{u['mutant']}")
        results.append(
            GateResult(
                "G7",
                not bad7,
                detail=f"変異 {detected}/{total} 検出" + ("; 未検出: " + ", ".join(bad7) if bad7 else ""),
            )
        )

    # G8 暦の網羅（日付を扱うルールのケースに §10.3 の日付が含まれる）
    if cases_by_rule is None:
        results.append(GateResult("G8", True, skipped=True, detail="ケースが渡されていない"))
    else:
        from ..spec.model import OPS_DATE
        from ..testgen.cases import rule_ops

        bad8: list[str] = []
        required = {"date:month_end_31", "date:month_end_28", "date:leap_feb_29", "date:year_end"}
        for rule in spec.rules:
            has_date_input = any(d.type == "date" for d in rule.inputs.values())
            if not (rule_ops(rule) & OPS_DATE and has_date_input):
                continue
            tags = {t for c in cases_by_rule.get(rule.id, []) for t in c.tags}
            missing_tags = required - tags
            if missing_tags:
                bad8.append(f"{rule.id}: {sorted(missing_tags)}")
            if rule_ops(rule) & BUSINESS_DAY_OPS and "holiday" not in tags:
                bad8.append(f"{rule.id}: 祝日ありのケースが無い")
        results.append(GateResult("G8", not bad8, detail=", ".join(bad8)[:500]))

    # G9 衝突なし（定数の重複宣言はパッチ時に停止済み。追加モードの定数の表記が本文に 1 回だけ現れること）
    from ..testgen.cases import rule_params

    added_param_names: set[str] = set()
    for rule in spec.rules:
        if rule.origin == "added":
            added_param_names |= rule_params(rule)
    dup: list[str] = []
    para_text_units = [u for u in added_units if "__r" not in u and u in idx.units]
    for name, p in spec.params.items():
        if name not in added_param_names:
            continue
        count = sum(_count_surface(idx.units[u].text, p.surface) for u in para_text_units)
        if count != 1:
            dup.append(f"{name}: 本文中の出現が {count} 回（1 回であること）")
    results.append(GateResult("G9", not dup, detail=", ".join(dup)[:500]))

    # G10 本体の検査（lint / build / render の成否。実行はパイプライン側）
    failed = [k for k, ok in toolchain.items() if not ok]
    results.append(GateResult("G10", not failed, detail=", ".join(failed)))

    # G11 発見可能性：根拠単位が、言い回しによる検出で拾えるか（拾えない単位は記録する）
    cues = re.compile(
        r"円|％|%|パーセント|割|日|か月|年|時間|乗じ|加算|控除|合計|上限|下限|限度|超え|満たない|"
        r"以内|までに|みなす|該当|端数|営業日|数量|単価"
    )
    unfound: list[str] = []
    if units_by_rule:
        for rule in spec.rules:
            for u in units_by_rule.get(rule.id, []):
                if u in idx.units and not cues.search(idx.units[u].text):
                    unfound.append(f"{rule.id}:{u}")
    results.append(
        GateResult(
            "G11",
            True,
            detail=("拾えない単位: " + ", ".join(unfound))[:400]
            if unfound
            else "全単位が言い回しで検出できる",
        )
    )
    return results


def _count_surface(text: str, surface: str) -> int:
    """数字の途中から始まる偶然の一致（「１５万円」の中の「５万円」）を数えない出現計数。"""
    pat = re.compile(r"(?<![0-9０-９,，.．])" + re.escape(surface))
    return len(pat.findall(text))


# --- G6 用の入力サンプリング -------------------------------------------------------


def _uses_calendar(rule) -> bool:
    from ..codegen.python import _collect_ops

    ops: set[str] = set()
    _collect_ops(rule, ops)
    return bool(ops & BUSINESS_DAY_OPS)


def _to_kwargs(rule, inputs: dict) -> dict:
    out = {}
    for name, decl in rule.inputs.items():
        v = inputs.get(name)
        if v is not None and decl.type == "date" and isinstance(v, str):
            v = date.fromisoformat(v)
        out[name] = v
    return out


def _sample_inputs(rule, rng: random.Random) -> dict:
    inputs = {}
    for name, decl in rule.inputs.items():
        if decl.type == "int":
            lo = decl.min if decl.min is not None else 0
            hi = decl.max if decl.max is not None else 1000
            inputs[name] = rng.randint(lo, hi)
        elif decl.type == "bool":
            inputs[name] = rng.choice([True, False])
        elif decl.type == "date":
            lo = date.fromisoformat(decl.min or "2026-01-01")
            hi = date.fromisoformat(decl.max or "2031-12-31")
            inputs[name] = (lo + timedelta(days=rng.randint(0, (hi - lo).days))).isoformat()
        elif decl.type == "list":
            inputs[name] = [rng.randint(0, 2_000_000) for _ in range(rng.randint(0, 6))]
        elif decl.type == "enum":
            inputs[name] = rng.choice(list(decl.values))
    return inputs
