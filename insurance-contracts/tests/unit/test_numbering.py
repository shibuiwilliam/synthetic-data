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


def test_定款の附則は項番号で起こす() -> None:
    """定款の附則は「１」「２」、号は「（１）」（docs/shared_fixes.md C3）。"""
    c = ctx("teikan")
    assert label_for(c, "appendix_section", 1, in_appendix=True) == "第１"
    assert label_for(c, "paragraph", 1, in_appendix=True, siblings=3) == "１"
    assert label_for(c, "paragraph", 2, in_appendix=True, siblings=3) == "２"
    assert label_for(c, "item", 1, in_appendix=True) == "（１）"
    # 損保・生保の別表は従来どおり
    assert label_for(ctx(), "paragraph", 2, in_appendix=True, siblings=3) == "２．"
    assert label_for(ctx(), "item", 1, in_appendix=True) == "①"


def _teikan_index() -> DocumentIndex:
    body = [
        Node(
            id="ch3",
            kind="chapter",
            title="総代会",
            children=[Node(id="ch3_a1", kind="article", title="決議")],
        ),
        Node(
            id="ch4",
            kind="chapter",
            title="取締役",
            children=[Node(id="ch4_a1", kind="article", title="報酬等")],
        ),
    ]
    appendices = [
        Node(
            id="app1",
            kind="appendix",
            children=[
                Node(id="app1_s1", kind="appendix_section", title="施行期日"),
                Node(id="app1_s2", kind="appendix_section", title="経過措置"),
                Node(id="app1_s3", kind="appendix_section", title="定款の変更の経過"),
            ],
        )
    ]
    return DocumentIndex(ctx("teikan"), body, appendices)


@pytest.mark.parametrize(
    ("from_id", "to_id", "expected"),
    [
        # 条が全編通し番号なので章の冠を付けない（C2）
        ("ch3_a1", "ch4_a1", "第２条（報酬等）"),
        ("ch4_a1", "ch3_a1", "第１条（決議）"),
        # 附則の中の項目は「附則」を冠して参照する（C4）
        ("ch3_a1", "app1_s3", "附則第３"),
    ],
)
def test_定款の参照解決(from_id, to_id, expected) -> None:
    assert resolve_ref(_teikan_index(), from_id, to_id, "relative") == expected


def test_損保では章の冠が残る() -> None:
    """C2 は teikan 限定。条が章ごとに振り直される方式は章から書く。"""
    assert resolve_ref(_index(), "ch1_a1_p1", "ch4_s3_a1", "relative") == "第２章第１節第１条"


def test_団体保険の番号方式() -> None:
    """項＝丸数字（第1項は無番号）、号＝「１．」、細目＝(ｱ)（docs/reference_structures.md #12）。"""
    c = ctx("group", "halfwidth")
    assert label_for(c, "chapter", 2) == "第2章"
    assert label_for(c, "article", 23) == "第23条"
    assert label_for(c, "paragraph", 1, siblings=3) == ""
    assert label_for(c, "paragraph", 2, siblings=3) == "②"
    assert label_for(c, "item", 3) == "3．", "号のピリオドは全角（実物の体裁）"
    assert label_for(c, "subitem", 1) == "(ｱ)"


def test_条見出しを条の上に置くと条ラベルは第1項に走り込む() -> None:
    """docs/reference_structures.md #12 の体裁。`meta.article_heading = "above"`。"""
    c = NumberingContext(scheme="group", digit_style="halfwidth", article_heading="above")
    body = [
        Node(
            id="ch1",
            kind="chapter",
            title="保険金の支払",
            children=[
                Node(
                    id="ch1_a1",
                    kind="article",
                    title="死亡保険金の支払",
                    children=[Node(id="ch1_a1_p1", kind="paragraph"), Node(id="ch1_a1_p2", kind="paragraph")],
                )
            ],
        )
    ]
    labels = DocumentIndex(c, body).labels()
    assert labels["ch1_a1"].label == "第1条", "条のラベルは正解として残す"
    assert labels["ch1_a1"].heading_text == "（死亡保険金の支払）", "見出し行には見出し文言だけ"
    assert labels["ch1_a1_p1"].run_in_label == "第1条", "条ラベルは第1項の本文の先頭に走り込む"
    assert labels["ch1_a1_p1"].label == "", "第1項そのものは無番号"
    assert labels["ch1_a1_p2"].run_in_label is None


def test_備考欄のマーカーは黒丸数字() -> None:
    c = NumberingContext(scheme="group", footnote_style="remarks_box")
    assert footnote_marker(c, 1) == "❶"
    assert footnote_marker(c, 3) == "❸"
    # 既定の体裁は変わらない
    assert footnote_marker(NumberingContext(scheme="group"), 1) == "（*１）"


def test_重要事項説明書は条を持たない番号方式() -> None:
    """大見出しは番号のみ、節は（N）、条の位置に丸数字（docs/reference_structures.md #9）。"""
    c = ctx("jyusetsu", "halfwidth")
    assert label_for(c, "chapter", 2) == "2"
    assert label_for(c, "section", 1) == "(1)"
    assert label_for(c, "article", 3) == "③"
    assert label_for(c, "paragraph", 2, siblings=3) == "", "項に番号は振らない"


def test_plainの条見出しは括弧を使わない() -> None:
    assert heading_text("article", "③", "主な特約の概要", "plain") == "③　主な特約の概要"
    # 既定の体裁は変わらない
    assert heading_text("article", "第１条", "告知義務") == "第１条（告知義務）"


def test_無番号の項を指す参照は第N項と書き下す() -> None:
    """group / teikan は第1項が無番号なので、そのまま連ねると空文字になる（#12 で実際に起きた）。"""
    c = NumberingContext(scheme="group", digit_style="halfwidth")
    body = [
        Node(
            id="ch1",
            kind="chapter",
            title="保険金の支払",
            children=[
                Node(
                    id="ch1_a1",
                    kind="article",
                    title="死亡保険金の支払",
                    children=[
                        Node(
                            id="ch1_a1_p1",
                            kind="paragraph",
                            children=[
                                Node(id="ch1_a1_p1_i1", kind="item"),
                                Node(id="ch1_a1_p1_i2", kind="item"),
                            ],
                        ),
                        Node(id="ch1_a1_p2", kind="paragraph"),
                    ],
                )
            ],
        )
    ]
    index = DocumentIndex(c, body)
    assert resolve_ref(index, "ch1_a1_p2", "ch1_a1_p1") == "第1項"
    assert resolve_ref(index, "ch1_a1_p2", "ch1_a1_p1_i2") == "第1項第2号"
    # 印字は無番号のまま（参照の書き下し方だけが違う）
    assert index.labels()["ch1_a1_p1"].label == ""
    # 損保は印字どおり「（２）」を連ねる
    assert resolve_ref(_index(), "ch4_s3_a1_p1", "ch4_s3_a1_p2") == "（２）"


def test_章番号を含む表番号() -> None:
    """docs/reference_structures.md #14 の「表1-1」「表3-2」（`meta.caption_numbering: chapter`）。"""
    from yakkan.build import assign_caption_labels
    from yakkan.models import Figure, Flowchart, SourceDraft, Table

    def table(tid: str, caption: str) -> Table:
        return Table.model_validate(
            {
                "id": tid,
                "caption": caption,
                "semantic_type": "generic",
                "layout": {"header_rows": 0, "col_widths": [50, 50]},
                "grid": [
                    [
                        {"id": f"{tid}__r0c0", "text": "あ"},
                        {"id": f"{tid}__r0c1", "text": "い"},
                    ]
                ],
            }
        )

    def figure(fid: str) -> Figure:
        return Figure(
            id=fid,
            caption="流れ",
            alt="説明",
            facts=["事実"],
            diagram=Flowchart.model_validate(
                {
                    "kind": "flowchart",
                    "nodes": [
                        {"id": "a", "label": "甲", "shape": "start", "col": 0, "row": 0},
                        {"id": "b", "label": "乙", "shape": "end", "col": 0, "row": 1},
                    ],
                    "edges": [{"from": "a", "to": "b"}],
                }
            ),
        )

    body = [
        Node(id="ch1", kind="chapter", title="第一", blocks=[table("t1", "あ"), table("t2", "い")]),
        Node(id="ch2", kind="chapter", title="第二", blocks=[table("t3", "う"), figure("f1")]),
    ]
    base = {
        "content_id": "x",
        "genre": "group",
        "seed": 1,
        "meta": {
            "title": "t",
            "issuer": {"name": "n", "kind": "stock", "short_name": "n"},
            "product_name": "p",
            "edition_date": "2026-10-01",
            "form_code": "F1",
            "numbering_scheme": "group",
            "digit_style": "halfwidth",
            "disclaimer": "d",
        },
        "front_matter": {"cover": {"title": "t", "issuer_name": "n", "form_code": "F1"}},
        "body": [n.model_dump(mode="json") for n in body],
    }
    flat = SourceDraft.model_validate(base)
    assert assign_caption_labels(flat, ctx("group", "halfwidth")) == {
        "t1": "表1",
        "t2": "表2",
        "t3": "表3",
        "f1": "図1",
    }

    scoped = SourceDraft.model_validate({**base, "meta": {**base["meta"], "caption_numbering": "chapter"}})
    assert assign_caption_labels(scoped, ctx("group", "halfwidth")) == {
        "t1": "表1-1",
        "t2": "表1-2",
        "t3": "表2-1",
        "f1": "図2-1",
    }, "章ごとに振り直す"

    # 章に属さない表（別表の中）には番号を振らない（docs/remaining_issues.md S2）。
    # 通し採番のままだと「表1-1」と「表1」が同居し、読み取りの正解として紛らわしい。
    outside = {
        **base,
        "meta": {**base["meta"], "caption_numbering": "chapter"},
        "appendices": [
            Node(id="app1", kind="appendix", title="別表", blocks=[table("t9", "え")]).model_dump(mode="json")
        ],
    }
    labels = assign_caption_labels(SourceDraft.model_validate(outside), ctx("group", "halfwidth"))
    assert "t9" not in labels, "章の外の表には番号を振らない"
    assert labels["t3"] == "表2-1", "章の中の採番は変わらない"

    flat_outside = SourceDraft.model_validate({**outside, "meta": base["meta"]})
    assert assign_caption_labels(flat_outside, ctx("group", "halfwidth"))["t9"] == "表4", (
        "通し採番のときは章の外も番号を振る"
    )


def test_章の外の表を参照するとL01が落ちる() -> None:
    """番号の無い表は `{ref:}` の参照先にできない（docs/remaining_issues.md S2）。

    以前はキャプションの有無だけで判定していたので、`caption_numbering: chapter` で
    章の外の表を参照すると lint を素通りし、build が `BuildError` で落ちていた。
    """
    from yakkan.lint.runner import lint_draft
    from yakkan.models import SourceDraft, Table

    def table(tid: str) -> Table:
        return Table.model_validate(
            {
                "id": tid,
                "caption": "高度障害状態",
                "semantic_type": "generic",
                "layout": {"header_rows": 0, "col_widths": [50, 50]},
                "grid": [[{"id": f"{tid}__r0c0", "text": "あ"}, {"id": f"{tid}__r0c1", "text": "い"}]],
            }
        )

    base = {
        "content_id": "x",
        "genre": "group",
        "seed": 1,
        "meta": {
            "title": "t",
            "issuer": {"name": "n", "kind": "stock", "short_name": "n"},
            "product_name": "p",
            "edition_date": "2026-10-01",
            "form_code": "F1",
            "numbering_scheme": "group",
            "digit_style": "halfwidth",
            "disclaimer": "d",
            "caption_numbering": "chapter",
        },
        "front_matter": {"cover": {"title": "t", "issuer_name": "n", "form_code": "F1"}},
        "body": [
            Node(
                id="ch1",
                kind="chapter",
                title="第一",
                children=[Node(id="ch1_a1", kind="article", title="第一条", text="{ref:t9}によります。")],
            ).model_dump(mode="json")
        ],
        "appendices": [
            Node(id="app1", kind="appendix", title="別表", blocks=[table("t9")]).model_dump(mode="json")
        ],
    }
    findings = lint_draft(SourceDraft.model_validate(base), only=["L01"])
    messages = [f.message for f in findings if f.severity == "error"]
    assert any("t9" in m and "章に属さない" in m for m in messages), messages
