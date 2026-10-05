"""変異によるテストの十分性の測定（DESIGN.md §13.4-4・5、ゲート G7）。

仕様を 1 箇所だけ壊した変異をすべて作り、生成したケースがすべての変異を検出できるかを測る。
検出できない変異は乱数で検出できる入力を探して足す。それでも見つからない変異は、
理由を記録する（静的に式へ現れない定数の変異は、最初から作らず理由を記録する）。
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import date
from random import Random

from ..spec.interp import eval_rule
from ..spec.model import CalcSpec, Rule
from .cases import Case, _jsonable, _sample_inputs

_CMP_SWAP = {"lt": "le", "le": "lt", "gt": "ge", "ge": "gt"}
_MINMAX_SWAP = {"min": "max", "max": "min"}
_LOGIC_SWAP = {"and": "or", "or": "and"}
_ROUND_SWAP = {"floor": "ceil", "ceil": "floor", "half_up": "floor"}
_BUSINESS_SWAP = {"prev_business_day": "next_business_day", "next_business_day": "prev_business_day"}
_TIER_SWAP = {"all_units": "marginal", "marginal": "all_units"}


@dataclass
class Mutant:
    mutant_id: str
    description: str
    spec: CalcSpec

    def __repr__(self) -> str:  # 診断用
        return f"Mutant({self.mutant_id}: {self.description})"


@dataclass
class MutationReport:
    total: int
    detected: int
    added_cases: int
    undetected: list[dict] = field(default_factory=list)  # {mutant, description, reason}
    skipped: list[dict] = field(default_factory=list)  # 最初から作らない変異（静的な理由つき）

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "detected": self.detected,
            "added_cases": self.added_cases,
            "undetected": self.undetected,
            "skipped": self.skipped,
        }


def enumerate_mutants(spec_dict: dict, rule_id: str) -> tuple[list[Mutant], list[dict]]:
    """1 ルール分の変異と、作らなかった変異（理由つき）を返す。"""
    mutants: list[Mutant] = []
    skipped: list[dict] = []
    rule_dict = next(r for r in spec_dict["rules"] if r["id"] == rule_id)
    challenge_aspect = (rule_dict.get("challenge") or {}).get("aspect")
    used_params: set[str] = set()
    _collect_params(rule_dict["steps"], used_params)
    used_by_others: set[str] = set()
    for r in spec_dict["rules"]:
        if r["id"] != rule_id:
            _collect_params(r["steps"], used_by_others)

    challenge = rule_dict.get("challenge") or {}
    inert = set(challenge.get("inert_params", ()))
    inert_steps = set(challenge.get("inert_steps", ()))
    if inert_steps:
        # inert な手順の中でしか使われない定数も、出力に現れない
        per_step_params: dict[str, set[str]] = {}
        for st in rule_dict["steps"]:
            found: set[str] = set()
            _collect_params([st], found)
            per_step_params[st["name"]] = found
        for pname in set().union(*per_step_params.values()):
            uses = {sn for sn, ps in per_step_params.items() if pname in ps}
            if uses and uses <= inert_steps:
                inert.add(pname)

    # 定数の ±1
    for name, p in spec_dict["params"].items():
        if name in inert:
            skipped.append(
                {
                    "mutant": f"param:{name}",
                    "reason": "challenge（異例）により結果に影響しない定数（下限が上限を上回るため下限は効かない）",
                }
            )
            continue
        if name not in used_params:
            if name not in used_by_others:
                skipped.append(
                    {
                        "mutant": f"param:{name}",
                        "reason": "式に現れない定数（入力の意味を記述するだけで、関数の値に影響しない）",
                    }
                )
            continue
        for delta in (-1, 1):
            m = copy.deepcopy(spec_dict)
            mp = m["params"][name]
            if p["type"] == "ratio":
                mp["num"] = p["num"] + delta
            elif p["type"] == "int":
                mp["value"] = p["value"] + delta
            else:
                continue
            mutants.append(
                Mutant(f"param:{name}:{delta:+d}", f"定数 {name} を {delta:+d}", CalcSpec.from_dict(m))
            )

    # 表の値と境界の ±1（最初の行。このルールの式が参照する表だけ）
    used_tables: set[str] = set()
    _collect_tables(rule_dict["steps"], used_tables)
    conflict_table = (
        rule_dict.get("challenge", {}).get("conflict_table") if challenge_aspect == "value_conflict" else None
    )
    for tname, t in spec_dict.get("tables", {}).items():
        if tname not in used_tables:
            continue
        if tname == conflict_table:
            skipped.append(
                {
                    "mutant": f"table:{tname}",
                    "reason": "challenge（矛盾）の対立値。読みが割れないケースでは値の変異が現れない",
                }
            )
            continue
        for field_name in ("value", "upto"):
            if t["rows"][0].get(field_name) is None:
                continue
            m = copy.deepcopy(spec_dict)
            m["tables"][tname]["rows"][0][field_name] = t["rows"][0][field_name] + 1
            mutants.append(
                Mutant(
                    f"table:{tname}:{field_name}:+1",
                    f"表 {tname} の {field_name} を +1",
                    CalcSpec.from_dict(m),
                )
            )

    # 式の演算の入替（1 箇所ずつ）
    sites: list[tuple[list, str]] = []  # (パス, 説明) — パスは [step_idx, 'args', i, ...]
    rule_src = next(r for r in spec_dict["rules"] if r["id"] == rule_id)

    def walk(expr, path) -> None:
        if not isinstance(expr, dict) or "op" not in expr:
            return
        op = expr["op"]
        for table, label in (
            (_CMP_SWAP, "比較の取り違え"),
            (_MINMAX_SWAP, "min と max の入替"),
            (_LOGIC_SWAP, "and と or の入替"),
            (_BUSINESS_SWAP, "前営業日と翌営業日の入替"),
        ):
            if op in table:
                sites.append((list(path) + [("op", table[op])], f"{label}（{op}）"))
        if op in ("muldiv", "round_to"):
            if challenge_aspect == "rounding":
                skipped.append(
                    {
                        "mutant": "expr:rounding",
                        "reason": "challenge（端数処理の欠落）のため丸めの読みは採点対象外",
                    }
                )
            else:
                sites.append((list(path) + [("rounding", _ROUND_SWAP[expr["rounding"]])], "丸めの方向の入替"))
        if op == "tiered":
            rows = spec_dict.get("tables", {}).get(expr.get("table"), {}).get("rows", [])
            if len(rows) <= 1:
                skipped.append(
                    {
                        "mutant": f"tiered:{expr.get('table')}:method",
                        "reason": "区分が 1 つの表では全量方式と超過分方式が同じ結果になる（等価）",
                    }
                )
            else:
                sites.append(
                    (list(path) + [("method", _TIER_SWAP[expr["method"]])], "全量方式と超過分方式の入替")
                )
        if op == "period_end":
            sites.append((list(path) + [("include_start", not expr["include_start"])], "初日算入の反転"))
        for i, a in enumerate(expr.get("args", [])):
            walk(a, path + [i])

    for si, step in enumerate(rule_src["steps"]):
        walk(step["expr"], [si])

    inert_step_indexes = {i for i, st in enumerate(rule_dict["steps"]) if st["name"] in inert_steps}
    sites = [
        site
        for site in sites
        if not (site[0][0] in inert_step_indexes and not _site_skip_note(skipped, site))
    ]

    for path, desc in sites:
        m = copy.deepcopy(spec_dict)
        rule_m = next(r for r in m["rules"] if r["id"] == rule_id)
        *steps_path, (attr, new_value) = path
        node = rule_m["steps"][steps_path[0]]["expr"]
        for idx in steps_path[1:]:
            node = node["args"][idx]
        node[attr] = new_value
        mutants.append(Mutant(f"expr:{json.dumps(steps_path)}:{attr}", desc, CalcSpec.from_dict(m)))

    return mutants, skipped


def measure(
    spec_dict: dict,
    rule: Rule,
    cases: list[Case],
    rng: Random,
    hunt_tries: int = 200,
    case_filter=None,
) -> tuple[MutationReport, list[Case]]:
    """変異の検出率を測る。検出できない変異は乱数で入力を探し、見つかればケースを足す。"""
    spec = CalcSpec.from_dict(spec_dict)
    mutants, skipped = enumerate_mutants(spec_dict, rule.id)
    extra: list[Case] = []
    undetected: list[dict] = []
    detected = 0
    live_cases = [c for c in cases if c.kind != "unknown"]
    for mut in mutants:
        mrule = mut.spec.rule(rule.id)
        if _killed_by_cases(mut.spec, mrule, live_cases):
            detected += 1
            continue
        found = None
        for _ in range(hunt_tries):
            inputs = _sample_inputs(rule, rng)
            if case_filter is not None and not case_filter(inputs):
                continue
            expected = eval_rule(spec, rule, dict(inputs))
            got = eval_rule(mut.spec, mrule, dict(inputs))
            if got != expected:
                found = (inputs, expected)
                break
        if found:
            inputs, expected = found
            case = Case(
                case_id=f"{rule.id}:m{len(extra) + 1:03d}",
                function=rule.function,
                kind="random",
                inputs=inputs,
                expected=_jsonable(expected),
                tags=[f"kills:{mut.mutant_id}"],
            )
            extra.append(case)
            live_cases.append(case)
            detected += 1
        else:
            undetected.append(
                {
                    "mutant": mut.mutant_id,
                    "description": mut.description,
                    "reason": f"乱数探索 {hunt_tries} 件で差が出なかった（要確認）",
                }
            )
    report = MutationReport(
        total=len(mutants),
        detected=detected,
        added_cases=len(extra),
        undetected=undetected,
        skipped=skipped,
    )
    return report, extra


def _killed_by_cases(mspec: CalcSpec, mrule: Rule, cases: list[Case]) -> bool:
    for c in cases:
        holidays = frozenset(date.fromisoformat(h) for h in c.holidays)
        got = eval_rule(mspec, mrule, dict(c.inputs), holidays)
        if _jsonable(got) != c.expected:
            return True
    return False


def _site_skip_note(skipped: list[dict], site) -> bool:
    """inert な手順の式サイトをスキップし、理由を記録する（常に False を返して除外させる）。"""
    skipped.append(
        {
            "mutant": f"expr:step{site[0][0]}",
            "reason": "challenge（異例）によりこの手順の値は出力に現れない（常に上限値に落ちる）",
        }
    )
    return False


def _collect_tables(steps: list[dict], out: set[str]) -> None:
    def walk(e) -> None:
        if not isinstance(e, dict):
            return
        if "table" in e:
            out.add(e["table"])
        for a in e.get("args", []):
            walk(a)
        for k in ("filter", "map"):
            if k in e:
                walk(e[k])

    for s in steps:
        walk(s["expr"])


def _collect_params(steps: list[dict], out: set[str]) -> None:
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

    for s in steps:
        walk(s["expr"])
