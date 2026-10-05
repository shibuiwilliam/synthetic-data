"""評価指標（CLAUDE.md §9・docs/evaluation.md）。

読み取り側の予測 JSON と `answer.json` を突き合わせる。**予測に内部 id は無い前提**なので、
突合はすべて**中身**で行う（テキスト・見出し文言・キャプション番号・QA の id のみ例外）。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Any


def normalize(text: str) -> str:
    """比較用の正規化。NFKC ＋ 空白除去（全角空白を含む）。"""
    return re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", text or ""))


# --- 文字誤り率 ---------------------------------------------------------------


def levenshtein(a: Sequence[Any], b: Sequence[Any]) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def cer(gold: str, pred: str) -> float:
    """文字誤り率。gold が空なら pred も空のとき 0、それ以外は 1。"""
    g, p = normalize(gold), normalize(pred)
    if not g:
        return 0.0 if not p else 1.0
    return levenshtein(g, p) / len(g)


# --- 集合の F1 ----------------------------------------------------------------


def set_f1(gold: list[Any], pred: list[Any]) -> dict[str, float]:
    """多重集合の F1（同じ値が複数あってもよい）。"""
    from collections import Counter

    g, p = Counter(gold), Counter(pred)
    tp = sum((g & p).values())
    precision = tp / sum(p.values()) if p else 0.0
    recall = tp / sum(g.values()) if g else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


# --- 表 -----------------------------------------------------------------------


def grid_to_bracket(grid: list[list[str]]) -> str:
    """TEDS 用に表を括弧表記の木にする（PubTabNet の定義に倣い、行→セルの 2 階層）。"""
    rows = []
    for row in grid:
        cells = "".join("{td{" + normalize(c) + "}}" for c in row)
        rows.append("{tr" + cells + "}")
    return "{table" + "".join(rows) + "}"


def teds(gold: list[list[str]], pred: list[list[str]]) -> float:
    """Tree-Edit-Distance based Similarity。1 に近いほど良い。"""
    from apted import APTED, Config
    from apted.helpers import Tree

    class _Config(Config):
        def rename(self, node1: Any, node2: Any) -> int:
            return int(node1.name != node2.name)

    gold_tree = Tree.from_text(grid_to_bracket(gold))
    pred_tree = Tree.from_text(grid_to_bracket(pred))
    distance = APTED(gold_tree, pred_tree, _Config()).compute_edit_distance()

    def size(node: Any) -> int:
        return 1 + sum(size(child) for child in node.children)

    denominator = max(size(gold_tree), size(pred_tree))
    return round(1 - distance / denominator, 4) if denominator else 1.0


# --- bbox ---------------------------------------------------------------------


def iou(a: Sequence[float], b: Sequence[float]) -> float:
    """2 つの矩形（x0, y0, x1, y1）の IoU。重なりが無ければ 0。"""
    if len(a) != 4 or len(b) != 4:
        return 0.0
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    if dx <= 0 or dy <= 0:
        return 0.0
    intersection = dx * dy
    area_a = max(a[2] - a[0], 0) * max(a[3] - a[1], 0)
    area_b = max(b[2] - b[0], 0) * max(b[3] - b[1], 0)
    union = area_a + area_b - intersection
    return round(intersection / union, 4) if union > 0 else 0.0


# --- 読み順 -------------------------------------------------------------------


def kendall_tau(gold_order: list[str], pred_order: list[str]) -> float:
    """共通する要素だけで Kendall の τ を出す。要素が 2 未満なら 1.0。"""
    rank = {key: i for i, key in enumerate(gold_order)}
    seq = [rank[k] for k in pred_order if k in rank]
    n = len(seq)
    if n < 2:
        return 1.0
    concordant = discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if seq[i] == seq[j]:
                continue
            if seq[i] < seq[j]:
                concordant += 1
            else:
                discordant += 1
    total = concordant + discordant
    return round((concordant - discordant) / total, 4) if total else 1.0


# --- 検索 ---------------------------------------------------------------------


def dcg(grades: list[int]) -> float:
    import math

    return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


def ndcg_at_k(ranked_grades: list[int], ideal_grades: list[int], k: int) -> float:
    actual = dcg(ranked_grades[:k])
    ideal = dcg(sorted(ideal_grades, reverse=True)[:k])
    return round(actual / ideal, 4) if ideal else 0.0


def recall_at_k(ranked_grades: list[int], n_relevant: int, k: int) -> float:
    if not n_relevant:
        return 0.0
    return round(sum(1 for g in ranked_grades[:k] if g > 0) / n_relevant, 4)


def mrr(ranked_grades: list[int]) -> float:
    for i, grade in enumerate(ranked_grades, start=1):
        if grade > 0:
            return round(1 / i, 4)
    return 0.0


def r_precision(ranked_grades: list[int], n_relevant: int) -> float:
    """上位 R 件（R = 適合数）の適合率。網羅を測る `enumeration` の主指標。

    打ち切り位置を適合数に合わせるので、`Recall@k` のように「k が足りなくて
    上限に届かない」ことが起きない（docs/search_query_plan.md W7）。
    """
    if not n_relevant:
        return 0.0
    return round(sum(1 for g in ranked_grades[:n_relevant] if g > 0) / n_relevant, 4)
