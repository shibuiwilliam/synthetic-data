"""生成の経路そのものの検査（本体との接続・公開範囲・採点）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import BASE_CONTENT, EXAMPLE_DOC, needs_base

from insurance_contracts_calculation import base_adapter as ba
from insurance_contracts_calculation.config import Settings
from insurance_contracts_calculation.generate import generate


@pytest.fixture(scope="module")
def generated(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("gen")
    return generate(BASE_CONTENT, out, 3, Settings.of("standard", render=False, png=False)).out_dir


@needs_base
def test_derived_is_recalculated_by_the_base(generated: Path) -> None:
    """`derived` は本体の build が付ける（仮実装を持たない）。

    足すノードは配置によって種類が違う（条・別表・特約）。どれも `derived` に載る。
    """
    policy = json.loads((generated / "policy.json").read_text(encoding="utf-8"))
    labels = policy["derived"]["labels"]
    manifest = json.loads((generated / "calc" / "manifest.json").read_text(encoding="utf-8"))
    added = manifest["added"]["nodes"]
    assert added
    for nid in added:
        assert nid in labels, f"{nid} が derived に無い"
        citation = labels[nid]["citation"]
        assert citation, f"{nid} の見出しが空"
        if nid.startswith("app"):
            assert "表" in citation, f"別表 {nid} の見出しが別表番号になっていない: {citation}"
        elif nid.startswith("rider_"):
            assert "特約" in citation, f"特約 {nid} の見出しが特約名になっていない: {citation}"
        else:
            assert "条" in citation, f"条 {nid} の見出しが条番号になっていない: {citation}"
    assert "derived_stale" not in manifest


@needs_base
def test_added_nodes_can_be_referenced(generated: Path) -> None:
    """追加した条への `{ref:}` が解決する（TASK.md S1-7）。"""
    from insurance_contracts_calculation.realize import patch as patch_ops

    policy = json.loads((generated / "policy.json").read_text(encoding="utf-8"))
    draft = {k: v for k, v in policy.items() if k != "derived"}
    added = json.loads((generated / "calc" / "manifest.json").read_text(encoding="utf-8"))["added"]["nodes"]
    # 章に足した条を選ぶ（別表・特約は親が章ではない）
    pairs = [
        (ch, nid)
        for nid in added
        for ch in patch_ops.chapters(draft)
        if any(c["id"] == nid for c in ch.get("children") or [])
    ]
    assert pairs, "章に足した条が 1 つも無い"
    chapter, target = pairs[0]
    probe = patch_ops.add_node(
        chapter["id"],
        {
            "id": f"{chapter['id']}_aref",
            "kind": "article",
            "title": "参照の確認",
            "children": [
                {
                    "id": f"{chapter['id']}_aref_p1",
                    "kind": "paragraph",
                    "text": "この条は{ref:" + target + "}に定めます。",
                }
            ],
        },
    )
    rebuilt = ba.rebuild(patch_ops.apply(draft, [probe]))
    text = rebuilt["derived"]["plain_text"][f"{chapter['id']}_aref_p1"]["without_label"]
    assert "{ref:" not in text, "追加した条への参照が解決していない"
    assert "条" in text
    assert not [f for f in ba.lint(patch_ops.apply(draft, [probe])) if f.severity == "error"]


@needs_base
def test_nothing_is_written_under_dataset(generated: Path, repo_root: Path) -> None:
    assert "dataset" not in generated.parts
    assert not (repo_root / "dataset" / generated.name).exists()


def test_public_package_hides_the_answers(tmp_path: Path) -> None:
    from insurance_contracts_calculation.export.datasheet import export_public

    out = export_public(EXAMPLE_DOC, tmp_path / "public")
    names = set(out["files"])
    assert "policy.json" in names
    assert "calc/tasks.jsonl" in names
    assert not [n for n in names if n.startswith(("calc/spec", "calc/answer", "calc/programs", "calc/tests"))]
    assert "calc/cases.jsonl" not in names
    cases = tmp_path / "public" / "calc" / "examples.jsonl"
    if cases.exists():
        kinds = {json.loads(line)["kind"] for line in cases.read_text(encoding="utf-8").splitlines() if line}
        assert kinds == {"example"}


def test_eval_scores_the_wrong_submission() -> None:
    """誤った提出を採点すると、落ちた軸が分かる（TASK.md S4-4）。"""
    from insurance_contracts_calculation.evalkit.report import run_eval

    report = run_eval(EXAMPLE_DOC, EXAMPLE_DOC.parent / "wrong_impl.py", track="impl")
    impl = report["json"]["impl"]
    assert impl["error"] is None
    assert 0 < impl["rate"] < 1.0, "誤った実装なのに満点か 0 点になっている"
    assert impl["functions_fully_correct"] < impl["functions"]
    assert "by_axis" in impl and impl["by_axis"]["pattern"]


def test_eval_gives_full_marks_to_the_reference() -> None:
    from insurance_contracts_calculation.evalkit.report import run_eval

    program = next((EXAMPLE_DOC / "calc" / "programs").glob("*.py"))
    report = run_eval(EXAMPLE_DOC, program, track="impl")
    assert report["json"]["impl"]["rate"] == 1.0


def test_discovery_scoring_is_sane() -> None:
    from insurance_contracts_calculation.evalkit import discovery

    answer = json.loads((EXAMPLE_DOC / "calc" / "answer_key.json").read_text(encoding="utf-8"))
    perfect = [{"function": a["function"], "units": a["units"]} for a in answer]
    assert discovery.score(answer, perfect).f1 == 1.0
    assert discovery.score(answer, []).f1 == 0.0


def test_runner_survives_a_broken_submission(tmp_path: Path) -> None:
    from insurance_contracts_calculation.evalkit import report, runner

    pack = report.load_pack(EXAMPLE_DOC)
    loop = tmp_path / "loop.py"
    loop.write_text("while True:\n    pass\n", encoding="utf-8")
    assert runner.run(loop, pack["cases"], pack["dates"], timeout=2.0).timed_out
    broken = tmp_path / "broken.py"
    broken.write_text("raise RuntimeError('壊れている')\n", encoding="utf-8")
    assert runner.run(broken, pack["cases"], pack["dates"], timeout=5.0).error


def test_solvability_harness_is_usable(tmp_path: Path) -> None:
    """G12 の出題と採点の仕掛けが動くこと（TASK.md S4-7）。

    「基準となるシステム」に何を使うかは人の判断（TASK.md §9 H5）なので、ここでは
    正解プログラムそのものを提出として流し、仕掛けが通ることだけを確かめる。
    """
    from insurance_contracts_calculation.verify import solvability

    prompt = solvability.prompt_for(EXAMPLE_DOC)
    assert "根拠（約款の該当箇所）" in prompt
    assert "キーワード引数" in prompt
    tasks = [
        json.loads(line)
        for line in (EXAMPLE_DOC / "calc" / "tasks_H2.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    for t in tasks:
        assert t["function"] in prompt, "H2 のヒントに関数名が出ていない"
        assert t["evidence_units"], "H2 なのに根拠単位が付いていない"

    program = next((EXAMPLE_DOC / "calc" / "programs").glob("*.py")).read_text(encoding="utf-8")
    result = solvability.check(EXAMPLE_DOC, lambda _p: program, tmp_path)
    assert result.ok, result.detail
    assert result.data["rate"] == 1.0


def test_hint_levels_differ() -> None:
    """ヒントの水準が上がるほど渡す情報が増える（TASK.md S4-1）。"""
    rows = {}
    for name, hint in (("tasks.jsonl", "H0"), ("tasks_H1.jsonl", "H1"), ("tasks_H2.jsonl", "H2")):
        rows[hint] = [
            json.loads(line)
            for line in (EXAMPLE_DOC / "calc" / name).read_text(encoding="utf-8").splitlines()
            if line
        ]
    assert all("citations" not in t for t in rows["H0"])
    assert all(t["citations"] for t in rows["H1"])
    assert all("evidence_units" not in t for t in rows["H1"])
    assert all(t["evidence_units"] for t in rows["H2"])


def _write_reading(path: Path, doc_dir: Path, *, only_body: bool = False) -> Path:
    """読取結果JSON を作る（本体の prediction 形式）。"""
    from insurance_contracts_calculation.core.docindex import Doc

    policy = json.loads((doc_dir / "policy.json").read_text(encoding="utf-8"))
    doc = Doc.from_dict(policy)
    keep = ("paragraph", "article", "item") if only_body else None
    els = [{"text": u.text} for u in doc.units.values() if u.text and (keep is None or u.utype in keep)]
    path.write_text(
        json.dumps({"doc_id": doc_dir.name, "elements": els}, ensure_ascii=False), encoding="utf-8"
    )
    return path


def test_e2e_requires_a_reading_result() -> None:
    """一気通貫は読取結果を入力に取る。渡さなければ**黙って impl と同じ採点にしない**。"""
    from insurance_contracts_calculation.evalkit.report import run_eval

    with pytest.raises(ValueError, match="読取結果"):
        run_eval(EXAMPLE_DOC, EXAMPLE_DOC.parent / "wrong_impl.py", track="e2e")


def test_e2e_measures_how_much_evidence_survived_the_reading(tmp_path: Path) -> None:
    """読取結果に根拠が残っているかを測る（DESIGN.md §11.4）。"""
    from insurance_contracts_calculation.evalkit.report import run_eval

    program = next((EXAMPLE_DOC / "calc" / "programs").glob("*.py"))
    full = run_eval(
        EXAMPLE_DOC,
        program,
        track="e2e",
        reading_path=_write_reading(tmp_path / "full.json", EXAMPLE_DOC),
    )["json"]
    assert full["reading"]["rate"] == 1.0, "全部読めている読取結果で保存率が 1.0 にならない"
    assert full["impl"]["rate"] == 1.0

    poor = run_eval(
        EXAMPLE_DOC,
        program,
        track="e2e",
        reading_path=_write_reading(tmp_path / "poor.json", EXAMPLE_DOC, only_body=True),
    )["json"]
    assert poor["reading"]["rate"] < 1.0, "表や図を落とした読取結果でも保存率が下がらない"
    lost = {m["unit"] for m in poor["reading"]["missing"]}
    assert lost, "落ちた根拠が記録されていない"
    assert any(u.startswith(("tbl_", "fig_", "fml_")) for u in lost), "表・図・算式の欠落を拾えていない"
    assert "e2e" in poor, "読取の誤りと実装の誤りの切り分けが出ていない"
    assert poor["e2e"]["evidence_rate"] == poor["reading"]["rate"]


def test_e2e_rejects_a_broken_reading_result(tmp_path: Path) -> None:
    from insurance_contracts_calculation.evalkit.reading import Reading, ReadingError

    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"doc_id": "x"}), encoding="utf-8")
    with pytest.raises(ReadingError):
        Reading.load(empty)
    with pytest.raises(ReadingError):
        Reading.load(tmp_path / "そんなファイルは無い.json")
