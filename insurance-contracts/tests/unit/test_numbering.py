"""番号付けとラベル導出（docs/rendering.md §6.4）。"""

from __future__ import annotations

import pytest

from yakkan.models import Node
from yakkan.numbering import (
    CIRCLED_MAX,
    DocumentIndex,
    NumberingContext,
    appendix_label,
    circled,
    footnote_marker,
    heading_text,
    label_for,
    resolve_ref,
    to_digits,
)


def ctx(scheme="nonlife", digits="fullwidth") -> NumberingContext:
    return NumberingContext(scheme=scheme, digit_style=digits)


@pytest.mark.parametrize(
    ("scheme", "kind", "index", "expected"),
    [
        ("nonlife", "chapter", 1, "第１章"),
        ("nonlife", "section", 3, "第３節"),
        ("nonlife", "article", 12, "第１２条"),
        ("nonlife", "paragraph", 2, "（２）"),
        ("nonlife", "item", 3, "③"),
        ("nonlife", "subitem", 1, "ｱ."),
        ("nonlife", "subsubitem", 2, "（ｲ）"),
        ("life", "paragraph", 2, "２．"),
        # 括弧の全角/半角は digit_style が決める（docs/decisions.md 2026-09-21）
        ("life", "item", 2, "（２）"),
        ("life", "subitem", 3, "③"),
        ("life", "subsubitem", 1, "ｱ"),
        ("teikan", "chapter", 2, "第２章"),
        ("teikan", "article", 5, "第５条"),
        ("teikan", "paragraph", 2, "２"),
        ("teikan", "item", 1, "（１）"),
    ],
)
def test_方式ごとのラベル(scheme, kind, index, expected) -> None:
    assert label_for(ctx(scheme), kind, index, siblings=9) == expected


def test_単項は無番号() -> None:
    assert label_for(ctx(), "paragraph", 1, siblings=1) == ""
    assert label_for(ctx(), "paragraph", 1, siblings=2) == "（１）"


def test_teikan_の第1項は無番号() -> None:
    assert label_for(ctx("teikan"), "paragraph", 1, siblings=3) == ""
    assert label_for(ctx("teikan"), "paragraph", 2, siblings=3) == "２"


def test_半角指定() -> None:
    assert label_for(ctx(digits="halfwidth"), "article", 3) == "第3条"
    assert label_for(ctx(digits="halfwidth"), "paragraph", 2, siblings=2) == "(2)"
    assert label_for(ctx("life", "halfwidth"), "item", 2) == "(2)"
    assert to_digits(12, "fullwidth") == "１２"


def test_丸数字は20までで打ち切り警告する() -> None:
    c = ctx()
    assert circled(20, "fullwidth", c.warnings) == "⑳"
    assert not c.warnings
    assert circled(21, "fullwidth", c.warnings, "ch1_p1_i21") == "（２１）"
    assert len(c.warnings) == 1
    assert "２１" in circled(21, "fullwidth", None) or "21" in circled(21, "halfwidth", None)
    assert CIRCLED_MAX == 20


def test_別紙は独立体系() -> None:
    c = ctx()
    assert label_for(c, "appendix_section", 1, in_appendix=True) == "第１"
    assert label_for(c, "paragraph", 2, in_appendix=True, siblings=3) == "２．"
    assert label_for(c, "item", 1, in_appendix=True) == "①"
    assert label_for(c, "subitem", 2, in_appendix=True) == "ｲ."


def test_別表と附則のラベル() -> None:
    assert appendix_label(ctx(), 2) == "別表２"
    assert appendix_label(ctx(), 1, "付表") == "付表１"
    assert appendix_label(ctx("teikan"), 1) == "附則"


def test_脚注マーカー() -> None:
    assert footnote_marker(ctx(), 1) == "（*１）"
    assert footnote_marker(ctx("life"), 2) == "（注２）"


def test_見出し文字列は条だけ括弧() -> None:
    assert heading_text("article", "第１条", "告知義務") == "第１条（告知義務）"
    assert heading_text("chapter", "第１章", "基本条項") == "第１章　基本条項"
    assert heading_text("paragraph", "（２）", None) == "（２）"
    assert heading_text("paragraph", "", "") == ""


def _tree() -> list[Node]:
    return [
        Node(
            id="ch1",
            kind="chapter",
            title="賠償責任条項",
            children=[
                Node(
                    id="ch1_a1",
                    kind="article",
                    title="補償内容",
                    children=[
                        Node(id="ch1_a1_p1", kind="paragraph"),
                        Node(id="ch1_a1_p2", kind="paragraph"),
                    ],
                )
            ],
        ),
        Node(
            id="ch4",
            kind="chapter",
            title="基本条項",
            children=[
                Node(
                    id="ch4_s3",
                    kind="section",
                    title="事故発生時の義務",
                    children=[
                        Node(
                            id="ch4_s3_a1",
                            kind="article",
                            title="お支払いする保険金",
                            children=[
                                Node(id="ch4_s3_a1_p1", kind="paragraph"),
                                Node(id="ch4_s3_a1_p2", kind="paragraph"),
                            ],
                        ),
                        Node(id="ch4_s3_a2", kind="article", title="通知義務"),
                    ],
                )
            ],
        ),
    ]


def _index() -> DocumentIndex:
    appendices = [Node(id="app1", kind="appendix", title="後遺障害等級表")]
    return DocumentIndex(ctx(), _tree(), appendices)


@pytest.mark.parametrize(
    ("from_id", "to_id", "mode", "expected"),
    [
        # 同じ条の中の項 → 項番号だけ
        ("ch4_s3_a1_p1", "ch4_s3_a1_p2", "relative", "（２）"),
        # 同じ節の別の条 → 条番号＋見出し文言
        ("ch4_s3_a1_p1", "ch4_s3_a2", "relative", "第２条（通知義務）"),
        # 別の条の項 → 条＋見出し文言＋項番号
        ("ch4_s3_a2", "ch4_s3_a1_p1", "relative", "第１条（お支払いする保険金）（１）"),
        # 別の章 → 章・節まで遡るので見出し文言は付けない
        ("ch1_a1_p1", "ch4_s3_a1", "relative", "第２章第１節第１条"),
        # short は条まで・見出し文言なし
        ("ch4_s3_a2", "ch4_s3_a1_p1", "short", "第１条"),
        ("ch1_a1_p1", "ch4_s3_a1_p2", "short", "第２章第１節第１条"),
        # full は根からの絶対表記＋見出し文言
        ("ch4_s3_a2", "ch4_s3_a1_p1", "full", "第２章第１節第１条（お支払いする保険金）（１）"),
        # 別表
        ("ch1_a1_p1", "app1", "relative", "別表１"),
    ],
)
def test_参照解決(from_id, to_id, mode, expected) -> None:
    assert resolve_ref(_index(), from_id, to_id, mode) == expected


def test_参照先が無ければ例外() -> None:
    with pytest.raises(KeyError):
        resolve_ref(_index(), "ch1_a1_p1", "nowhere")


def test_ラベルは位置で決まりidの数字とは独立() -> None:
    """id は安定 id。`ch4` が 2 番目の章なら「第２章」になる。"""
    labels = _index().labels()
    assert labels["ch4"].label == "第２章"
    assert labels["ch4"].heading_text == "第２章　基本条項"
    assert labels["ch4_s3_a1"].path == ["第２章　基本条項", "第１節　事故発生時の義務"]
    assert labels["ch4_s3_a1"].depth == 2
