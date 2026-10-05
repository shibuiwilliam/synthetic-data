"""提出プログラムの隔離実行（DESIGN.md §13.5）。

- 別プロセス・時間制限つきで実行する。ネットワークの遮断は OS 任せにせず、
  信頼できない提出物はさらに外側のサンドボックスで包むこと（ここでは分離と時間制限まで）。
- ケースは計算パックの cases.jsonl、型とカレンダーの要否は tasks.jsonl から取る。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

_DRIVER = """
import importlib.util
import json
import sys
from datetime import date

module_path, cases_path, tasks_path = sys.argv[1], sys.argv[2], sys.argv[3]
spec = importlib.util.spec_from_file_location("submission", module_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

types = {}
with open(tasks_path, encoding="utf-8") as f:
    for line in f:
        card = json.loads(line)
        types[card["function"]] = {
            "inputs": {i["name"]: i["type"] for i in card["inputs"]},
            "output": card["output"]["type"],
            "uses_calendar": card.get("uses_calendar", False),
        }


def conv(value, type_):
    if value is None:
        return None
    if type_ == "date":
        return date.fromisoformat(value)
    return value


results = []
with open(cases_path, encoding="utf-8") as f:
    for line in f:
        case = json.loads(line)
        t = types[case["function"]]
        kwargs = {n: conv(v, t["inputs"].get(n, "int")) for n, v in case["inputs"].items()}
        if t["uses_calendar"]:
            kwargs["holidays"] = frozenset(date.fromisoformat(h) for h in case.get("holidays", []))
        row = {"case_id": case["case_id"], "function": case["function"], "kind": case["kind"]}
        try:
            got = getattr(mod, case["function"])(**kwargs)
            expected = conv(case["expected"], t["output"])
            row["ok"] = got == expected
            row["got"] = got.isoformat() if isinstance(got, date) else got
        except Exception as exc:  # noqa: BLE001 — 提出物の例外は不合格として記録する
            row["ok"] = False
            row["error"] = f"{type(exc).__name__}: {exc}"
        results.append(row)
print(json.dumps(results, ensure_ascii=False, default=str))
"""


def run_submission(pack_calc_dir: Path, module_path: Path, timeout: int = 60) -> list[dict]:
    """提出モジュールを計算パックの全ケースで実行し、ケースごとの結果を返す。"""
    pack_calc_dir = Path(pack_calc_dir)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(_DRIVER)
        driver = f.name
    try:
        proc = subprocess.run(  # noqa: PLW1510 — 戻り値で自前判定する
            [
                sys.executable,
                driver,
                str(Path(module_path).resolve()),
                str(pack_calc_dir / "cases.jsonl"),
                str(pack_calc_dir / "tasks.jsonl"),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        Path(driver).unlink(missing_ok=True)
    if proc.returncode != 0:
        return [
            {
                "case_id": "__load__",
                "function": "__load__",
                "kind": "load",
                "ok": False,
                "error": proc.stderr[-800:],
            }
        ]
    return json.loads(proc.stdout)
