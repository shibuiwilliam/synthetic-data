"""id 命名規則（yakkan/ids.py）。"""

from __future__ import annotations

import pytest

from yakkan.ids import (
    block_id,
    block_id_matches_type,
    cell_id,
    figure_node_id,
    is_child_id_of,
    is_valid_node_id,
    node_id,
    node_id_matches_kind,
    parse_cell_id,
    parse_figure_node_id,
)


def test_ノードidは親を接頭辞に持つ() -> None:
    assert node_id(None, "chapter", 4) == "ch4"
    assert node_id("ch4", "section", 3) == "ch4_s3"
    assert node_id("ch4_s3", "article", 1) == "ch4_s3_a1"
    assert node_id("ch4_s3_a1", "paragraph", 2) == "ch4_s3_a1_p2"
    assert node_id("ch4_s3_a1_p2", "item", 3) == "ch4_s3_a1_p2_i3"
    assert node_id(None, "appendix", 1) == "app1"
    assert node_id("app1", "appendix_section", 2) == "app1_s2"


def test_ルート直下に置けない種別() -> None:
    with pytest.raises(ValueError):
        node_id(None, "article", 1)


def test_ブロックidの接頭辞() -> None:
    assert block_id("table", "notify_facts") == "tbl_notify_facts"
    assert block_id("figure", "accident_flow") == "fig_accident_flow"
    assert block_id_matches_type("tbl_x", "table")
    assert not block_id_matches_type("fig_x", "table")
    with pytest.raises(ValueError):
        block_id("table", "NotifyFacts")


def test_セルと図ノードのid() -> None:
    assert cell_id("tbl_notify_facts", 1, 0) == "tbl_notify_facts__r1c0"
    assert parse_cell_id("tbl_notify_facts__r1c0") == ("tbl_notify_facts", 1, 0)
    assert figure_node_id("fig_flow", 3) == "fig_flow__n3"
    assert parse_figure_node_id("fig_flow__n3") == ("fig_flow", 3)
    assert parse_cell_id("tbl_x") is None


def test_親子判定() -> None:
    assert is_child_id_of("ch4_s3", "ch4")
    assert not is_child_id_of("ch4_s3_a1", "ch4")
    assert not is_child_id_of("ch40", "ch4")
    assert is_valid_node_id("ch4_s3_a1_p2")
    assert not is_valid_node_id("chapter_four")
    assert node_id_matches_kind("ch4_s3_a1", "article")
    assert not node_id_matches_kind("ch4_s3_a1", "section")
