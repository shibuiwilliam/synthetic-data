"""H5 検算：47 問の仕様を親の契約書JSONに照合し、interp で算出して答えと突合する。

実行（contracts-calculation で）:
    PYTHONPATH=src uv run --project .. python -m contracts_calculation.h5.verify

出力（生成物。手で編集しない）:
    docs/h5_inventory.json  … 47 問の棚卸し＋機械判定
    docs/h5_report.md       … 判定レポート（一致／不一致／形式化不能／読み幅あり）

検査の対応: G1=validate、G2=引用の逐語照合、G4=数値の往復（meta.constants・紙面表記⇄仕様の値）、
契約日は meta.contract_date と突合。判定は決定的（同じ入力から同じ出力）。
"""

from __future__ import annotations

import json
import re
from datetime import date

from contracts_calculation import base_adapter as ba
from contracts_calculation.docmodel import numbers_ja as nj
from contracts_calculation.docmodel.index import DocumentIndex
from contracts_calculation.h5.specs import ENTRIES
from contracts_calculation.spec.interp import _Evaluator
from contracts_calculation.spec.model import CalcSpec
from contracts_calculation.spec.validate import validate_spec

_IDX: dict[str, DocumentIndex] = {}


def _idx(cid: str) -> DocumentIndex:
    if cid not in _IDX:
        _IDX[cid] = DocumentIndex.load(ba.repo_root() / "content" / cid)
    return _IDX[cid]


# --- 表記 → 値（G4 の読取側） ----------------------------------------------------

_HOURS_RE = re.compile(r"([0-9]+)時間")
_AMOUNT_TOKEN_RE = re.compile(r"金?[0-9,]*(?:億[0-9,]*)?(?:万)?[0-9,]*円")


def _surface_value(surface: str, ptype: str, unit: str | None):
    """紙面表記から仕様の値を読み戻す。読めなければ None。"""
    s = nj.normalize(surface)
    if ptype == "date":
        d = nj.parse_date_ja(s)
        return d.isoformat() if d else None
    if ptype == "ratio":
        return nj.parse_ratio(s)
    # int
    if unit == "PERCENT":
        r = nj.parse_ratio(s)
        if r and (r[0] * 100) % r[1] == 0:
            return r[0] * 100 // r[1]
        return None
    if unit in ("DAY", "MONTH", "YEAR"):
        d = nj.parse_duration(s)
        if d:
            return d.n
        dom = nj.parse_day_of_month(s)
        if isinstance(dom, int):
            return dom
        return None
    if unit == "HOUR":
        m = _HOURS_RE.search(s)
        return int(m.group(1)) if m else None
    if unit == "COUNT":
        c = nj.parse_count(s)
        if c is not None:
            return c
        m = re.search(r"([0-9]+)回", s)
        return int(m.group(1)) if m else None
    # JPY / JPY/HOUR …：表記の中の金額を拾う
    for m in _AMOUNT_TOKEN_RE.finditer(s):
        v = nj.parse_amount_yen(m.group(0))
        if v is not None:
            return v
    # 「円」の付かない素のカンマ数字（表のセル。例「７，４６５，０００」）
    t = s.replace(",", "")
    if t.isdigit():
        return int(t)
    return None


def _ratio_eq(a: tuple[int, int], num: int, den: int) -> bool:
    return a is not None and a[0] * den == num * a[1]


# --- 答えの解釈 ------------------------------------------------------------------


def parse_answer(kind: str, answer: str):
    s = nj.normalize(answer)
    if kind == "amount":
        return nj.parse_amount_yen(s)
    if kind == "number_plain":
        t = s.replace(",", "")
        return int(t) if t.isdigit() else None
    if kind == "date":
        return nj.parse_date_ja(s)
    if kind == "day_ordinal":
        m = re.fullmatch(r"([0-9]+)日目", s)
        return int(m.group(1)) if m else None
    if kind == "percent":
        r = nj.parse_ratio(s)
        if r and (r[0] * 100) % r[1] == 0:
            return r[0] * 100 // r[1]
        return None
    if kind == "multiplier_percent":
        m = re.fullmatch(r"([0-9]+)(?:\.([0-9]+))?倍", s)
        if not m:
            return None
        frac = (m.group(2) or "").ljust(2, "0")[:2]
        return int(m.group(1)) * 100 + int(frac)
    raise ValueError(f"未知の answer_kind: {kind}")


# --- 1 問の検査 ------------------------------------------------------------------


def eval_steps(spec: CalcSpec, rule, inputs: dict) -> dict:
    env = {}
    for name, decl in rule.inputs.items():
        raw = inputs.get(name)
        if isinstance(raw, str) and decl.type == "date":
            raw = date.fromisoformat(raw)
        env[name] = raw
    ev = _Evaluator(spec, rule, env, frozenset())
    steps: dict = {}
    for st in rule.steps:
        steps[st.name] = ev.eval(st.expr, steps)
    return steps


def check_entry(entry: dict) -> dict:
    cid, qid = entry["cid"], entry["qid"]
    idx = _idx(cid)
    spec = CalcSpec.from_dict(entry["spec"])
    rule = spec.rules[0]
    problems: list[str] = []

    # G1 仕様の検査
    for issue in validate_spec(spec):
        problems.append(f"G1: {issue}")

    # G2 引用の逐語照合
    for name, p in spec.params.items():
        if p.source is None:
            problems.append(f"G2: params.{name} に根拠が無い")
            continue
        if p.source.unit not in idx.units:
            problems.append(f"G2: params.{name} の単位 {p.source.unit} が存在しない")
        elif not idx.quote_in_unit(p.source.unit, p.source.quote):
            problems.append(
                f"G2: params.{name} の引用が {p.source.unit} に逐語で存在しない: {p.source.quote!r}"
            )

    # G4 数値の往復（meta.constants との突合、紙面表記 → 値）
    for pname, ckey in entry["const_keys"].items():
        p = spec.params[pname]
        meta_surface = idx.constants.get(ckey)
        if meta_surface is None:
            problems.append(f"G4: meta.constants に {ckey} が無い")
            continue
        read = _surface_value(meta_surface, p.type, p.unit)
        if p.type == "ratio":
            if not _ratio_eq(read, p.num, p.den):
                problems.append(
                    f"G4: {ckey}={meta_surface!r} の読取 {read} が仕様 {p.num}/{p.den} と一致しない"
                )
        elif p.type == "date":
            if read != p.value:
                problems.append(f"G4: {ckey}={meta_surface!r} の読取 {read} が仕様 {p.value} と一致しない")
        else:
            if read != p.value:
                problems.append(f"G4: {ckey}={meta_surface!r} の読取 {read} が仕様 {p.value} と一致しない")
    for name, p in spec.params.items():
        if name in entry["derived_params"]:
            continue  # 導出値：表記の往復は適用外（導出注記で扱う）
        read = _surface_value(p.surface or "", p.type, p.unit)
        if p.type == "ratio":
            if not _ratio_eq(read, p.num, p.den):
                problems.append(f"G4: params.{name} の表記 {p.surface!r} が値 {p.num}/{p.den} に読み戻せない")
        elif read is None or (p.type == "date" and read != p.value) or (p.type != "date" and read != p.value):
            problems.append(f"G4: params.{name} の表記 {p.surface!r} が値 {p.value} に読み戻せない")

    # 契約日の突合
    for iname in entry["meta_date_inputs"]:
        if entry["given"].get(iname) != idx.contract_date:
            problems.append(
                f"meta: 入力 {iname}={entry['given'].get(iname)} が meta.contract_date={idx.contract_date} と一致しない"
            )

    # 算出と突合
    computed = steps = expected = None
    if not any(s.startswith("G1") for s in problems):
        steps = eval_steps(spec, rule, dict(entry["given"]))
        computed = steps[rule.output["step"]]
    answer = _answer_of(cid, qid)
    expected = parse_answer(entry["answer_kind"], answer) if answer is not None else None
    if expected is None:
        problems.append(f"答えの表記を読めない: {answer!r}")

    match = computed is not None and expected is not None and computed == expected
    has_reading = any(f["kind"] == "reading" for f in entry["flags"])
    if problems or not match:
        verdict = "不一致"
    elif has_reading:
        verdict = "読み幅あり（計算は一致）"
    else:
        verdict = "一致"
    return {
        "cid": cid,
        "qid": qid,
        "verdict": verdict,
        "computed": _jsonable(computed),
        "expected": _jsonable(expected),
        "answer_raw": answer,
        "steps": {k: _jsonable(v) for k, v in (steps or {}).items()},
        "problems": problems,
        "flags": entry["flags"],
        "derived_params": entry["derived_params"],
    }


_QA_CACHE: dict[str, dict] = {}


def _answer_of(cid: str, qid: str) -> str | None:
    if cid not in _QA_CACHE:
        qa = json.loads((ba.repo_root() / "content" / cid / "qa_authored.json").read_text(encoding="utf-8"))
        items = qa if isinstance(qa, list) else qa.get("items", [])
        _QA_CACHE[cid] = {q["id"]: q for q in items}
    q = _QA_CACHE[cid].get(qid)
    return q["answer"] if q else None


def _jsonable(v):
    return v.isoformat() if isinstance(v, date) else v


# --- 一括実行とレポート ------------------------------------------------------------


def run() -> list[dict]:
    results = [check_entry(e) for e in ENTRIES]
    assert len(results) == 47, f"47 問のはずが {len(results)} 問"
    return results


def write_outputs(results: list[dict]) -> None:
    docs = ba.calc_root() / "docs"
    (docs / "h5_inventory.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    lines = [
        "# docs/h5_report.md — apply 型 QA 47 問の機械検算（自動生成。手で編集しない）",
        "",
        "> 作り直すには: `PYTHONPATH=src uv run --project .. python -m contracts_calculation.h5.verify`",
        (
            "> 仕様の正本は `src/contracts_calculation/h5/specs.py`。"
            "検査: G1=仕様検査 / G2=逐語照合 / G4=数値の往復 / 契約日=meta 突合。"
        ),
        "",
        "## 集計",
        "",
        "| 判定 | 件数 |",
        "|---|---|",
    ]
    for k in ("一致", "読み幅あり（計算は一致）", "不一致", "形式化不能"):
        lines.append(f"| {k} | {counts.get(k, 0)} |")
    lines += ["", "## 問ごとの判定", ""]
    cur = None
    for r in results:
        if r["cid"] != cur:
            cur = r["cid"]
            lines.append(f"### {cur}")
            lines.append("")
        lines.append(f"#### {r['qid']} — **{r['verdict']}**")
        lines.append("")
        lines.append(
            f"- 答え（紙面）: {r['answer_raw']} ／ 読取値: {r['expected']} ／ 算出値: {r['computed']}"
        )
        if r["steps"]:
            steps_s = "、".join(f"{k}={v}" for k, v in r["steps"].items())
            lines.append(f"- 計算過程: {steps_s}")
        for f in r["flags"]:
            mark = "読み幅" if f["kind"] == "reading" else "注記"
            lines.append(f"- {mark}: {f['text']}")
        if r["derived_params"]:
            lines.append(f"- 導出パラメータ（表記の往復の適用外）: {', '.join(r['derived_params'])}")
        for p in r["problems"]:
            lines.append(f"- 問題: {p}")
        lines.append("")
    (docs / "h5_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    results = run()
    write_outputs(results)
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print("判定:", json.dumps(counts, ensure_ascii=False))
    bad = [r for r in results if r["verdict"] == "不一致"]
    for r in bad:
        print(f"不一致: {r['cid']}:{r['qid']} computed={r['computed']} expected={r['expected']}")
        for p in r["problems"]:
            print("   ", p)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
