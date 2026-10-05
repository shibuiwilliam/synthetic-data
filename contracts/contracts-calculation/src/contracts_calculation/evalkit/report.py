"""評価結果の集計：関数ごとの合格、ケース種別・パターン・難易度の軸ごとの合格率。"""

from __future__ import annotations

from collections import defaultdict


def aggregate(doc_results: dict[str, dict]) -> dict:
    """doc_results: content_id → {"cases": [runner の結果], "answer_key": [...]}。"""
    by_function: dict[str, dict] = {}
    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_pattern: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # 関数合格の分子・分母
    for cid, data in sorted(doc_results.items()):
        pattern_of = {a["function"]: a["pattern"] for a in data["answer_key"]}
        per_fn: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for row in data["cases"]:
            per_fn[row["function"]][1] += 1
            per_fn[row["function"]][0] += int(bool(row.get("ok")))
            agg = by_kind[row.get("kind", "?")]
            agg[1] += 1
            agg[0] += int(bool(row.get("ok")))
        for fn, (ok, total) in per_fn.items():
            passed = ok == total
            by_function[f"{cid}:{fn}"] = {"passed": passed, "cases_ok": ok, "cases_total": total}
            pat = pattern_of.get(fn, "?")
            by_pattern[pat][1] += 1
            by_pattern[pat][0] += int(passed)
    functions_total = len(by_function)
    functions_passed = sum(1 for v in by_function.values() if v["passed"])
    return {
        "functions_passed": functions_passed,
        "functions_total": functions_total,
        "function_pass_rate": round(functions_passed / functions_total, 4) if functions_total else 0.0,
        "by_function": by_function,
        "by_case_kind": {k: {"ok": v[0], "total": v[1]} for k, v in sorted(by_kind.items())},
        "by_pattern": {k: {"passed": v[0], "total": v[1]} for k, v in sorted(by_pattern.items())},
    }


def format_summary(agg: dict) -> str:
    lines = [
        (
            f"関数合格: {agg['functions_passed']}/{agg['functions_total']}"
            f"（{agg['function_pass_rate'] * 100:.1f}%）"
        ),
        "ケース種別ごと: " + "  ".join(f"{k}:{v['ok']}/{v['total']}" for k, v in agg["by_case_kind"].items()),
        "パターンごとの関数合格: "
        + "  ".join(f"{k}:{v['passed']}/{v['total']}" for k, v in agg["by_pattern"].items()),
    ]
    failed = [k for k, v in agg["by_function"].items() if not v["passed"]]
    if failed:
        lines.append("不合格: " + ", ".join(failed[:20]))
    return "\n".join(lines)
