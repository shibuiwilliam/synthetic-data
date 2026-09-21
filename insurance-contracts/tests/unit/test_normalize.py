"""正規化ルール（docs/rendering.md §6.9）の固定。"""

from __future__ import annotations

from yakkan.verify.normalize import Line, normalize, page_text, reading_order


def test_空白だけを落とす() -> None:
    assert normalize("第１章　補償の概要") == "第１章補償の概要"
    assert normalize("あ\nい う") == "あいう"


def test_全角半角の区別は保持する() -> None:
    assert normalize("１％（２）") != normalize("1%(2)")
    assert normalize("ｱ") != normalize("ア")


def test_2段組の読み順は左段から右段へ() -> None:
    lines = [
        Line("見出し", 10, 0, 500, "body", "span"),
        Line("左1", 20, 0, 200, "body", "left"),
        Line("右1", 20, 300, 500, "body", "right"),
        Line("左2", 30, 0, 200, "body", "left"),
        Line("右2", 30, 300, 500, "body", "right"),
        Line("段またぎ表", 40, 0, 500, "body", "span"),
        Line("左3", 50, 0, 200, "body", "left"),
    ]
    assert [ln.text for ln in reading_order(lines)] == [
        "見出し",
        "左1",
        "左2",
        "右1",
        "右2",
        "段またぎ表",
        "左3",
    ]


def test_ヘッダフッタは本文の読み順に入らない() -> None:
    lines = [
        Line("章名", 5, 0, 100, "header", "span"),
        Line("本文", 50, 0, 500, "body", "span"),
        Line("1", 800, 280, 300, "footer", "span"),
    ]
    assert page_text(lines, "body") == "本文"
    assert page_text(lines, "header") == "章名"
    assert page_text(lines, "footer") == "1"
