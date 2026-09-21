"""`answer.json` の組み立てと QA の自動生成・検証（P5）。

`tests/golden/sample_min/` を描画して使う。描画が要るので module スコープで 1 回だけ回す。
macOS では `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が要る（`make check` 経由なら自動）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yakkan.answer import BODY_REGIONS, build_answer
from yakkan.build import build
from yakkan.compose import load_draft
from yakkan.models import QA, QASet
from yakkan.qa.auto import generate, pool_sizes
from yakkan.qa.validate import CONTAINMENT_TYPES, normalize, validate
from yakkan.styles import load_style

SAMPLE = Path(__file__).parents[1] / "golden" / "sample_min"
STYLE_ID = "nl-a4-2col-mincho"


@pytest.fixture(scope="module")
def answer(tmp_path_factory):
    from yakkan.render.weasy import render_source

    source = build(load_draft(SAMPLE))
    out = tmp_path_factory.mktemp("qa")
    result = render_source(source, load_style(STYLE_ID), out, render_png=False)
    return build_answer(source, result.layout)


# --- answer.json -------------------------------------------------------------


def test_ページ別テキストは本文の行だけでできている(answer):
    """ヘッダ／フッタの行は `text` に入らず、`text_with_furniture` にだけ入る。

    「ヘッダの文字列が text に出てこない」という書き方はできない。
    章名は目次にも本文にも出るので、文字列一致では区別できないため。
    """
    for page, layout_page in zip(answer.pages, answer.layout.pages, strict=True):
        body = "".join(ln.text for ln in layout_page.text_lines if ln.region in BODY_REGIONS)
        furniture = "".join(ln.text for ln in layout_page.text_lines if ln.region not in BODY_REGIONS)
        assert len(page.text) <= len(body), "本文以外の行が混ざっている"
        assert len(page.text_with_furniture) >= len(body) + len(furniture)
        if layout_page.header and layout_page.header.text:
            assert page.text_with_furniture.startswith(layout_page.header.text)
        if layout_page.footer and layout_page.footer.text:
            assert page.text_with_furniture.endswith(layout_page.footer.text)


def test_繰り返し表頭は一度だけ数える():
    """`repeated: true` の fragment に載る行を `text` から除く。

    再掲は**同じページの中でも起きる**（2 段組で表が段をまたぐと右段の頭に表頭が出る）ので、
    ページ単位ではなく bbox で判定している。合成した Layout で挙動だけを確かめる。
    """
    from yakkan.models import ElementFragment, ElementLayout, Layout, PageLayout, Renderer, TextLine

    layout = Layout(
        doc_id="t--s",
        content_id="t",
        style_id="s",
        renderer=Renderer(version="x", fonts=[]),
        page_size_pt=(595.0, 842.0),
        page_count=1,
        pages=[
            PageLayout(
                number=1,
                columns=2,
                text_lines=[
                    TextLine(bbox=[10, 10, 90, 20], text="等級", element_id="tbl__r0c0", region="table"),
                    TextLine(bbox=[10, 30, 90, 40], text="第1級", element_id="tbl__r1c0", region="table"),
                    # 右段に再掲された表頭
                    TextLine(bbox=[310, 10, 390, 20], text="等級", element_id="tbl__r0c0", region="table"),
                ],
            )
        ],
        elements={
            "tbl__r0c0": ElementLayout(
                kind="cell",
                fragments=[
                    ElementFragment(page=1, bbox=[10, 10, 90, 20]),
                    ElementFragment(page=1, bbox=[310, 10, 390, 20], repeated=True),
                ],
            ),
            "tbl__r1c0": ElementLayout(
                kind="cell", fragments=[ElementFragment(page=1, bbox=[10, 30, 90, 40])]
            ),
        },
    )
    from yakkan.answer import _page_texts

    pages = _page_texts(layout)
    assert pages[0].text == "等級第1級", "再掲された表頭が二重に入っている"
    assert pages[0].text_with_furniture.count("等級") == 2, "実際の紙面には 2 回出る"


def test_outlineはページ番号を持ち文書順に並ぶ(answer):
    assert answer.outline
    assert all(entry.page >= 1 for entry in answer.outline)
    body_pages = [e.page for e in answer.outline if e.depth == 0]
    assert body_pages == sorted(body_pages), "章の開始ページが単調増加でない"


def test_charsはtextの長さ(answer):
    assert all(page.chars == len(page.text) for page in answer.pages)


# --- 自動生成 ----------------------------------------------------------------


def test_30問生成できて検証を通る(answer):
    qa_set = generate(answer, count=30, seed=0)
    assert len(qa_set.items) == 30
    findings = validate(qa_set, answer)
    assert [str(f) for f in findings if f.severity == "error"] == []


def test_同じseedなら同じ結果(answer):
    a = generate(answer, count=30, seed=0)
    b = generate(answer, count=30, seed=0)
    assert [(i.type, i.question, i.answer) for i in a.items] == [
        (i.type, i.question, i.answer) for i in b.items
    ]


def test_種別が偏らない(answer):
    qa_set = generate(answer, count=30, seed=0)
    counts: dict[str, int] = {}
    for item in qa_set.items:
        counts[item.type] = counts.get(item.type, 0) + 1
    pools = pool_sizes(answer)
    available = {k for k, v in pools.items() if v > 0}
    assert set(counts) == available, "候補がある種別が採用されていない"
    # ラウンドロビンなので、採用数の差は 1 問に収まる。
    # それ以上少ない種別は **候補を使い切っている**はず（30 問に届かせるために他が埋める）。
    top = max(counts.values())
    for key, picked in counts.items():
        assert picked >= top - 1 or picked == pools[key], (
            f"{key} は {picked} 問（最多 {top}）しか採られていないのに候補が {pools[key]} 件残っている"
        )


def test_evidenceは描画済みの要素だけ(answer):
    qa_set = generate(answer, count=30, seed=0)
    for item in qa_set.items:
        for element_id in item.evidence:
            assert element_id in answer.layout.elements, f"{item.id}: {element_id} が未描画"


def test_figure_factは答えが片寄らない(answer):
    """図を読まずに全問正解できないこと（答えが「はい」だけだと成立してしまう）。"""
    pools = pool_sizes(answer)
    if not pools.get("figure_fact"):
        pytest.skip("この fixture に図が無い")
    from yakkan.qa.auto import _figure_fact

    answers = {str(item.answer) for item in _figure_fact(answer)}
    assert answers == {"はい", "いいえ"}


# --- 検証（L14）--------------------------------------------------------------


def _qa(**kwargs) -> QA:
    base = dict(
        id="qa_test_001",
        type="extract",
        question="問い",
        answer="答え",
        answer_type="string",
        evidence=[],
        page_hint=[],
        source="authored",
    )
    base.update(kwargs)
    return QA(**base)


def test_型が合わないとerror(answer):
    item = _qa(answer=1.0, answer_type="string", evidence=["ch1_a1"])
    findings = validate(QASet(doc_id="x", items=[item]), answer)
    assert any("answer_type=string" in f.message for f in findings)


def test_countはnumberでなければerror(answer):
    item = _qa(type="count", answer="3", answer_type="string", evidence=["ch1_a1"])
    findings = validate(QASet(doc_id="x", items=[item]), answer)
    assert any("answer_type=number" in f.message for f in findings)


def test_evidenceが空だとerror(answer):
    findings = validate(QASet(doc_id="x", items=[_qa(evidence=[])]), answer)
    assert any("evidence が空" in f.message for f in findings)


def test_存在しないevidenceはerror(answer):
    findings = validate(QASet(doc_id="x", items=[_qa(evidence=["no_such_id"])]), answer)
    assert any("source に無い" in f.message for f in findings)


def test_extract系はanswerがevidenceに含まれないとerror(answer):
    node_id = next(iter(answer.source.derived.plain_text))
    item = _qa(type="extract", answer="この文書に存在しない文字列です", evidence=[node_id])
    findings = validate(QASet(doc_id="x", items=[item]), answer)
    assert any("含まれない" in f.message for f in findings)


def test_extract系は正規化して比較する(answer):
    """全角半角や空白のゆれで落とさない。"""
    element_id, entry = next(
        (k, v) for k, v in answer.source.derived.plain_text.items() if len(v.without_label) > 10
    )
    # 元のテキストに半角空白を混ぜても通ること
    noisy = entry.without_label[:10] + " "
    item = _qa(type="definition", answer=noisy, evidence=[element_id])
    findings = [f for f in validate(QASet(doc_id="x", items=[item]), answer) if "含まれない" in f.message]
    assert findings == []


def test_ページ範囲外のpage_hintはerror(answer):
    item = _qa(evidence=["ch1_a1"], answer="", page_hint=[999])
    findings = validate(QASet(doc_id="x", items=[item]), answer)
    assert any("ページ範囲外" in f.message for f in findings)


def test_問いの重複はwarn(answer):
    node_id = next(iter(answer.source.derived.labels))
    a = _qa(id="q1", type="locate", answer=1.0, answer_type="number", evidence=[node_id])
    b = _qa(id="q2", type="locate", answer=1.0, answer_type="number", evidence=[node_id])
    findings = validate(QASet(doc_id="x", items=[a, b]), answer)
    assert any(f.severity == "warn" and "重複" in f.message for f in findings)


def test_包含検査の対象種別(answer):
    assert {"extract", "table_lookup", "definition"} == CONTAINMENT_TYPES


def test_normalizeは全角半角と空白を吸収():
    assert normalize("１００％ 以上") == normalize("100% 以上") == "100%以上"
