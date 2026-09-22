"""検索結果の採点（docs/evaluation.md）。

入力は「クエリごとの順位つきパッセージ id」。全文検索・ベクトル検索・ハイブリッド・
ランク学習のどれでも、この形にすれば同じ物差しで比べられる。

    {"runs": [{"query_id": "q_head_0001", "passages": ["doc::ch1_a1", "doc::ch2_a3", ...]}]}
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from yakkan.eval.metrics import mrr, ndcg_at_k, recall_at_k

#: 既定で報告する打ち切り位置
CUTOFFS = (1, 5, 10)


def load_qrels(path: Path) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["query_id"]][row["passage_id"]] = int(row["grade"])
    return dict(out)


def evaluate_run(
    qrels: dict[str, dict[str, int]],
    runs: list[dict[str, Any]],
    *,
    cutoffs: tuple[int, ...] = CUTOFFS,
    queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """順位つき結果を採点する。qrels に無いクエリは無視する。"""
    kind_of = {q["query_id"]: q.get("kind", "") for q in (queries or [])}
    per_kind: dict[str, list[dict[str, float]]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    for run in runs:
        query_id = run.get("query_id")
        relevant = qrels.get(query_id)
        if not relevant:
            continue
        ranked = [int(relevant.get(pid, 0)) for pid in run.get("passages", [])]
        ideal = list(relevant.values())
        row: dict[str, Any] = {"query_id": query_id, "kind": kind_of.get(query_id, "")}
        for k in cutoffs:
            row[f"ndcg@{k}"] = ndcg_at_k(ranked, ideal, k)
            row[f"recall@{k}"] = recall_at_k(ranked, len(relevant), k)
            # 適合が k 件を超えるクエリは、上位 k 件を適合で埋めても 1 にならない。
            # **満点の並びでも recall@10 が 0.87 になり、欠陥に見える**ので、
            # 到達できる上限を併記する（docs/remaining_issues.md T2）。
            row[f"recall_ceiling@{k}"] = round(min(1.0, k / len(relevant)), 4)
        row["mrr"] = mrr(ranked)
        rows.append(row)
        per_kind[row["kind"]].append(row)

    def mean(items: list[dict[str, float]], key: str) -> float:
        values = [float(i[key]) for i in items if key in i]
        return round(sum(values) / len(values), 4) if values else 0.0

    metrics = (
        [f"ndcg@{k}" for k in cutoffs]
        + [f"recall@{k}" for k in cutoffs]
        + [f"recall_ceiling@{k}" for k in cutoffs]
        + ["mrr"]
    )
    return {
        "queries_scored": len(rows),
        "queries_in_qrels": len(qrels),
        "overall": {m: mean(rows, m) for m in metrics},
        "by_kind": {
            kind: {"queries": len(items)} | {m: mean(items, m) for m in metrics}
            for kind, items in sorted(per_kind.items())
        },
        "per_query": rows,
    }


def oracle_run(qrels: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    """満点になる検索結果（適合度の高い順に並べたもの）。ハーネスの自己評価に使う。"""
    return [
        {
            "query_id": query_id,
            "passages": [pid for pid, _g in sorted(rel.items(), key=lambda kv: (-kv[1], kv[0]))],
        }
        for query_id, rel in sorted(qrels.items())
    ]
