"""条末脚注の印の表示文字列が、文書の `meta` どおりになること。

`（*1）` に決め打ちすると、既定の約款の多数派（`digit_style: fullwidth` が 90 件中 55 件）で
根拠の引用が原文と 1 文字違い、G2「根拠の照合」が落ちる。落ちた文書はバッチが seed を
ずらして組み直すので、**黙って脚注の分散だけが消える**。それを止めるための回帰テスト。
"""

from __future__ import annotations

import pytest

from insurance_contracts_calculation.core.docindex import Doc

BASE = {
    "content_id": "t-0001",
    "meta": {"constants": {}},
    "front_matter": {},
    "body": [],
    "appendices": [],
    "back_matter": {},
    "defined_terms": [],
    "derived": {"labels": {}, "plain_text": {}, "refs": [], "tables": {}, "figures": {}},
}


def _doc(**meta) -> Doc:
    data = {**BASE, "meta": {**BASE["meta"], **meta}}
    return Doc(None, data)


@pytest.mark.parametrize(
    ("meta", "expect"),
    [
        ({"digit_style": "halfwidth", "numbering_scheme": "nonlife"}, "（*1）"),
        ({"digit_style": "fullwidth", "numbering_scheme": "nonlife"}, "（*１）"),
        ({"digit_style": "halfwidth", "numbering_scheme": "life"}, "（注1）"),
        ({"digit_style": "fullwidth", "numbering_scheme": "life"}, "（注１）"),
        ({"digit_style": "fullwidth", "numbering_scheme": "group", "footnote_style": "remarks_box"}, "❶"),
        ({}, "（*1）"),  # meta に何も無ければ nonlife・halfwidth
    ],
)
def test_the_marker_follows_the_document_meta(meta: dict, expect: str) -> None:
    assert _doc(**meta).resolve("…とします{fn:1}。") == f"…とします{expect}。"


def test_the_marker_counts_up() -> None:
    doc = _doc(digit_style="fullwidth", numbering_scheme="nonlife")
    assert doc.resolve("{fn:1}{fn:2}{fn:10}") == "（*１）（*２）（*１０）"


def test_remarks_box_falls_back_past_the_last_black_circle() -> None:
    doc = _doc(numbering_scheme="group", footnote_style="remarks_box")
    assert doc.resolve("{fn:10}") == "❿"
    assert doc.resolve("{fn:11}") == "(11)"
