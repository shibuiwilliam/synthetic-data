"""base_adapter：能力の宣言、content 一覧、書き込み先の防護、build の往復。"""

import shutil

import pytest

from contracts_calculation import base_adapter


def test_capabilities() -> None:
    caps = base_adapter.capabilities()
    assert caps.table and caps.header_sheet and caps.formula
    assert "flowchart" in caps.figure_kinds and "timeline" in caps.figure_kinds
    assert caps.constants == "dictionary"
    assert "head_matter" in caps.node_kinds and "appendix" in caps.node_kinds


def test_list_base_contents() -> None:
    contents = base_adapter.list_base_contents()
    assert len(contents) >= 20
    names = [p.name for p in contents]
    assert "ots-0001" in names and "emp-0002" in names

    v1 = base_adapter.list_v1_base_contents()
    assert len(v1) == 20
    assert [p.name for p in v1] == list(base_adapter.V1_BASE_CONTENT_IDS)


def test_write_guard_rejects_parent_paths(tmp_path) -> None:
    with pytest.raises(ValueError):
        base_adapter.run_build(base_adapter.repo_root() / "content" / "ots-0001")


def test_build_roundtrip(tmp_path) -> None:
    """content をサブプロジェクト配下へコピーし、本体の build で索引を再計算できる。"""
    src = base_adapter.repo_root() / "content" / "nda-0001"
    work = base_adapter.calc_root() / "data" / "_tmp_test" / "nda-0001"
    if work.parent.exists():
        shutil.rmtree(work.parent)
    shutil.copytree(src, work)
    try:
        base_adapter.run_build(work)
        rebuilt = base_adapter.load_source(work)
        assert rebuilt.get("derived"), "build が derived を付け直す"
    finally:
        shutil.rmtree(work.parent, ignore_errors=True)
