"""評価ハーネスの自己評価（docs/evaluation.md）。

**満点の予測で満点が出る**ことと、**崩した予測で点が下がる**ことを固定する。
指標そのものの単体テストもここに置く。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yakkan.eval.metrics import cer, kendall_tau, ndcg_at_k, recall_at_k, set_f1, teds
from yakkan.eval.search import evaluate_run, load_qrels, oracle_run

DATASET = Path("dataset")


def _first_dataset() -> Path | None:
    if not DATASET.is_dir():
        return None
    for directory in sorted(DATASET.iterdir()):
        if (directory / "answer.json").exists() and (directory / "qa.json").exists():
            return directory
    return None


# --- 指標 ---------------------------------------------------------------------


def test_CERは一致で0() -> None:
    assert cer("第１条（告知義務）", "第1条 (告知義務)") == 0.0, "NFKC と空白除去で正規化する"
    assert cer("あいうえお", "あいう") == pytest.approx(0.4)
    assert cer("", "") == 0.0
    assert cer("", "余計") == 1.0


def test_多重集合のF1() -> None:
    assert set_f1(["a", "b"], ["a", "b"])["f1"] == 1.0
    assert set_f1(["a", "a"], ["a"])["recall"] == 0.5
    assert set_f1([], [])["f1"] == 0.0


def test_TEDSは同じ表で1() -> None:
    grid = [["用語", "定義"], ["被保険者", "補償を受ける方"]]
    assert teds(grid, grid) == 1.0
    assert teds(grid, [["用語", "定義"]]) < 1.0


def test_Kendallのτ() -> None:
    assert kendall_tau(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert kendall_tau(["a", "b", "c"], ["c", "b", "a"]) == -1.0
    assert kendall_tau(["a"], ["a"]) == 1.0


def test_bboxのIoU() -> None:
    from yakkan.eval.metrics import iou

    assert iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert iou([0, 0, 10, 10], [20, 20, 30, 30]) == 0.0
    assert iou([0, 0, 10, 10], [0, 0, 5, 10]) == 0.5


def test_検索の指標() -> None:
    assert ndcg_at_k([2, 1], [2, 1], 2) == 1.0
    assert ndcg_at_k([0, 0], [2, 1], 2) == 0.0
    assert recall_at_k([2, 0, 1], 3, 10) == pytest.approx(0.6667, abs=1e-4)


# --- 自己評価（dataset が無い環境では飛ばす） ---------------------------------


@pytest.mark.skipif(_first_dataset() is None, reason="dataset/ が無い")
def test_満点の予測は満点になる() -> None:
    from yakkan.answer import load_answer
    from yakkan.eval import build_prediction, evaluate

    directory = _first_dataset()
    assert directory is not None
    answer = load_answer(directory)
    items = json.loads((directory / "qa.json").read_text(encoding="utf-8"))["items"]
    score = evaluate(directory, build_prediction(answer, items))

    assert score["text"]["cer_macro"] == 0.0
    assert score["outline"]["f1"] == 1.0
    assert score["outline"]["kind_acc"] == 1.0
    # 同じ (label, title) の見出しが複数あっても取り違えないこと（S7）。
    # 出現回数を鍵に混ぜる前は、満点の予測でも page_acc が 0.39 まで落ちていた。
    assert score["outline"]["page_acc"] == 1.0
    assert score["outline"]["citation_acc"] == 1.0
    assert score["citation"]["coverage"] == 1.0, "本文ノードが全部 reading_order に出ていること"
    assert score["citation"]["citation_acc"] == 1.0
    assert score["tables"]["teds_macro"] == 1.0
    assert score["tables"]["cell_f1"]["f1"] == 1.0
    assert score["figures"]["node_f1"]["f1"] == 1.0
    assert score["figures"]["edge_f1"]["f1"] == 1.0
    assert score["figures"]["path_f1"]["f1"] == 1.0
    assert score["enumerations"]["order_exact"] == 1.0
    assert score["layout"]["iou_mean"] == 1.0, "oracle は gold の bbox をそのまま出す"
    assert score["reading_order"]["tau_macro"] == 1.0
    assert score["qa"]["exact_match"] == 1.0


@pytest.mark.skipif(_first_dataset() is None, reason="dataset/ が無い")
def test_崩した予測は点が下がる() -> None:
    from yakkan.answer import load_answer
    from yakkan.eval import build_prediction, degrade, evaluate

    directory = _first_dataset()
    assert directory is not None
    answer = load_answer(directory)
    items = json.loads((directory / "qa.json").read_text(encoding="utf-8"))["items"]
    perfect = build_prediction(answer, items)
    score = evaluate(directory, degrade(perfect, seed=1, rate=0.3))

    assert score["text"]["cer_macro"] > 0.0
    assert score["outline"]["f1"] < 1.0
    assert score["citation"]["citation_acc"] == 0.0, "citation を消したので 0"
    assert score["tables"]["teds_macro"] < 1.0
    assert score["figures"]["edge_f1"]["f1"] == 0.0


@pytest.mark.skipif(not (DATASET / "search" / "qrels.jsonl").exists(), reason="検索評価セットが無い")
def test_満点の検索結果は満点になる() -> None:
    qrels = load_qrels(DATASET / "search" / "qrels.jsonl")
    result = evaluate_run(qrels, oracle_run(qrels))
    assert result["overall"]["ndcg@1"] == 1.0
    assert result["overall"]["ndcg@10"] == 1.0
    assert result["overall"]["mrr"] == 1.0


@pytest.mark.skipif(not (DATASET / "search" / "qrels.jsonl").exists(), reason="検索評価セットが無い")
def test_順序を崩すと検索の点が下がる() -> None:
    qrels = load_qrels(DATASET / "search" / "qrels.jsonl")
    runs = oracle_run(qrels)
    # 先頭に非適合のパッセージを挟む
    broken = [{"query_id": r["query_id"], "passages": ["___miss___", *r["passages"]]} for r in runs]
    result = evaluate_run(qrels, broken)
    assert result["overall"]["ndcg@1"] == 0.0
    assert result["overall"]["mrr"] < 1.0


# --- 検索評価セットの性質（docs/remaining_issues.md R1） ----------------------


def test_citationの前方一致() -> None:
    from yakkan.search_set import _under

    assert _under("第2章 第1条 (1)", "第2章 第1条")
    assert _under("第2章 第1条", "第2章 第1条")
    assert not _under("第2章 第10条", "第2章 第1条"), "前方一致は語の境界で切る"
    assert not _under("第2章 第1条", "第2章 第1条 (1)")
    assert not _under("", "第2章")


@pytest.mark.skipif(not (DATASET / "search" / "queries.jsonl").exists(), reason="検索評価セットが無い")
def test_どのクエリ種別にも部分適合がある() -> None:
    """grade 2 しか無いと nDCG が二値になり、順位の良し悪しを測れない（R1）。"""
    import json as _json
    from collections import Counter, defaultdict

    kinds = {
        _json.loads(line)["query_id"]: _json.loads(line)["kind"]
        for line in (DATASET / "search" / "queries.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    grades: defaultdict[str, Counter[int]] = defaultdict(Counter)
    per_query: Counter[str] = Counter()
    for line in (DATASET / "search" / "qrels.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = _json.loads(line)
        grades[kinds[row["query_id"]]][int(row["grade"])] += 1
        per_query[row["query_id"]] += 1

    for kind in ("term", "heading", "scoped", "qa"):
        assert grades[kind][2] > 0, f"{kind} に grade 2 が無い"
        assert grades[kind][1] > 0, f"{kind} に grade 1 が無い（部分適合が作れていない）"
    single = sum(1 for v in per_query.values() if v == 1)
    assert single / len(per_query) < 0.5, "適合が 1 件だけのクエリが半数を超えている"


@pytest.mark.skipif(not (DATASET / "search" / "qrels.jsonl").exists(), reason="検索評価セットが無い")
def test_部分適合を落とすとnDCGが下がる() -> None:
    """grade 1 が効いていること（二値ではないこと）を確かめる。"""
    qrels = load_qrels(DATASET / "search" / "qrels.jsonl")
    graded = {q: rel for q, rel in qrels.items() if any(g == 1 for g in rel.values())}
    assert graded, "部分適合を持つクエリが無い"
    runs = [
        {"query_id": q, "passages": [p for p, g in sorted(rel.items(), key=lambda kv: (-kv[1], kv[0]))]}
        for q, rel in graded.items()
    ]
    # grade 1 を末尾から落とした結果は、満点より nDCG@10 が下がる
    dropped = [
        {"query_id": r["query_id"], "passages": [p for p in r["passages"] if graded[r["query_id"]][p] == 2]}
        for r in runs
    ]
    best = evaluate_run(graded, runs)["overall"]["ndcg@10"]
    worse = evaluate_run(graded, dropped)["overall"]["ndcg@10"]
    assert best == 1.0
    assert worse < best, "grade 1 を落としても点が変わらないなら、部分適合が効いていない"


# --- grade 1 の打ち切り（docs/remaining_issues.md S5） ------------------------


def test_grade1の間引きは文書をまたいで均等に取る() -> None:
    from yakkan.search_set import _spread

    related = {f"doc{d}::e{i}": 1 for d in range(4) for i in range(10)}
    kept = _spread(related, 8)
    assert len(kept) == 8
    per_doc = {}
    for passage_id in kept:
        per_doc[passage_id.split("::")[0]] = per_doc.get(passage_id.split("::")[0], 0) + 1
    assert per_doc == {"doc0": 2, "doc1": 2, "doc2": 2, "doc3": 2}, per_doc
    assert _spread(related, 100) == dict(sorted(related.items())), "上限以下なら素通し"


@pytest.mark.skipif(not (DATASET / "search" / "queries.jsonl").exists(), reason="検索評価セットが無い")
def test_打ち切ったクエリには印がある() -> None:
    rows = [
        json.loads(line)
        for line in (DATASET / "search" / "queries.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        assert row["n_related"] <= row["n_related_total"]
        assert row["related_truncated"] == (row["n_related"] < row["n_related_total"])
    assert any(row["related_truncated"] for row in rows), "打ち切りが 1 件も無いなら印を検査できていない"


# --- 現実の読み取り誤りへの反応（docs/remaining_issues.md S6） ----------------

#: 崩しの強さ。`misread` は入れ子に崩すので、この順に指標が単調に悪化するはず
MISREAD_RATES = (0.0, 0.05, 0.1, 0.2, 0.4, 0.7)

#: 高いほど良い指標。**F1 ではなく recall を見る。**
#: 要素を落とすと誤りも一緒に落ちて precision が上がり、F1 は跳ねることがある。
MISREAD_LOWER = (
    ("outline", "recall"),
    ("citation", "citation_acc"),
    ("tables", "teds_macro"),
    ("tables", "cell_f1", "recall"),
    ("figures", "node_f1", "recall"),
    ("figures", "edge_f1", "recall"),
    ("figures", "path_f1", "recall"),
    ("reading_order", "tau_macro"),
    ("enumerations", "order_exact"),
    ("qa", "exact_match"),
)


def _dig(score: dict, path: tuple[str, ...]) -> float:
    value: object = score
    for key in path:
        value = value[key]  # type: ignore[index]
    return float(value)  # type: ignore[arg-type]


@pytest.mark.skipif(_first_dataset() is None, reason="dataset/ が無い")
@pytest.mark.parametrize("seed", [0, 3])
def test_崩すほど指標が単調に悪くなる(seed: int) -> None:
    """自己評価が循環しないようにするための検査（R6・S6）。

    満点の予測を「現実の読み取り誤り」で少しずつ崩し、**強さに対して指標が
    単調に悪化する**ことを確かめる。指標が誤りを吸収してしまう（正規化しすぎる、
    突合が緩い）と単調性が崩れるので、満点が出ることだけを見るより強い検査になる。
    """
    from yakkan.answer import load_answer
    from yakkan.eval import build_prediction, evaluate, misread

    directory = _first_dataset()
    assert directory is not None
    answer = load_answer(directory)
    items = json.loads((directory / "qa.json").read_text(encoding="utf-8"))["items"]
    perfect = build_prediction(answer, items)
    series = [evaluate(directory, misread(perfect, seed=seed, rate=r)) for r in MISREAD_RATES]

    cer = [s["text"]["cer_macro"] for s in series]
    assert cer[0] == 0.0, "崩さなければ満点のまま"
    assert all(b >= a - 1e-9 for a, b in zip(cer, cer[1:], strict=False)), cer
    assert cer[-1] > cer[1], "強く崩しても CER が動かないなら、崩し方が指標に届いていない"

    for path in MISREAD_LOWER:
        values = [_dig(s, path) for s in series]
        assert values[0] == 1.0, f"{path} は崩さなければ満点"
        assert all(b <= a + 1e-9 for a, b in zip(values, values[1:], strict=False)), (path, values)
        assert values[-1] < values[0], f"{path} が強い崩しに反応していない"


# --- 外から使えるか（docs/remaining_issues.md T2・T7〜T9） --------------------


def test_列挙は番号を付けても付けなくても同じ点になる() -> None:
    """紙面どおり「（１）取締役会」と出しても、番号を落として出しても正解（T8）。"""
    from yakkan.eval.harness import strip_enum_label
    from yakkan.eval.metrics import normalize

    for raw in ("（１）取締役会", "(1)取締役会", "①取締役会", "❶取締役会", "１．取締役会", "取締役会"):
        assert normalize(strip_enum_label(raw)) == "取締役会", raw
    # NFKC は ① を「1」にするので、**正規化の前に**落とさないと
    # 「10日以内に…」の 1 と見分けがつかなくなる
    assert normalize(strip_enum_label("10日以内に通知します")) == "10日以内に通知します"
    assert strip_enum_label("（かっこ書き）を含む本文") == "（かっこ書き）を含む本文"


@pytest.mark.skipif(_first_dataset() is None, reason="dataset/ が無い")
def test_outlineに見えない見出しが混ざらない() -> None:
    """ラベルも文言も無い節点は紙面に出ないので outline に入れない（T7）。"""
    from yakkan.answer import load_answer

    directory = _first_dataset()
    assert directory is not None
    answer = load_answer(directory)
    blank = [o for o in answer.outline if not (o.label or "").strip() and not (o.title or "").strip()]
    assert not blank, f"{len(blank)} 件の見えない見出しが outline にある"


@pytest.mark.skipif(_first_dataset() is None, reason="dataset/ が無い")
def test_包含での対応づけは全文一致以上に当たる() -> None:
    """段落の切り方がずれても位置づけを測れるようにした指標（T9）。"""
    from yakkan.answer import load_answer
    from yakkan.eval import build_prediction, evaluate, misread

    directory = _first_dataset()
    assert directory is not None
    answer = load_answer(directory)
    items = json.loads((directory / "qa.json").read_text(encoding="utf-8"))["items"]
    perfect = build_prediction(answer, items)
    score = evaluate(directory, perfect)
    assert score["citation"]["coverage_contains"] == 1.0
    assert score["citation"]["citation_acc_contains"] == 1.0
    # 崩した予測でも、包含のほうが全文一致より甘くなる（下回らない）
    broken = evaluate(directory, misread(perfect, seed=1, rate=0.4))
    assert broken["citation"]["coverage_contains"] >= broken["citation"]["coverage"]


@pytest.mark.skipif(not (DATASET / "search" / "qrels.jsonl").exists(), reason="検索評価セットが無い")
def test_Recallの上限を併記する() -> None:
    """適合が k 件を超えるクエリでは満点でも Recall@k が 1 にならない（T2）。"""
    qrels = load_qrels(DATASET / "search" / "qrels.jsonl")
    result = evaluate_run(qrels, oracle_run(qrels))
    assert result["overall"]["recall@10"] == result["overall"]["recall_ceiling@10"], (
        "満点の並びなら Recall は到達できる上限と一致するはず"
    )
    assert result["overall"]["recall_ceiling@10"] < 1.0, "上限が 1 なら、この指標を出す意味がない"
    assert result["overall"]["recall_ceiling@1"] < result["overall"]["recall_ceiling@10"]


# --- 表と見出しの数え方（docs/remaining_issues.md X3） ------------------------


@pytest.mark.skipif(_first_dataset() is None, reason="dataset/ が無い")
def test_列挙として組んだ表は表として数えない() -> None:
    """同じ中身を tables と enumerations の両方に出させない（X3）。"""
    from yakkan.answer import load_answer
    from yakkan.eval.harness import _gold_tables

    directory = _first_dataset()
    assert directory is not None
    answer = load_answer(directory)
    as_enum = {e.id for e in answer.source.derived.enumerations if e.source == "table"}
    scored = _gold_tables(answer)
    # 採点対象の表は、どれも列挙として数えられていない
    from yakkan.lint.walk import iter_blocks
    from yakkan.models import Table

    all_tables = [b.id for b, _o, _a in iter_blocks(answer.source) if isinstance(b, Table)]
    assert len(scored) == len(all_tables) - len(as_enum & set(all_tables))


def test_キャプションは正規化して突き合わせる() -> None:
    """全角の文書は gold が「表１」、読み取り側は「表1」と出すのが自然（X3）。"""
    from yakkan.eval.harness import score_tables
    from yakkan.models import Answer

    class _Fake:
        """`score_tables` が触るところだけを持つ最小の偽物。"""

    answer = Answer.model_construct()  # type: ignore[call-arg]
    gold = [{"caption_label": "表１", "grid": [["あ", "い"]], "triples": []}]
    pred = {"tables": [{"caption_label": "表1", "grid": [["あ", "い"]], "cells": []}]}

    import yakkan.eval.harness as harness

    original = harness._gold_tables
    harness._gold_tables = lambda _a: gold  # type: ignore[assignment]
    try:
        result = score_tables(answer, pred)
    finally:
        harness._gold_tables = original  # type: ignore[assignment]
    assert result["teds_macro"] == 1.0
