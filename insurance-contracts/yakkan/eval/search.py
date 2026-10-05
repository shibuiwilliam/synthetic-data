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

from yakkan.eval.metrics import mrr, ndcg_at_k, r_precision, recall_at_k

#: 既定で報告する打ち切り位置。100 は `enumeration`（網羅を測る kind）のため
CUTOFFS = (1, 5, 10, 100)


def load_qrels(path: Path) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["query_id"]][row["passage_id"]] = int(row["grade"])
    return dict(out)


def evaluate_run(  # noqa: C901 - kind ごとの指標の出し分けが本質
    qrels: dict[str, dict[str, int]],
    runs: list[dict[str, Any]],
    *,
    cutoffs: tuple[int, ...] = CUTOFFS,
    queries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """順位つき結果を採点する。

    **`no_answer` のように gold が空のクエリも採点する**（何も返さないのが正解なので、
    飛ばしてしまうと「黙れるか」を測れない。docs/search_query_plan.md W9）。
    `hard_negatives` が宣言されているクエリでは `confusion@k`（上位 k 件に占める
    紛らわしい非適合の割合）も出す。
    """
    kind_of = {q["query_id"]: q.get("kind", "") for q in (queries or [])}
    negatives_of = {q["query_id"]: set(q.get("hard_negatives") or []) for q in (queries or [])}
    empty_gold = {q["query_id"] for q in (queries or []) if not q.get("n_relevant")}
    per_kind: dict[str, list[dict[str, float]]] = defaultdict(list)
    rows: list[dict[str, Any]] = []
    for run in runs:
        query_id = run.get("query_id")
        relevant = qrels.get(query_id) or {}
        if not relevant and query_id not in empty_gold:
            continue
        returned = list(run.get("passages", []))
        ranked = [int(relevant.get(pid, 0)) for pid in returned]
        ideal = list(relevant.values())
        row: dict[str, Any] = {"query_id": query_id, "kind": kind_of.get(query_id, "")}
        if not relevant:
            # gold が空：返さないのが正解。1 件でも返したら誤り
            row["false_positive_rate"] = 1.0 if returned else 0.0
            rows.append(row)
            per_kind[row["kind"]].append(row)
            continue
        for k in cutoffs:
            row[f"ndcg@{k}"] = ndcg_at_k(ranked, ideal, k)
            row[f"recall@{k}"] = recall_at_k(ranked, len(relevant), k)
            # 適合が k 件を超えるクエリは、上位 k 件を適合で埋めても 1 にならない。
            # **満点の並びでも recall@10 が 0.87 になり、欠陥に見える**ので、
            # 到達できる上限を併記する（docs/remaining_issues.md T2）。
            row[f"recall_ceiling@{k}"] = round(min(1.0, k / len(relevant)), 4)
        row["mrr"] = mrr(ranked)
        row["r_precision"] = r_precision(ranked, len(relevant))
        # **grade 2 だけを見た再現率。** grade 1 が字面で簡単に取れる kind
        # （`definition_masked` はクエリ文が grade 1 の引用）では、
        # 「答えそのもの」を引けたかが recall@k からは読めない
        n_exact = sum(1 for g in relevant.values() if g >= 2)
        for k in (5, 10):
            found = sum(1 for pid in returned[:k] if relevant.get(pid, 0) >= 2)
            row[f"exact_recall@{k}"] = round(found / n_exact, 4) if n_exact else 0.0
        # 1 位が grade 2 と同じ文書か。文書同定と文書内の順位付けは別の能力なので分けて報告する
        gold_docs = {pid.split("::", 1)[0] for pid, g in relevant.items() if g >= 2}
        row["doc@1"] = 1.0 if returned and returned[0].split("::", 1)[0] in gold_docs else 0.0
        for k in (5, 10):
            hit = any(pid.split("::", 1)[0] in gold_docs for pid in returned[:k])
            row[f"doc_recall@{k}"] = 1.0 if hit else 0.0
        hard = negatives_of.get(query_id) or set()
        if hard:
            for k in (5, 10):
                top = returned[:k]
                row[f"confusion@{k}"] = (
                    round(sum(1 for pid in top if pid in hard) / len(top), 4) if top else 0.0
                )
        rows.append(row)
        per_kind[row["kind"]].append(row)

    def mean(items: list[dict[str, float]], key: str) -> float:
        values = [float(i[key]) for i in items if key in i]
        return round(sum(values) / len(values), 4) if values else 0.0

    metrics = (
        [f"ndcg@{k}" for k in cutoffs]
        + [f"recall@{k}" for k in cutoffs]
        + [f"recall_ceiling@{k}" for k in cutoffs]
        + ["mrr", "r_precision", "doc@1", "doc_recall@5", "doc_recall@10"]
        + ["exact_recall@5", "exact_recall@10"]
        + ["confusion@5", "confusion@10", "false_positive_rate"]
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


def oracle_run(
    qrels: dict[str, dict[str, int]], queries: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """満点になる検索結果（適合度の高い順に並べたもの）。ハーネスの自己評価に使う。

    `queries` を渡すと、**gold が空のクエリ（`no_answer`）には空の結果**を入れる。
    何も返さないのが正解なので、これで `false_positive_rate` が 0.0 になる。
    """
    runs = [
        {
            "query_id": query_id,
            "passages": [pid for pid, _g in sorted(rel.items(), key=lambda kv: (-kv[1], kv[0]))],
        }
        for query_id, rel in sorted(qrels.items())
    ]
    scored = {run["query_id"] for run in runs}
    for query in queries or []:
        if query["query_id"] not in scored and not query.get("n_relevant"):
            runs.append({"query_id": query["query_id"], "passages": []})
    return sorted(runs, key=lambda r: str(r["query_id"]))
