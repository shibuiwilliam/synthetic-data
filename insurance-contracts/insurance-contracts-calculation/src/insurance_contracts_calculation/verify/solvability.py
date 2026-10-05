"""G12 解答可能性（任意）。

基準となるシステムに H2 のヒントで実装させ、全ケース合格するかを見る。
不合格のルールは、生成器の誤りか難易度かを**人が**確認する（`HITL.md` H5）。

このモジュールは「出題の材料を組み立てる」ところまでを決定的に行う。
実際に解かせる相手（セッション内のサブエージェントなど）は呼び出し側が与える。
**生成の経路では使わない**（`CLAUDE.md` 守ること 11）。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ..core.docindex import Doc
from ..evalkit import report, runner
from ..testgen import taskcards
from . import gates


def prompt_for(data_dir: Path, rule_id: str | None = None) -> str:
    """H2 のヒント（根拠単位つき）で出題する材料を組み立てる。"""
    pack = report.load_pack(Path(data_dir))
    policy = json.loads((Path(data_dir) / "policy.json").read_text(encoding="utf-8"))
    doc = Doc.from_dict(policy)
    tasks_path = Path(data_dir) / "calc" / "tasks_H2.jsonl"
    tasks = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines() if line]
    if rule_id:
        tasks = [t for t in tasks if t["rule_id"] == rule_id]
    out = ["# 約款から計算規定を実装する", "", "次の関数を Python で実装してください。", ""]
    for t in tasks:
        out += [f"## {t['function']}（{t['title']}）", ""]
        for i in t["inputs"]:
            out.append(
                f"- 引数 `{i['name']}`: {i['desc']}（{i['type']}{'/' + i['unit'] if i['unit'] else ''}）"
            )
            # 明細（`list[dict]`）は、**辞書の項目名まで書かないと実装できない**。
            # 書き落としていたため、G12 の解き手が `item_loss` を直接の引数だと読み、
            # 12 ケースすべてが TypeError になった（S10-3 で判明）
            for f in i.get("fields", []):
                unit = "/" + f["unit"] if f.get("unit") else ""
                out.append(f"  - 各辞書の項目 `{f['name']}`: {f['desc']}（{f['type']}{unit}）")
        out.append(f"- 戻り値: {t['output']['type']}{'/' + (t['output']['unit'] or '')}")
        out += ["", "### 根拠（約款の該当箇所）", ""]
        for uid in t.get("evidence_units", []):
            if uid in doc.units:
                out.append(f"- [{uid}] {doc.units[uid].text}")
            else:
                for sub in sorted(k for k in doc.units if k.startswith(uid + "__")):
                    out.append(f"- [{sub}] {doc.units[sub].text}")
        out.append("")
    out += [
        "## 約束ごと",
        "",
    ]
    # 約束ごとは**タスクカードと同じ文**を使う（2 か所に書くとずれる。S10-3 で実際にずれていた）
    out += [f"- {text}。" for text in taskcards.CONVENTIONS.values()]
    out += [
        "- 割合は整数演算で計算し、端数処理を明示する。",
        "- 標準ライブラリだけを使う。",
        "",
    ]
    _ = pack
    return "\n".join(out)


def check(
    data_dir: Path, solve: Callable[[str], str], workdir: Path, timeout: float = 10.0
) -> gates.GateResult:
    """`solve(プロンプト) -> Python のソース` を受け取り、全ケース合格するかを見る。"""
    pack = report.load_pack(Path(data_dir))
    source = solve(prompt_for(data_dir))
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    impl = workdir / "submission.py"
    impl.write_text(source, encoding="utf-8")
    result = runner.run(impl, pack["cases"], pack["dates"], timeout=timeout)
    scored = report._score_impl(pack, result)
    failed = sorted({c["case_id"].split(":")[1] for c in scored["failures"]})
    return gates.GateResult(
        "G12",
        gates.GATE_TITLES["G12"],
        not failed,
        "合格しなかった関数: " + ", ".join(failed) if failed else "",
        {"rate": scored["rate"], "cases": scored["cases"], "passed": scored["passed"]},
    )
