"""docmodel.index：本体の実物 content（条文型・約款型・様式型・頭書型）を索引化できる。"""

import pytest

from contracts_calculation import base_adapter
from contracts_calculation.docmodel.index import DocumentIndex

# 5 類型のうち 4 doctype を対象にする（条文型 ots／約款型 con／様式型 emp／頭書型 lea）
CIDS = ["ots-0001", "con-0001", "emp-0001", "lea-0001"]


@pytest.fixture(scope="module", params=CIDS)
def index(request) -> DocumentIndex:
    content_dir = base_adapter.repo_root() / "content" / request.param
    return DocumentIndex.load(content_dir)


def test_loads_and_has_units(index: DocumentIndex) -> None:
    assert len(index.units) > 20
    assert index.parties, "契約書には当事者が必須"
    assert all(p.alias and p.name for p in index.parties.values())


def test_constants_present(index: DocumentIndex) -> None:
    assert index.constants, "本体の content は meta.constants を持つ"


def test_quote_in_unit_ots() -> None:
    idx = DocumentIndex.load(base_adapter.repo_root() / "content" / "ots-0001")
    # 第1条第1項の冒頭（実物の文字列）
    assert idx.quote_in_unit("a1_p1", "甲は乙に本件業務を委託し")
    assert not idx.quote_in_unit("a1_p1", "存在しない文字列")


def test_table_cell_is_unit_con() -> None:
    idx = DocumentIndex.load(base_adapter.repo_root() / "content" / "con-0001")
    cell_ids = [uid for uid in idx.units if "__r" in uid]
    assert cell_ids, "表セルも単位になる"
    assert idx.quote_in_unit("tbl_part__r1c2", "２割")


def test_citation_format() -> None:
    idx = DocumentIndex.load(base_adapter.repo_root() / "content" / "ots-0001")
    a1 = idx.unit("a1")
    assert a1.kind == "article"
    assert a1.citation.startswith("第1条")
