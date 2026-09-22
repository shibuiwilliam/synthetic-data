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
    from yakkan.eval import build_prediction, evaluate
    from yakkan.models import Answer

    directory = _first_dataset()
    assert directory is not None
    answer = Answer.model_validate_json((directory / "answer.json").read_text(encoding="utf-8"))
    items = json.loads((directory / "qa.json").read_text(encoding="utf-8"))["items"]
    score = evaluate(directory, build_prediction(answer, items))

    assert score["text"]["cer_macro"] == 0.0
    assert score["outline"]["f1"] == 1.0
    assert score["outline"]["kind_acc"] == 1.0
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
    from yakkan.eval import build_prediction, degrade, evaluate
    from yakkan.models import Answer

    directory = _first_dataset()
    assert directory is not None
    answer = Answer.model_validate_json((directory / "answer.json").read_text(encoding="utf-8"))
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
