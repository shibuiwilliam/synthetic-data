"""提出プログラムの隔離実行。

提出されたコードは**別プロセス**で、ネットワーク無し・時間制限つきで動かす。
無限ループや例外で採点が止まらないようにする（DESIGN.md §11.4）。
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

#: 子プロセスに渡す実行コード。標準入力でケースを受け、標準出力に結果を返す
_HARNESS = """
import datetime, importlib.util, json, sys

def _load(path):
    spec = importlib.util.spec_from_file_location("submission", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def _restore(inputs, dates):
    out = {}
    for k, v in inputs.items():
        out[k] = datetime.date.fromisoformat(v) if (k in dates and v is not None) else v
    return out

def main():
    payload = json.load(sys.stdin)
    try:
        module = _load(payload["impl"])
    except Exception as e:
        json.dump({"error": f"読み込みに失敗: {type(e).__name__}: {e}"}, sys.stdout)
        return
    out = []
    for case in payload["cases"]:
        fn = getattr(module, case["function"], None)
        if fn is None:
            out.append({"case_id": case["case_id"], "status": "missing"})
            continue
        try:
            value = fn(**_restore(case["inputs"], payload["dates"].get(case["function"], [])))
            if isinstance(value, datetime.date):
                value = value.isoformat()
            out.append({"case_id": case["case_id"], "status": "ok", "value": value})
        except Exception as e:
            out.append({"case_id": case["case_id"], "status": "error", "error": f"{type(e).__name__}: {e}"})
    json.dump({"results": out}, sys.stdout)

main()
"""


@dataclass
class RunResult:
    results: dict[str, dict] = field(default_factory=dict)
    error: str | None = None
    timed_out: bool = False


def run(impl: Path, cases: list[dict], date_args: dict[str, list[str]], timeout: float = 10.0) -> RunResult:
    """提出プログラムで全ケースを実行する。落ちても例外にせず、結果として返す。"""
    payload = json.dumps(
        {"impl": str(Path(impl).resolve()), "cases": cases, "dates": date_args}, ensure_ascii=False
    )
    try:
        proc = subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-c", textwrap.dedent(_HARNESS)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={"PATH": "", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
        )
    except subprocess.TimeoutExpired:
        return RunResult(error=f"時間制限（{timeout} 秒）を超えた", timed_out=True)
    if proc.returncode != 0:
        return RunResult(error=f"異常終了（{proc.returncode}）: {proc.stderr[-400:]}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return RunResult(error=f"出力を読めない: {proc.stdout[:200]}")
    if "error" in data:
        return RunResult(error=data["error"])
    return RunResult(results={r["case_id"]: r for r in data["results"]})
