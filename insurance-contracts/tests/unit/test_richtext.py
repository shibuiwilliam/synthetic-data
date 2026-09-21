"""RichText のトークナイザと平文化（docs/schema.md §5.3）。"""

from __future__ import annotations

import pytest

from yakkan.richtext import (
    AutoLabel,
    Bold,
    Br,
    Const,
    Fn,
    PlainContext,
    Ref,
    RichTextError,
    Ruby,
    Term,
    Text,
    Underline,
    parse,
    plain,
    raw_text,
    with_label,
)


def full_ctx() -> PlainContext:
    return PlainContext(
        resolve_ref=lambda target, mode: {"relative": "（１）", "short": "第１条", "full": "第１章第１条"}[
            mode
        ],
        resolve_term=lambda term_id: {"policyholder": "保険契約者"}[term_id],
        resolve_const=lambda key: {"limit": "1,000万円"}[key],
    )


def test_地の文だけ() -> None:
    assert parse("当会社は、保険金を支払います。") == (Text("当会社は、保険金を支払います。"),)


def test_全トークンを解釈する() -> None:
    nodes = parse(
        "{ref:a}{ref:b|short}{ref:c|full}{fn:2}{term:x}{b:太}{u:下}{ruby:遅滞|ちたい}{br}{const:k}{auto_label}"
    )
    assert nodes == (
        Ref("a", "relative"),
        Ref("b", "short"),
        Ref("c", "full"),
        Fn(2),
        Term("x"),
        Bold((Text("太"),)),
        Underline((Text("下"),)),
        Ruby("遅滞", "ちたい"),
        Br(),
        Const("k"),
        AutoLabel(),
    )


def test_入れ子と平文化() -> None:
    ctx = full_ctx()
    text = "{b:重要{u:な{term:policyholder}}}は{const:limit}を確認"
    assert plain(text, ctx) == "重要な保険契約者は1,000万円を確認"
    assert ctx.used_terms == ["policyholder"]
    assert ctx.used_consts == ["limit"]


def test_エスケープ() -> None:
    assert plain("{{ref:a}}", PlainContext()) == "{ref:a}"
    assert plain("100{{}}", PlainContext()) == "100{}"


def test_囲みトークンの入れ子は内側から閉じる() -> None:
    """`{b:重要{u:な}}` の末尾 '}}' はエスケープではなく 2 段の閉じ括弧。"""
    assert plain("{b:重要{u:な}}です", PlainContext()) == "重要なです"


def test_ルビは基底文字だけを平文にする() -> None:
    ctx = PlainContext()
    assert plain("{ruby:遅滞|ちたい}なく", ctx) == "遅滞なく"
    assert ctx.rubies == [("遅滞", "ちたい")]
    assert plain("{ruby:遅滞|ちたい}", PlainContext(ruby_with_reading=True)) == "遅滞（ちたい）"


def test_脚注マーカーと改行() -> None:
    assert plain("装置{fn:1}を{br}付ける", PlainContext()) == "装置（*1）を\n付ける"


def test_参照は解決関数に委ねる() -> None:
    ctx = full_ctx()
    assert plain("{ref:x}と{ref:y|short}", ctx) == "（１）と第１条"
    assert ctx.used_refs == [("x", "relative", "（１）"), ("y", "short", "第１条")]


def test_ラベル付き平文() -> None:
    assert with_label("（２）", "当会社は…") == "（２）当会社は…"
    assert with_label("", "当会社は…") == "当会社は…"
    assert with_label("第１条", "告知義務", "　") == "第１条　告知義務"


def test_地の文の抽出はトークンを除く() -> None:
    """強調の中の文字も地の文に含める（太字の「第１条」も L03 で捕まえるため）。"""
    assert raw_text(parse("当会社は{ref:a}の{b:とおり}支払います")) == "当会社はのとおり支払います"


@pytest.mark.parametrize(
    "source",
    [
        "{unknown:x}",
        "{ref}",
        "{ref:}",
        "{ref:a|middle}",
        "{fn:0}",
        "{fn:x}",
        "{term:}",
        "{b:}",
        "{b:閉じない",
        "{ruby:漢字}",
        "{const:}",
        "}",
        "{ref:{term:x}}",
        "{br:1}",
    ],
)
def test_不正な記法はエラー(source: str) -> None:
    with pytest.raises(RichTextError):
        parse(source)


def test_エラーは位置を持つ() -> None:
    with pytest.raises(RichTextError) as exc:
        parse("正しい文です。{bad:x}")
    assert exc.value.position == 7
