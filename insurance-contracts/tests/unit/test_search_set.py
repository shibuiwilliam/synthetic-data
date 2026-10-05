"""検索評価セットの生成（`yakkan.search_set`）。

**クエリが解を決定できるか**を固定する。`yakkan eval --oracle`（満点の予測）は
クエリの良し悪しを検出しない——満点の並びを与えれば必ず満点になる。
健全性は生成側で機械的に確かめる（docs/search_query_plan.md §3）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from yakkan.export_models import Passage, Qrel, Query
from yakkan.search_set import (
    MAX_SURFACE_OVERLAP,
    WIDE_DF_DOCS,
    _element_index,
    _heading_name,
    _resolve_evidence,
    _scene_of,
    _surface_overlap,
    query_id,
    validate_search_set,
)

DATASET = Path("dataset")
SEARCH = DATASET / "search"


def _passage(doc_id: str, element_id: str, **kwargs: Any) -> Passage:
    base: dict[str, Any] = {
        "passage_id": f"{doc_id}::{element_id}",
        "doc_id": doc_id,
        "content_id": doc_id.split("--")[0],
        "genre": "auto",
        "product_name": f"{doc_id} 保険",
        "issuer": f"{doc_id} 損害保険株式会社",
        "kind": "article",
        "title": "第1条（告知義務）",
        "citation": "第1章 第1条",
        "text": "本文",
        "element_ids": [element_id],
        "pages": [1],
    }
    base.update(kwargs)
    return Passage(**base)


# --- T-2 見出し名から番号ラベルを落とす（W2） ---------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("第3条（告知義務）", "告知義務"),
        ("①　お引受けの判断", "お引受けの判断"),
        ("① お引受けの判断", "お引受けの判断"),
        ("（2）保険金のお支払い", "保険金のお支払い"),
        ("用語の定義", "用語の定義"),
        ("①　AB", None),  # ラベルを落とすと 3 字未満
        ("第1章　総則", None),
    ],
)
def test_見出し名は番号ラベルを含まない(title: str, expected: str | None) -> None:
    assert _heading_name(title) == expected


# --- T-1 qa の evidence は文書内で解決する（W1） -------------------------------


def test_同名のelement_idは文書ごとに別のパッセージへ解決される() -> None:
    """`ch2_a1` は 80 文書にある。コーパス全体で 1 本の索引を張ると gold が誤配する。"""
    passages = [_passage("docA--s", "ch2_a1"), _passage("docB--s", "ch2_a1")]
    index = _element_index(passages)
    assert _resolve_evidence("ch2_a1", index["docA--s"]) == "docA--s::ch2_a1"
    assert _resolve_evidence("ch2_a1", index["docB--s"]) == "docB--s::ch2_a1"


def test_表のセルはその表のパッセージに寄る() -> None:
    passages = [_passage("docA--s", "tbl_x", kind="table", element_ids=["tbl_x"])]
    index = _element_index(passages)
    assert _resolve_evidence("tbl_x__r1c2", index["docA--s"]) == "docA--s::tbl_x"


# --- T-14 場面適用の問いから場面だけを採る（W14） ------------------------------


def test_場面適用の問いは末尾の問いかけだけを落とす() -> None:
    question = (
        "人身傷害の補償で、両手の指の機能をすべて失う後遺障害が残った場合、"
        "後遺障害による損害の額は保険金額の何パーセントとして算定されますか。"
    )
    assert _scene_of(question) == "人身傷害の補償で、両手の指の機能をすべて失う後遺障害が残った場合"


def test_問いかけしか無ければ場面は採れない() -> None:
    assert _scene_of("保険金はいくらですか。") is None


# --- 字面の重なり（W12 の V-S5） -----------------------------------------------


def test_字面の重なりは同文で1になる() -> None:
    assert _surface_overlap("被保険者の範囲", "被保険者の範囲") == 1.0
    assert _surface_overlap("被保険者の範囲", "まったく別の文言です") < MAX_SURFACE_OVERLAP


# --- T-7 query_id の安定性（W11） ---------------------------------------------


def test_query_idは生成キーだけで決まる() -> None:
    """content が増えても既存クエリの id が変わらないこと（通し番号では全部ずれる）。"""
    first = query_id("term", "被保険者")
    assert first == query_id("term", "被保険者")
    assert first.startswith("q_term_")
    assert first != query_id("heading", "被保険者")
    assert first != query_id("term", "保険契約者")


def test_query_idは空白の違いを無視する() -> None:
    assert query_id("heading", "告知 義務") == query_id("heading", "告知義務")


# --- T-5 自己検査（W5） --------------------------------------------------------


def _query(kind: str, text: str, **kwargs: Any) -> Query:
    base: dict[str, Any] = {
        "query_id": query_id(kind, text),
        "kind": kind,
        "query": text,
        "n_relevant": 1,
        "n_exact": 1,
        "n_related": 0,
        "n_related_total": 0,
    }
    base.update(kwargs)
    return Query(**base)


def test_自己検査_V_S1_qaのgoldは出題元の文書を指す() -> None:
    passages = [_passage("docA--s", "ch1_a1"), _passage("docB--s", "ch1_a1")]
    query = _query("qa", "第1条の見出しは何ですか。", note="heading の問い（docA--s）")
    qrels = [Qrel(query_id=query.query_id, passage_id="docB--s::ch1_a1", grade=2)]
    problems = validate_search_set(passages, [query], qrels)
    assert any(p.startswith("V-S1") for p in problems)


def test_自己検査_V_S2_素のクエリは1文書にしかgoldを持たない() -> None:
    passages = [_passage("docA--s", "ch1_a1"), _passage("docB--s", "ch1_a1")]
    query = _query("heading", "告知義務", n_relevant=2, n_exact=2)
    qrels = [
        Qrel(query_id=query.query_id, passage_id="docA--s::ch1_a1", grade=2),
        Qrel(query_id=query.query_id, passage_id="docB--s::ch1_a1", grade=2),
    ]
    assert any(p.startswith("V-S2") for p in validate_search_set(passages, [query], qrels))


def test_自己検査_V_S3_enumerationにgrade1は無い() -> None:
    passages = [_passage("docA--s", "ch1_a1")]
    query = _query("enumeration", "すべて挙げてください。", n_related=1, n_related_total=1)
    qrels = [Qrel(query_id=query.query_id, passage_id="docA--s::ch1_a1", grade=2)]
    assert any(p.startswith("V-S3") for p in validate_search_set(passages, [query], qrels))


def test_自己検査_V_S4_同じ入力に別のgoldは許さない() -> None:
    passages = [_passage("docA--s", "ch1_a1"), _passage("docA--s", "ch2_a1")]
    a = _query("heading", "告知義務")
    b = Query(**{**a.model_dump(), "query_id": "q_heading_other"})
    qrels = [
        Qrel(query_id=a.query_id, passage_id="docA--s::ch1_a1", grade=2),
        Qrel(query_id="q_heading_other", passage_id="docA--s::ch2_a1", grade=2),
    ]
    assert any(p.startswith("V-S4") for p in validate_search_set(passages, [a, b], qrels))


def test_自己検査_V_S4_filtersが違えば別の入力() -> None:
    """`filtered` は同じ文言をメタデータで絞り込む kind なので、これは正常。"""
    passages = [_passage("docA--s", "ch1_a1"), _passage("docB--s", "ch2_a1")]
    a = _query("filtered", "告知義務", filters={"issuer": "docA--s 損害保険株式会社"})
    b = _query("filtered", "告知義務", filters={"issuer": "docB--s 損害保険株式会社"})
    b = Query(**{**b.model_dump(), "query_id": "q_filtered_b"})
    qrels = [
        Qrel(query_id=a.query_id, passage_id="docA--s::ch1_a1", grade=2),
        Qrel(query_id="q_filtered_b", passage_id="docB--s::ch2_a1", grade=2),
    ]
    assert not [p for p in validate_search_set(passages, [a, b], qrels) if p.startswith("V-S4")]


def test_自己検査_V_S5_definition_maskedはgoldと字面が重なりすぎない() -> None:
    passages = [_passage("docA--s", "t__r1", kind="definition", title="被保険者の範囲")]
    query = _query("definition_masked", "被保険者の範囲")
    qrels = [Qrel(query_id=query.query_id, passage_id="docA--s::t__r1", grade=2)]
    assert any(p.startswith("V-S5") for p in validate_search_set(passages, [query], qrels))


def test_自己検査_V_S6_クエリ文は番号ラベルで始まらない() -> None:
    passages = [_passage("docA--s", "ch1_a1")]
    query = _query("heading", "①　お引受けの判断")
    qrels = [Qrel(query_id=query.query_id, passage_id="docA--s::ch1_a1", grade=2)]
    assert any(p.startswith("V-S6") for p in validate_search_set(passages, [query], qrels))


def test_自己検査_V_S7_filtersは1文書を一意に決める() -> None:
    shared = {"issuer": "同じ損害保険株式会社", "product_name": "定款"}
    passages = [
        _passage("docA--s", "ch1_a1", **shared),
        _passage("docB--s", "ch1_a1", **shared),
    ]
    query = _query("filtered", "告知義務", filters=shared)
    qrels = [Qrel(query_id=query.query_id, passage_id="docA--s::ch1_a1", grade=2)]
    assert any(p.startswith("V-S7") for p in validate_search_set(passages, [query], qrels))


def test_自己検査_V_S8_definitionパッセージは紙面上の位置を持つ() -> None:
    passages = [_passage("docA--s", "t__r1", kind="definition", title="運転者", pages=[])]
    assert any(p.startswith("V-S8") for p in validate_search_set(passages, [], []))


def test_自己検査_V_S9_grade1のterm_idはその文書でその語を指す() -> None:
    passages = [
        _passage("docA--s", "t__r1", kind="definition", title="対象動物"),
        _passage("docA--s", "ch1_a1", terms_used=["pet"]),
    ]
    query = _query("term", "いえのおまもり", n_relevant=2, n_related=1, n_related_total=1)
    qrels = [
        Qrel(query_id=query.query_id, passage_id="docA--s::t__r1", grade=2),
        Qrel(query_id=query.query_id, passage_id="docA--s::ch1_a1", grade=1),
    ]
    # docA では `pet` は「対象動物」なので、「いえのおまもり」の grade 1 にはならない
    problems = validate_search_set(passages, [query], qrels, terms_by_doc={"docA--s": {"pet": "対象動物"}})
    assert any(p.startswith("V-S9") for p in problems)


def test_自己検査_正しいセットでは何も出ない() -> None:
    passages = [
        _passage("docA--s", "t__r1", kind="definition", title="運転者"),
        _passage("docA--s", "ch1_a1", terms_used=["driver"]),
    ]
    query = _query("term", "運転者", n_relevant=2, n_related=1, n_related_total=1)
    qrels = [
        Qrel(query_id=query.query_id, passage_id="docA--s::t__r1", grade=2),
        Qrel(query_id=query.query_id, passage_id="docA--s::ch1_a1", grade=1),
    ]
    assert not validate_search_set(passages, [query], qrels, terms_by_doc={"docA--s": {"driver": "運転者"}})


# --- T-6 閾値の定数が probe と一致する ----------------------------------------


def test_振り分けの閾値はprobeと同じ値である() -> None:
    """生成と計測で閾値が食い違うと、probe の数字が実物を表さなくなる。"""
    import importlib.util

    path = Path("scripts/probe_search_queries.py")
    spec = importlib.util.spec_from_file_location("probe_search_queries", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.WIDE_DF_DOCS == WIDE_DF_DOCS


# --- データセットに対する検査（生成物があるときだけ） --------------------------


def _rows(name: str) -> list[dict[str, Any]]:
    path = SEARCH / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


needs_dataset = pytest.mark.skipif(not (SEARCH / "queries.jsonl").exists(), reason="検索評価セットが無い")


@needs_dataset
def test_生成済みの評価セットは自己検査を通る() -> None:
    passages = [Passage(**row) for row in _rows("passages.jsonl")]
    queries = [Query(**row) for row in _rows("queries.jsonl")]
    qrels = [Qrel(**row) for row in _rows("qrels.jsonl")]
    assert not validate_search_set(passages, queries, qrels)


@needs_dataset
def test_definitionパッセージは全件ページを持つ() -> None:
    rows = [r for r in _rows("passages.jsonl") if r["kind"] == "definition"]
    assert rows, "definition パッセージが無い"
    assert all(r["pages"] for r in rows), "紙面に存在しない definition パッセージがある"


@needs_dataset
def test_素のクエリは1文書にしかgoldを持たない() -> None:
    queries = {r["query_id"]: r for r in _rows("queries.jsonl")}
    docs: dict[str, set[str]] = {}
    for row in _rows("qrels.jsonl"):
        if row["grade"] != 2:
            continue
        kind = queries[row["query_id"]]["kind"]
        if kind in ("term", "heading"):
            docs.setdefault(row["query_id"], set()).add(row["passage_id"].split("::", 1)[0])
    assert docs
    spread = {q: d for q, d in docs.items() if len(d) > 1}
    assert not spread, f"素のクエリが複数文書に跨る: {list(spread)[:3]}"


@needs_dataset
def test_広く使われる語は素のクエリにしない() -> None:
    """`df_literal >= WIDE_DF_DOCS` の語は `enumeration` に回っていること。"""
    passages = _rows("passages.jsonl")
    queries = [r for r in _rows("queries.jsonl") if r["kind"] in ("term", "heading")]
    assert queries
    from yakkan.search_set import normalize

    texts = [(p["doc_id"], normalize(p["text"])) for p in passages]
    for row in queries[:40]:  # 全件は重いので先頭だけ（生成側は V-S2 で全件検査している）
        needle = normalize(row["query"])
        docs = {doc_id for doc_id, text in texts if needle in text}
        assert len(docs) < WIDE_DF_DOCS, f"{row['query']} が {len(docs)} 文書に散っている"


# --- T-11 決定論（W19） -------------------------------------------------------


@needs_dataset
def test_同じ入力から同じ評価セットが出る() -> None:
    """`build_search_set` を 2 回呼んで同じ並びになること（`seed` の受け渡しの検査）。

    `yakkan export` 全体のバイト一致は重いのでここでは測らない（手順は
    `docs/search_query_plan.md` W19。実測では 2 回の export が一致している）。
    """
    from yakkan.search_set import build_search_set

    passages = [Passage(**row) for row in _rows("passages.jsonl")][:600]
    first = build_search_set(passages, {})
    second = build_search_set(passages, {})
    assert [q.model_dump() for q in first[0]] == [q.model_dump() for q in second[0]]
    assert [r.model_dump() for r in first[1]] == [r.model_dump() for r in second[1]]


@needs_dataset
def test_no_answerは乱数を使うが再現する() -> None:
    """`random.Random(seed)` を明示的に受け渡しているので毎回同じクエリになる。"""
    from yakkan.search_set import build_search_set

    passages = [Passage(**row) for row in _rows("passages.jsonl")][:600]
    runs = [
        [q.query_id for q in build_search_set(passages, {})[0] if q.kind == "no_answer"] for _ in range(2)
    ]
    assert runs[0] == runs[1]


# --- T-16 / T-17 ジャンルの偏り（docs/search_query_plan.md 段 5） ---------------


@needs_dataset
def test_定義表を持たないジャンルはteikanだけ() -> None:
    """`life` の用語集が抜けていた（`definition` が 17 件しか無かった）件の回帰防止。

    `teikan`（定款）に用語集が無いのは**正しい**——実物にも無く、`defined_terms` も 0 語。
    """
    rows = [r for r in _rows("passages.jsonl") if r["kind"] == "definition"]
    genres = {r["genre"] for r in _rows("passages.jsonl")}
    with_definitions = {r["genre"] for r in rows}
    assert genres - with_definitions == {"teikan"}, "teikan 以外に用語集を持たないジャンルがある"


@needs_dataset
def test_definitionパッセージがジャンルに偏っていない() -> None:
    import collections

    counts = collections.Counter(r["genre"] for r in _rows("passages.jsonl") if r["kind"] == "definition")
    assert counts, "definition パッセージが無い"
    low = {g: n for g, n in counts.items() if n < 50}
    assert not low, f"definition パッセージが極端に少ないジャンル: {low}"
