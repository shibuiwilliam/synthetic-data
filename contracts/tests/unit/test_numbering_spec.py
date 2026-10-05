"""宣言的 numbering（`numbering/<scheme>.yaml` ＋ 解釈器）の検証（P2-2）。

2 つのことを固定する。

1. **表現力**：yakkan の 5 方式（nonlife / life / teikan / group / jyusetsu）を宣言で書き下したものが、
   置き換え前の Python 実装と**全 kind × 位置 × digit_style × 単項数 × 別表内外**で同一の
   ラベル・別表ラベル・脚注マーカー・見出し文字列・`{ref:}` 解決を出すこと
   （`tests/golden/numbering_legacy.json`。`scripts/capture_numbering_golden.py` が作る）。
   宣言で書けない規則があれば、ここが赤くなる（docs/schema.md §7）。
2. **契約書の 2 方式**が意図どおりのラベルを出すこと（`contract-standard` / `contract-form`）。

保険の 5 方式は `tests/fixtures/numbering/` に置いてある（**検証専用**。契約書の生成には使わない）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from keiyaku.models import Node
from keiyaku.numbering import (
    DocumentIndex,
    NumberingContext,
    appendix_label,
    footnote_marker,
    heading_text,
    label_for,
    resolve_ref,
)
from keiyaku.numbering_spec import NUMBERING_DIR, available_schemes, load_scheme, parse_scheme

GOLDEN = Path(__file__).resolve().parents[1] / "golden" / "numbering_legacy.json"
LEGACY_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "numbering"

# capture スクリプトと同じ総当たりの軸（ずれると比較にならないので、ここを正とする）
SCHEMES = ("nonlife", "life", "teikan", "group", "jyusetsu")
KINDS = (
    "part",
    "chapter",
    "section",
    "article",
    "paragraph",
    "item",
    "subitem",
    "subsubitem",
    "appendix_section",
)
DIGITS = ("fullwidth", "halfwidth")
INDEXES = (1, 2, 3, 10, 12, 21)
SIBLINGS = (1, 3)


@pytest.fixture(scope="module")
def legacy() -> dict:
    if not GOLDEN.is_file():
        pytest.skip("numbering_legacy.json が無い（scripts/capture_numbering_golden.py で作る）")
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _ctx(scheme: str, digit: str = "fullwidth", **kw) -> NumberingContext:
    return NumberingContext(scheme=scheme, digit_style=digit, numbering_dir=LEGACY_DIR, **kw)  # type: ignore[arg-type]


# --- 1. 表現力：置き換え前の実装と同一か -------------------------------------


def test_保険5方式の宣言が読める() -> None:
    assert set(available_schemes(LEGACY_DIR)) == set(SCHEMES)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_ラベルが置き換え前と一致する(legacy: dict, scheme: str) -> None:
    """全 kind × 位置 × digit_style × 単項数 × 別表内外。警告の文言まで含めて比べる。"""
    mismatches: list[str] = []
    for digit in DIGITS:
        for kind in KINDS:
            for n in INDEXES:
                for siblings in SIBLINGS:
                    for in_appendix in (False, True):
                        key = f"{scheme}|{digit}|{kind}|{n}|{siblings}|{int(in_appendix)}"
                        want = legacy["labels"][key]
                        ctx = _ctx(scheme, digit)
                        got = label_for(
                            ctx,
                            kind,
                            n,
                            node_id="x",
                            siblings=siblings,
                            scope="appendix" if in_appendix else "body",
                        )
                        warnings = [w.message for w in ctx.warnings]
                        if got != want["label"] or warnings != want["warnings"]:
                            mismatches.append(
                                f"{key}: got={got!r}/{warnings} want={want['label']!r}/{want['warnings']}"
                            )
    assert not mismatches, f"{len(mismatches)} 件ずれた\n" + "\n".join(mismatches[:15])


@pytest.mark.parametrize("scheme", SCHEMES)
def test_別表ラベルが置き換え前と一致する(legacy: dict, scheme: str) -> None:
    for digit in DIGITS:
        for index in (1, 2, 3):
            for kind_label in (None, "付表", "別紙"):
                key = f"{scheme}|{digit}|{index}|{kind_label or '-'}"
                assert (
                    appendix_label(_ctx(scheme, digit), index, kind_label) == legacy["appendix_labels"][key]
                ), key


@pytest.mark.parametrize("scheme", SCHEMES)
def test_脚注マーカーが置き換え前と一致する(legacy: dict, scheme: str) -> None:
    for digit in DIGITS:
        for style in ("inline", "remarks_box"):
            for n in (1, 2, 11):
                key = f"{scheme}|{digit}|{style}|{n}"
                ctx = _ctx(scheme, digit, footnote_style=style)
                assert footnote_marker(ctx, n) == legacy["footnotes"][key], key


def test_見出し文字列が置き換え前と一致する(legacy: dict) -> None:
    """`heading_text` は方式に依らない（ラベルと文言の連結規則だけ）。"""
    for kind in ("chapter", "article", "item"):
        for article_heading in ("inline", "above", "plain"):
            for label, title in (("第１条", "目的"), ("", "目的"), ("第１条", None)):
                key = f"{kind}|{article_heading}|{label or '-'}|{title or '-'}"
                assert heading_text(kind, label, title, article_heading) == legacy["headings"][key], key


def _tree() -> tuple[list[Node], list[Node]]:
    """`scripts/capture_numbering_golden.py` と同じ木（比較のため形を揃える）。"""
    body = [
        Node(
            id="ch1",
            kind="chapter",
            title="第一の章",
            children=[
                Node(
                    id="ch1_a1",
                    kind="article",
                    title="目的",
                    children=[
                        Node(id="ch1_a1_p1", kind="paragraph", text="本文一。"),
                        Node(id="ch1_a1_p2", kind="paragraph", text="本文二。"),
                    ],
                ),
                Node(
                    id="ch1_a2",
                    kind="article",
                    title="定義",
                    children=[
                        Node(
                            id="ch1_a2_p1",
                            kind="paragraph",
                            text="本文三。",
                            children=[
                                Node(id="ch1_a2_p1_i1", kind="item", text="号一。"),
                                Node(id="ch1_a2_p1_i2", kind="item", text="号二。"),
                            ],
                        )
                    ],
                ),
            ],
        ),
        Node(
            id="ch2",
            kind="chapter",
            title="第二の章",
            children=[
                Node(
                    id="ch2_s1",
                    kind="section",
                    title="第一の節",
                    children=[
                        Node(
                            id="ch2_s1_a1",
                            kind="article",
                            title="通知",
                            children=[Node(id="ch2_s1_a1_p1", kind="paragraph", text="本文四。")],
                        )
                    ],
                )
            ],
        ),
    ]
    appendices = [
        Node(
            id="app1",
            kind="appendix",
            title="別表の一",
            children=[
                Node(
                    id="app1_s1",
                    kind="appendix_section",
                    title="区分",
                    children=[Node(id="app1_s1_p1", kind="paragraph", text="別表の本文。")],
                )
            ],
        )
    ]
    return body, appendices


IDS = (
    "ch1",
    "ch1_a1",
    "ch1_a1_p1",
    "ch1_a1_p2",
    "ch1_a2",
    "ch1_a2_p1",
    "ch1_a2_p1_i1",
    "ch2",
    "ch2_s1",
    "ch2_s1_a1",
    "ch2_s1_a1_p1",
    "app1",
    "app1_s1",
    "app1_s1_p1",
)


@pytest.mark.parametrize("scheme", SCHEMES)
def test_参照解決が置き換え前と一致する(legacy: dict, scheme: str) -> None:
    """`{ref:}` は方式の `continuous_articles` と `paragraph_ref_style` に効かれる。"""
    body, appendices = _tree()
    mismatches: list[str] = []
    for digit in DIGITS:
        index = DocumentIndex(_ctx(scheme, digit), body, appendices)
        for from_id in IDS:
            for to_id in IDS:
                for mode in ("relative", "short", "full"):
                    key = f"{scheme}|{digit}|{from_id}->{to_id}|{mode}"
                    got = resolve_ref(index, from_id, to_id, mode)  # type: ignore[arg-type]
                    if got != legacy["refs"][key]:
                        mismatches.append(f"{key}: got={got!r} want={legacy['refs'][key]!r}")
    assert not mismatches, f"{len(mismatches)} 件ずれた\n" + "\n".join(mismatches[:15])


@pytest.mark.parametrize("scheme", SCHEMES)
def test_citationが置き換え前と一致する(legacy: dict, scheme: str) -> None:
    body, appendices = _tree()
    for digit in DIGITS:
        index = DocumentIndex(_ctx(scheme, digit), body, appendices)
        want = legacy["labels"][f"citation|{scheme}|{digit}"]
        got = {node_id: index.citation(node_id) for node_id in IDS}
        assert got == want, f"{scheme}|{digit}"


# --- 2. 契約書の 2 方式 -------------------------------------------------------


def test_契約書の2方式が導入されている() -> None:
    assert set(available_schemes()) >= {"contract-standard", "contract-form"}


@pytest.mark.parametrize(
    ("kind", "n", "siblings", "want"),
    [
        ("chapter", 2, 3, "第２章"),
        ("section", 2, 3, "第２節"),
        ("article", 4, 9, "第４条"),
        ("paragraph", 1, 3, ""),  # 第1項は無番号
        ("paragraph", 2, 3, "２"),
        ("item", 1, 3, "（１）"),
        ("subitem", 1, 3, "ｱ"),
        ("subsubitem", 1, 3, "（ｱ）"),
    ],
)
def test_contract_standardのラベル(kind: str, n: int, siblings: int, want: str) -> None:
    ctx = NumberingContext(scheme="contract-standard", digit_style="fullwidth")
    assert label_for(ctx, kind, n, "x", siblings=siblings) == want  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "n", "want"),
    [
        ("chapter", 1, "1"),  # 様式型は「1 労働契約の期間」
        ("article", 2, "(2)"),  # その下が「(2)」
        ("paragraph", 3, "③"),  # さらに下が丸数字
    ],
)
def test_contract_formのラベル(kind: str, n: int, want: str) -> None:
    """様式型（条を持たない）。半角数字で組む文書が多いので halfwidth で確かめる。"""
    ctx = NumberingContext(scheme="contract-form", digit_style="halfwidth")
    assert label_for(ctx, kind, n, "x", siblings=3) == want  # type: ignore[arg-type]


def test_contract_standardは条を全編通しで振る() -> None:
    spec = load_scheme("contract-standard")
    assert spec.continuous_articles, "契約書の条は章をまたいで通し番号（docs/schema.md §7.1）"
    assert spec.ref.no_chapter_prefix, "通し番号なので {ref:} に章を冠さない"
    assert spec.paragraph_ref_style == "written", "第1項が無番号なので参照は「第N項」と書き下す"


def test_条見出しが上にある体裁でも位置づけに条番号を二重に入れない() -> None:
    """`article_heading: above` は条ラベルを第1項の本文へ走り込ませる（描画の都合）。

    実害：これを citation にも混ぜていたため、約款型の号が「第三条 第三条 (1)」になり、
    **外から読んだ予測では再現できない位置づけ**になっていた（2026-10-02 の V-D）。
    """
    from keiyaku.models import Node
    from keiyaku.numbering import DocumentIndex

    body = [
        Node(
            id="a1",
            kind="article",
            title="総則",
            children=[
                Node(
                    id="a1_p1",
                    kind="paragraph",
                    text="本文",
                    children=[Node(id="a1_p1_i1", kind="item", text="一つ目")],
                ),
                Node(id="a1_p2", kind="paragraph", text="本文"),
            ],
        )
    ]
    ctx = NumberingContext(scheme="contract-kanji", digit_style="halfwidth", article_heading="above")
    index = DocumentIndex(ctx, body)
    assert index.citation("a1") == "第一条"
    assert index.citation("a1_p1") == "第一条", "第1項は無番号なので条だけ"
    assert index.citation("a1_p1_i1") == "第一条 (1)", "条番号を二重にしない"
    assert index.citation("a1_p2") == "第一条 2"


def test_頭書の中の段落は番号を持たない() -> None:
    """頭書の項目の中身は**項ではなく説明の行**。本文の規則に落ちると 2 行目に「2」が付く。

    実害：賃貸借の頭書に置いた注記（※ 修繕の費用の負担は別表1による）が「2 ※ …」と採番された。
    """
    ctx = NumberingContext(scheme="contract-standard", digit_style="halfwidth")
    assert label_for(ctx, "paragraph", 1, "x", siblings=2, scope="head_matter") == ""
    assert label_for(ctx, "paragraph", 2, "x", siblings=2, scope="head_matter") == ""
    # 頭書の項目そのものは番号を持つ（「1 品名及び数量」）
    assert label_for(ctx, "item", 2, "x", siblings=3, scope="head_matter") == "2"
    # 本文では従来どおり（第1項は無番号・第2項から採番）
    assert label_for(ctx, "paragraph", 2, "x", siblings=2) == "2"


def test_別紙は呼び名ごとに採番する() -> None:
    ctx = NumberingContext(scheme="contract-standard", digit_style="halfwidth")
    assert appendix_label(ctx, 1) == "別紙1"
    assert appendix_label(ctx, 1, "別表") == "別表1"
    assert appendix_label(ctx, 2, "様式第") == "様式第2"


# --- 3. 宣言の検査 -----------------------------------------------------------


def test_未知のキーは弾く() -> None:
    from keiyaku.numbering_spec import NumberingSpecError

    with pytest.raises(NumberingSpecError, match="未知のキー"):
        parse_scheme({"scheme": "x", "levels": {"article": {"fmt": "第{n}条"}}})
    with pytest.raises(NumberingSpecError, match="未知のキー"):
        parse_scheme({"scheme": "x", "unknown_top": 1})


def test_未知のcounterは弾く() -> None:
    """`kanji` は 2026-09-27 に**使えるようになった**（約款型の条番号。CT23）ので、
    ここでは本当に無いカウンタを使う。"""
    from keiyaku.numbering_spec import NumberingSpecError

    with pytest.raises(NumberingSpecError, match="counter"):
        parse_scheme({"scheme": "x", "levels": {"article": {"format": "{n}", "counter": "iroha"}}})


def test_ファイル名とschemeの食い違いを弾く() -> None:
    from keiyaku.numbering_spec import NumberingSpecError

    with pytest.raises(NumberingSpecError, match="食い違う"):
        parse_scheme({"scheme": "other"}, name="contract-standard")


def test_導入済みの宣言はすべて読める() -> None:
    """`numbering/` に置いたものが壊れていないこと（`keiyaku doctypes` も同じ検査をする）。"""
    assert available_schemes(), "numbering/ に宣言が無い"
    for name in available_schemes(NUMBERING_DIR):
        spec = load_scheme(name, NUMBERING_DIR)
        assert spec.scheme == name
        assert spec.levels, f"{name} に levels が無い"


# --- 漢数字のカウンタ（約款型。CT23） -----------------------------------------


@pytest.mark.parametrize(
    ("n", "want"),
    [
        (1, "一"),
        (2, "二"),
        (9, "九"),
        (10, "十"),
        (11, "十一"),
        (19, "十九"),
        (20, "二十"),
        (23, "二十三"),
        (30, "三十"),
        (99, "九十九"),
        (100, "百"),
        (101, "百一"),
        (110, "百十"),
        (233, "二百三十三"),
        (999, "九百九十九"),
    ],
)
def test_漢数字は法令の流儀で書く(n: int, want: str) -> None:
    """「一十」ではなく「十」、「一百」ではなく「百」。"""
    from keiyaku.numbering_spec import to_kanji

    assert to_kanji(n) == want


def test_漢数字はdigit_styleに依らない() -> None:
    """漢数字に全角・半角の別は無い。`digit_style` を変えても同じ文字になる。"""
    from keiyaku.numbering_spec import render_counter

    assert render_counter("kanji", 23, "fullwidth") == render_counter("kanji", 23, "halfwidth")
