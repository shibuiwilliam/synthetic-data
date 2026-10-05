"""出力済みの計算パックに、検証ゲートだけを再実行する（`icc verify`）。

生成し直さずに確かめられるので、テンプレートや検査を直したあとの点検に使う。
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import base_adapter as ba
from ..core.docindex import Doc
from ..spec import interp
from ..spec.validate import RuleSet
from . import gates


def recheck(target: Path) -> list[gates.GateResult]:
    target = Path(target)
    policy_path = target / "policy.json"
    calc = target / "calc"
    if not policy_path.is_file() or not calc.is_dir():
        return [gates.GateResult("G0", "出力の形", False, f"{target} に policy.json / calc/ が無い")]
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    spec = json.loads((calc / "spec.json").read_text(encoding="utf-8"))
    answer = json.loads((calc / "answer_key.json").read_text(encoding="utf-8"))
    manifest = json.loads((calc / "manifest.json").read_text(encoding="utf-8"))
    cases = [
        json.loads(line) for line in (calc / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line
    ]

    doc = Doc.from_dict(policy)
    rs = RuleSet(spec, doc)
    results = gates.spec_gates(rs)
    results.append(gates.explicitness(rs, doc))
    results.append(_examples(rs, doc, answer, cases))
    results.append(_implementation(rs, calc, cases))
    results.append(gates.discoverable(doc, answer))
    draft = {k: v for k, v in policy.items() if k != "derived"}
    results.append(gates.base_lint(ba.lint(draft)))
    after = ba.estimate_pages(draft, policy["genre"])
    rendered = manifest.get("pages", {}).get("rendered")
    results.append(
        gates.page_budget(manifest.get("pages", {}).get("before", 0.0), after, rendered, ba.max_pages())
    )
    render_dir = next((p for p in target.glob("*--*") if (p / "layout.json").is_file()), None)
    if render_dir is not None:
        results.append(gates.base_verify(ba.verify(render_dir), []))
    results.append(_hashes(target, manifest))
    return results


def _examples(rs: RuleSet, doc: Doc, answer: list[dict], cases: list[dict]) -> gates.GateResult:
    """G5 を再実行する。

    `cases.jsonl` の日付は ISO の文字列なので、生成時と同じ型に戻してから渡す
    （戻さないと日付を返す規定で `surface_of` が `int()` に落ちて落第ではなく例外になる）。
    """
    pairs: dict[str, list] = {}
    for c in cases:
        if c["kind"] == "example":
            inputs = _restore(c["inputs"], rs, c["rule_id"])
            pairs.setdefault(c["rule_id"], []).append((inputs, _expected(c)))
    return gates.examples_match(rs, doc, pairs, {a["rule"]: a["explanatory_units"] for a in answer})


def _implementation(rs: RuleSet, calc: Path, cases: list[dict]) -> gates.GateResult:
    module = next(iter(sorted((calc / "programs").glob("*.py"))), None)
    if module is None:
        return gates.GateResult("G6", "実装の一致", False, "正解プログラムが無い")
    source = module.read_text(encoding="utf-8")
    ns: dict = {}
    exec(compile(source, module.name, "exec"), ns)  # noqa: S102
    mismatches = []
    for c in cases:
        got = ns[c["function"]](**_restore(c["inputs"], rs, c["rule_id"]))
        want = c["expected"]
        if c.get("expected_type") == "date" and want is not None:
            import datetime as dt

            want = dt.date.fromisoformat(want)
        if got != want:
            mismatches.append(f"{c['case_id']}: 正解プログラム {got} / 保存された期待値 {want}")
    # 参照インタプリタとも突き合わせる
    for c in cases[:200]:
        expr = rs.full_expr(c["rule_id"])
        if interp._ev(rs, expr, _restore(c["inputs"], rs, c["rule_id"]), None) != _expected(c):
            mismatches.append(f"{c['case_id']}: 参照インタプリタと期待値が一致しない")
    return gates.implementation_matches(mismatches, len(cases))


def _restore(inputs: dict, rs: RuleSet, rule_id: str) -> dict:
    import datetime as dt

    spec = rs.rules[rule_id].get("inputs", {})
    return {
        k: (dt.date.fromisoformat(v) if (spec.get(k, {}).get("type") == "date" and v is not None) else v)
        for k, v in inputs.items()
    }


def _expected(case: dict):
    import datetime as dt

    want = case["expected"]
    if case.get("expected_type") == "date" and want is not None:
        return dt.date.fromisoformat(want)
    return want


def _hashes(target: Path, manifest: dict) -> gates.GateResult:
    from ..export.layout import file_hashes

    now = file_hashes(target)
    saved = manifest.get("files", {})
    changed = sorted(k for k in set(now) | set(saved) if now.get(k) != saved.get(k))
    # PDF と PNG は描画器の版でバイトが変わりうる。テキストの正解だけを固定の対象にする
    changed = [k for k in changed if not k.endswith((".pdf", ".png", ".html"))]
    return gates.GateResult(
        "G11", "決定性（保存されたハッシュとの一致）", not changed, "変わったファイル: " + ", ".join(changed)
    )
