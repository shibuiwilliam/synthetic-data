"""配布パッケージ（S10-6・`HITL.md` H4 (c)）。

H4 で「正解も含めて配る」と決まった。守るのは 3 点。

1. 配布物（軸 B）には正解が**入る**。
2. 採点のときに渡すもの（軸 A・`icc export`）には正解が**入らない**。この線は H4 で変えていない。
3. 汚染の注意と作り直し方が書いてある（正解を配るのだから、書いていないと使えない）。
"""

from __future__ import annotations

from pathlib import Path

from conftest import EXAMPLE_DOC, needs_base

from insurance_contracts_calculation.export.distribution import build
from insurance_contracts_calculation.export.layout import PRIVATE

ANSWER_FILES = ("spec.json", "answer_key.json", "cases.jsonl")


@needs_base
def test_the_distribution_contains_the_answers(tmp_path: Path) -> None:
    """軸 B：配布物には正解が入る。"""
    index = build(EXAMPLE_DOC.parent, tmp_path / "dist", version="test", generator_version="0.0.0")
    assert index["contains_answers"] is True
    doc = tmp_path / "dist" / "documents" / EXAMPLE_DOC.name
    for name in ANSWER_FILES:
        assert (doc / "calc" / name).is_file(), f"配布物に {name} が無い"
    assert list((doc / "calc" / "programs").glob("*.py")), "配布物に正解プログラムが無い"
    assert (doc / "calc" / "tests").is_dir(), "配布物に pytest が無い"


@needs_base
def test_the_export_for_scoring_still_hides_the_answers(tmp_path: Path) -> None:
    """軸 A：採点のときに渡すものには正解が入らない（H4 でもこの線は変えない）。"""
    from insurance_contracts_calculation.export.datasheet import export_public

    out = tmp_path / "public"
    export_public(EXAMPLE_DOC, out)
    leaked = [p for p in out.rglob("*") if p.is_file() and p.name in PRIVATE]
    assert not leaked, f"採点用のパッケージに正解が混ざった: {[p.name for p in leaked]}"
    assert not list(out.rglob("programs/*.py")), "正解プログラムが混ざった"


@needs_base
def test_the_distribution_warns_about_contamination(tmp_path: Path) -> None:
    """正解を配るので、汚染の注意と作り直し方を必ず書く。"""
    build(EXAMPLE_DOC.parent, tmp_path / "dist", version="test", generator_version="0.0.0")
    readme = (tmp_path / "dist" / "README.md").read_text(encoding="utf-8")
    sheet = (tmp_path / "dist" / "DATASHEET.md").read_text(encoding="utf-8")
    assert "学習" in readme and "使わないで" in readme, "学習に使わない注意が無い"
    assert "作り直" in readme, "作り直し方が書かれていない"
    assert "icc export" in readme, "採点時に渡すものを絞る方法が書かれていない"
    assert "架空" in readme and "架空" in sheet
    assert (tmp_path / "dist" / "LICENSE").is_file()


@needs_base
def test_the_index_records_what_is_needed_to_regenerate(tmp_path: Path) -> None:
    """作り直せるように seed と profile を残す（決定的に生成できることが前提）。"""
    index = build(EXAMPLE_DOC.parent, tmp_path / "dist", version="test", generator_version="0.0.0")
    for e in index["documents"]:
        assert e["seed"] is not None, f"{e['doc_id']} に seed が無い"
        assert e["rules"] > 0
    assert index["generator_version"] == "0.0.0"
    assert index["files"], "ファイルのハッシュが入っていない"


@needs_base
def test_the_intermediate_html_is_not_distributed(tmp_path: Path) -> None:
    """`render.html` は生成の中間物なので配らない。"""
    build(EXAMPLE_DOC.parent, tmp_path / "dist", version="test", generator_version="0.0.0")
    assert not list((tmp_path / "dist").rglob("render.html"))
