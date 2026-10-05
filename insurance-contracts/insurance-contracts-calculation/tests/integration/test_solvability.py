"""G12 の出題の作り方（S10-3 で見つけた不備の回帰テスト）。

G12 は「約款を読めば実装できるか」を測る。出題そのものに穴があると、約款の欠陥と
出題の欠陥を区別できない。実際に 3 件の不備が見つかり、1 回目の測定は 51% だった。
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import EXAMPLE_DOC, needs_base

from insurance_contracts_calculation.testgen.taskcards import CONVENTIONS
from insurance_contracts_calculation.verify import solvability


@needs_base
def test_no_placeholder_leaks_into_the_task_card() -> None:
    """入力の説明文にプレースホルダを残さない。

    `{t:車}` → `{term:insured_car}` で作るので、解決を忘れると
    タスクカードに `{term:insured_car}` と出る。表示が壊れるだけでなく、
    **内部IDが漏れる**（`CLAUDE.md` 守ること 4）。
    """
    spec = json.loads((EXAMPLE_DOC / "calc" / "spec.json").read_text(encoding="utf-8"))
    leaks = [
        (r["id"], name) for r in spec["rules"] for name, s in r.get("inputs", {}).items() if "{" in s["desc"]
    ]
    assert not leaks, f"spec.json の入力の説明文にプレースホルダが残っている: {leaks}"

    for name in ("tasks.jsonl", "tasks_H1.jsonl", "tasks_H2.jsonl"):
        rows = [
            json.loads(line)
            for line in (EXAMPLE_DOC / "calc" / name).read_text(encoding="utf-8").splitlines()
            if line
        ]
        bad = [(c["function"], i["name"]) for c in rows for i in c["inputs"] if "{" in (i.get("desc") or "")]
        assert not bad, f"{name} にプレースホルダが残っている: {bad}"


@needs_base
def test_the_prompt_names_the_fields_of_a_collection() -> None:
    """明細（`list[dict]`）は辞書の項目名まで出題に書く。

    書かないと解き手は項目を直接の引数だと読み、`TypeError` になる（12 ケース全滅した）。
    """
    rows = [
        json.loads(line)
        for line in (EXAMPLE_DOC / "calc" / "tasks_H2.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    fields = [
        (c["function"], i["name"], [f["name"] for f in i.get("fields", [])])
        for c in rows
        for i in c["inputs"]
        if i["type"] == "list"
    ]
    if not fields:
        return  # この文書に明細のルールが無い（抽選次第）
    prompt = solvability.prompt_for(EXAMPLE_DOC)
    for _fn, arg, names in fields:
        assert names, f"{arg} に fields が無い（タスクカード側の欠落）"
        for n in names:
            assert f"`{n}`" in prompt, f"出題が明細の項目 {n} を書いていない"


@needs_base
def test_the_prompt_and_the_task_card_share_one_set_of_conventions() -> None:
    """呼び出しの取り決めは 1 か所に書く。

    出題とタスクカードに別々に書いていたため、実際に文がずれていた
    （出題だけ三値の裏側の説明が無く、7 ケースを落とした）。
    """
    prompt = solvability.prompt_for(EXAMPLE_DOC)
    for text in CONVENTIONS.values():
        assert text in prompt, f"出題に取り決めが入っていない: {text[:30]}"


def test_the_unknown_convention_states_both_directions() -> None:
    """三値の取り決めは「確定しない」と「確定する」の両方を書く。

    片方だけだと、解き手が「None が 1 つでもあれば None」と読むか、
    逆に算術まで determinacy を広げるかのどちらかに倒れる（どちらも実測した）。
    """
    text = CONVENTIONS["unknown"]
    assert "確定できないときは None" in text, "不明を返す側が書かれていない"
    assert "確定した値を返す" in text, "確定する側（Kleene）が書かれていない"
    assert "厳密" in text, "算術が厳密であることが書かれていない"


@needs_base
def test_the_reference_program_passes_g12(tmp_path: Path) -> None:
    """正解プログラムを解き手に見立てれば G12 は必ず通る（採点経路の健全性）。"""
    program = next((EXAMPLE_DOC / "calc" / "programs").glob("*.py"))
    source = program.read_text(encoding="utf-8")
    result = solvability.check(EXAMPLE_DOC, lambda _p: source, tmp_path)
    assert result.ok, result.detail
    assert result.data["rate"] == 1.0
