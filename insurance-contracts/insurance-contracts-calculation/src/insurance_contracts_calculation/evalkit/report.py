"""採点と集計レポート（DESIGN.md §11.4）。

パターン・表現手段・難易度の軸・ケースの種別で集計し、JSON と Markdown を出す。
どの軸で落ちたかが分かるようにするのが目的で、合計点だけを出さない。
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from . import discovery, reading, runner


def load_pack(data_dir: Path) -> dict:
    calc = Path(data_dir) / "calc"
    cases = [
        json.loads(line) for line in (calc / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line
    ]
    answer = json.loads((calc / "answer_key.json").read_text(encoding="utf-8"))
    manifest = json.loads((calc / "manifest.json").read_text(encoding="utf-8"))
    spec = json.loads((calc / "spec.json").read_text(encoding="utf-8"))
    date_args: dict[str, list[str]] = {}
    for r in spec["rules"]:
        dates = [n for n, s in r.get("inputs", {}).items() if s["type"] == "date"]
        if dates:
            date_args[r["interface"]["function"]] = dates
    return {
        "cases": cases,
        "answer": answer,
        "manifest": manifest,
        "spec": spec,
        "dates": date_args,
        "dir": Path(data_dir),
    }


def evidence_texts(data_dir: Path) -> dict[str, str]:
    """根拠単位ID → 正解の文字列（読取結果との突合に使う）。"""
    from ..core.docindex import Doc

    policy = json.loads((Path(data_dir) / "policy.json").read_text(encoding="utf-8"))
    doc = Doc.from_dict(policy)
    out = {uid: u.text for uid, u in doc.units.items()}
    # 図と表は「単位ID＝ブロックID」で正解表に載る。中の文字列をつないで突合に使う
    for bid in doc.blocks:
        if bid in out:
            continue
        parts = [u.text for uid, u in doc.units.items() if uid.startswith(bid + "__")]
        if parts:
            out[bid] = "".join(parts)
    return out


def run_eval(
    data_dir: Path,
    submission: Path,
    track: str = "impl",
    hint: str = "H0",
    timeout: float = 10.0,
    reading_path: Path | None = None,
) -> dict:
    """提出を採点する。

    | トラック | 入力 | 採点 |
    |---|---|---|
    | `discover` | ルールと根拠単位の一覧（JSON） | 正解表の `units` に対する再現率・適合率 |
    | `impl` | Python モジュール | ケースの合格率。軸ごとに集計する |
    | `e2e` | Python モジュール ＋ **読取結果JSON** | 実装と同じ採点に加え、
      根拠が読取結果に残っているかを測る |
    """
    pack = load_pack(data_dir)
    out: dict = {
        "content_id": pack["manifest"]["content_id"],
        "track": track,
        "hint": hint,
        "submission": str(submission),
    }
    if track == "e2e":
        if reading_path is None:
            raise ValueError(
                "一気通貫（--track e2e）には読取結果が要る: --reading <読取結果JSON> を渡す。"
                "読取結果の形は本体の schema/prediction.schema.json に合わせる"
            )
        read = reading.Reading.load(reading_path)
        cov = reading.evidence_coverage(read, pack["answer"], evidence_texts(pack["dir"]))
        out["reading"] = {
            "path": str(reading_path),
            "doc_id": read.doc_id,
            "units": cov.units,
            "found": cov.found,
            "rate": cov.rate,
            "missing": cov.missing,
            "per_rule": cov.per_rule,
        }
    if track == "discover":
        pred = json.loads(Path(submission).read_text(encoding="utf-8"))
        s = discovery.score(pack["answer"], pred if isinstance(pred, list) else pred.get("rules", []))
        out["discovery"] = {
            "recall": s.recall,
            "precision": s.precision,
            "f1": s.f1,
            "per_rule": s.per_rule,
        }
        return {"json": out, "markdown": _markdown(out)}

    result = runner.run(Path(submission), pack["cases"], pack["dates"], timeout=timeout)
    out["impl"] = _score_impl(pack, result)
    if track == "e2e":
        out["e2e"] = _attribute(out)
    return {"json": out, "markdown": _markdown(out)}


def _attribute(out: dict) -> dict:
    """落ちた関数を「読取で根拠を落とした」と「読んだうえで取り違えた」に分ける。"""
    impl, read = out["impl"], out["reading"]
    by_fn = impl["by_axis"]["function"]
    rule_of = {}
    for rid, stat in read["per_rule"].items():
        rule_of[rid] = stat
    lost, wrong = [], []
    for fn, stat in by_fn.items():
        if stat["rate"] >= 1.0:
            continue
        rid = next((r for r in rule_of if r.replace(".", "_") == fn or fn.startswith(r.split(".")[0])), None)
        if rid is not None and rule_of[rid]["rate"] < 1.0:
            lost.append({"function": fn, "rate": stat["rate"], "evidence_rate": rule_of[rid]["rate"]})
        else:
            wrong.append({"function": fn, "rate": stat["rate"]})
    return {
        "evidence_rate": read["rate"],
        "failed_with_missing_evidence": lost,
        "failed_with_full_evidence": wrong,
        "note": "根拠が読取結果に残っているのに落ちた関数は、読み取りではなく実装の問題である",
    }


def _score_impl(pack: dict, result: runner.RunResult) -> dict:
    by_rule = {a["rule"]: a for a in pack["answer"]}
    axes: dict[str, dict[str, list[bool]]] = {
        "pattern": defaultdict(list),
        "modality": defaultdict(list),
        "kind": defaultdict(list),
        "function": defaultdict(list),
        "figure_only": defaultdict(list),
        "table_lookup": defaultdict(list),
    }
    total = passed = errors = 0
    failures: list[dict] = []
    for case in pack["cases"]:
        total += 1
        got = result.results.get(case["case_id"])
        ok = bool(got and got["status"] == "ok" and got.get("value") == case["expected"])
        if got and got["status"] in ("error", "missing"):
            errors += 1
        passed += int(ok)
        if not ok and len(failures) < 40:
            failures.append(
                {
                    "case_id": case["case_id"],
                    "inputs": case["inputs"],
                    "expected": case["expected"],
                    "got": (got or {}).get("value", (got or {}).get("status", "未実行")),
                }
            )
        a = by_rule.get(case["rule_id"], {})
        axes["pattern"][a.get("pattern", "?")].append(ok)
        axes["kind"][case["kind"]].append(ok)
        axes["function"][case["function"]].append(ok)
        for m in a.get("modalities") or ["prose"]:
            axes["modality"][m].append(ok)
        d = a.get("difficulty") or {}
        axes["figure_only"][str(d.get("figure_only", False))].append(ok)
        axes["table_lookup"][str(d.get("table_lookup"))].append(ok)
    per_function = {fn: all(v) for fn, v in axes["function"].items()}
    return {
        "error": result.error,
        "timed_out": result.timed_out,
        "cases": total,
        "passed": passed,
        "rate": round(passed / total, 4) if total else 0.0,
        "runtime_errors": errors,
        "functions_fully_correct": sum(1 for v in per_function.values() if v),
        "functions": len(per_function),
        "by_axis": {
            name: {
                k: {"cases": len(v), "passed": sum(v), "rate": round(sum(v) / len(v), 4)}
                for k, v in sorted(groups.items())
            }
            for name, groups in axes.items()
        },
        "failures": failures,
    }


def _markdown(out: dict) -> str:
    lines = [f"# 採点結果 {out['content_id']}（{out['track']} / ヒント {out['hint']}）", ""]
    if "reading" in out:
        r = out["reading"]
        lines += [
            f"- 読取結果: `{r['path']}`（{r['doc_id'] or '文書IDなし'}）",
            f"- 根拠の保存率 **{r['rate']:.1%}**（{r['found']}/{r['units']} 単位）",
            "",
        ]
        if r["missing"]:
            lines += [
                "### 読取結果に残っていない根拠",
                "",
                "| ルール | 単位 | 正解の文字列 |",
                "|---|---|---|",
            ]
            for m in r["missing"][:15]:
                lines.append(f"| {m['rule']} | {m['unit']} | {m['text']} |")
            lines.append("")
    if "discovery" in out:
        d = out["discovery"]
        lines += [
            f"- 再現率 {d['recall']:.0%} / 適合率 {d['precision']:.0%} / F1 {d['f1']:.3f}",
            "",
            "| 関数 | 再現率 | 適合率 | 拾えなかった単位 |",
            "|---|---|---|---|",
        ]
        for fn, r in sorted(d["per_rule"].items()):
            lines.append(
                f"| {fn} | {r['recall']:.0%} | {r['precision']:.0%} | {', '.join(r['missing']) or '—'} |"
            )
        return "\n".join(lines) + "\n"
    i = out["impl"]
    if i.get("error"):
        lines.append(f"**提出プログラムを実行できなかった**: {i['error']}")
        return "\n".join(lines) + "\n"
    lines += [
        f"- ケース {i['passed']}/{i['cases']}（{i['rate']:.1%}）",
        f"- 全ケース合格の関数 {i['functions_fully_correct']}/{i['functions']}",
        f"- 実行時エラー {i['runtime_errors']} 件",
        "",
    ]
    for axis, groups in i["by_axis"].items():
        if axis == "function":
            continue
        lines += [f"## {axis} 別", "", "| 区分 | 合格 | ケース | 合格率 |", "|---|---|---|---|"]
        for k, v in groups.items():
            lines.append(f"| {k} | {v['passed']} | {v['cases']} | {v['rate']:.1%} |")
        lines.append("")
    if "e2e" in out:
        e = out["e2e"]
        lines += ["## 落ちた原因の切り分け", ""]
        if e["failed_with_missing_evidence"]:
            lines.append("**読み取りで根拠を落とした関数**（読取の誤りの影響）:")
            for x in e["failed_with_missing_evidence"]:
                lines.append(
                    f"- `{x['function']}` 合格率 {x['rate']:.0%} / 根拠の保存率 {x['evidence_rate']:.0%}"
                )
        if e["failed_with_full_evidence"]:
            lines.append("**根拠は読めていたのに落ちた関数**（実装の問題）:")
            for x in e["failed_with_full_evidence"]:
                lines.append(f"- `{x['function']}` 合格率 {x['rate']:.0%}")
        lines.append("")
    if i["failures"]:
        lines += ["## 落ちたケース（先頭 40 件）", "", "| ケース | 入力 | 期待 | 実際 |", "|---|---|---|---|"]
        for f in i["failures"]:
            args = json.dumps(f["inputs"], ensure_ascii=False)
            lines.append(f"| {f['case_id']} | {args} | {f['expected']} | {f['got']} |")
    return "\n".join(lines) + "\n"
