"""素朴な検索器（ベースライン）。**評価セットが簡単すぎないかを測るために同梱する。**

`yakkan eval --oracle`（満点の予測）はクエリの良し悪しを検出しない——満点の並びを
与えれば必ず満点になる。**字面を照合するだけの検索器で満点近くが出る kind は、
順位の良し悪しを測る分解能が無い**（実測：改修前の `term` で nDCG@1 0.920）。
3 系統を走らせ、スコアの差（スプレッド）が出るかを見る（docs/search_query_plan.md W16・§5.2）。

外部依存は無い（標準ライブラリのみ）。形態素解析も同義語辞書も使わない。
"""

from __future__ import annotations

import collections
import math
import re
import statistics
import unicodedata
from typing import Any, Protocol

from yakkan.eval.metrics import ndcg_at_k

#: `title` は見出し一致が効くように 2 回数える（素朴な全文検索の慣行）
TITLE_WEIGHT = 2
BM25_K1 = 1.2
BM25_B = 0.75
#: この値を超える nDCG@1 が出る kind は「弁別力なし（飽和）」と印を付けて配る
SATURATED_NDCG1 = 0.85


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def bigrams(text: str) -> list[str]:
    s = normalize(text)
    return [s[i : i + 2] for i in range(len(s) - 1)] or ([s] if s else [])


class Retriever(Protocol):
    def search(self, query: str, k: int = 10) -> list[str]: ...


def _indexed(passage: dict[str, Any]) -> str:
    return (passage.get("title", "") + " ") * TITLE_WEIGHT + passage.get("text", "")


class TitleExact:
    """B1：クエリと `title` が正規化後に一致するパッセージだけを返す。"""

    name = "B1 title一致"

    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self.by_title: dict[str, list[str]] = collections.defaultdict(list)
        for passage in passages:
            self.by_title[normalize(passage.get("title", ""))].append(passage["passage_id"])

    def search(self, query: str, k: int = 10) -> list[str]:
        return sorted(self.by_title.get(normalize(query), []))[:k]


class Bm25:
    """B2：文字 2-gram の BM25。日本語を形態素解析せずに引く定番の素朴な実装。"""

    name = "B2 2gram BM25"

    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self.ids = [p["passage_id"] for p in passages]
        docs = [bigrams(_indexed(p)) for p in passages]
        self.lengths = [len(d) for d in docs]
        self.avgdl = (sum(self.lengths) / len(docs)) if docs else 1.0
        self.index: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
        for i, doc in enumerate(docs):
            for token, freq in collections.Counter(doc).items():
                self.index[token].append((i, freq))
        total = len(docs) or 1
        self.idf = {
            token: math.log(1 + (total - len(postings) + 0.5) / (len(postings) + 0.5))
            for token, postings in self.index.items()
        }

    def search(self, query: str, k: int = 10) -> list[str]:
        scores: dict[int, float] = collections.defaultdict(float)
        for token in set(bigrams(query)):
            postings = self.index.get(token)
            if not postings:
                continue
            weight = self.idf[token]
            for i, freq in postings:
                length = 1 - BM25_B + BM25_B * self.lengths[i] / self.avgdl
                scores[i] += weight * freq * (BM25_K1 + 1) / (freq + BM25_K1 * length)
        ranked = sorted(scores.items(), key=lambda x: (-x[1], self.ids[x[0]]))[:k]
        return [self.ids[i] for i, _ in ranked]


class Tfidf:
    """B3：文字 unigram の TF-IDF コサイン。2-gram BM25 とは別系統の字面照合。"""

    name = "B3 unigram TFIDF"

    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self.ids = [p["passage_id"] for p in passages]
        docs = [collections.Counter(normalize(_indexed(p))) for p in passages]
        total = len(docs) or 1
        df: collections.Counter[str] = collections.Counter()
        for doc in docs:
            df.update(doc.keys())
        self.idf = {t: math.log(total / (1 + c)) + 1 for t, c in df.items()}
        self.index: dict[str, list[tuple[int, float]]] = collections.defaultdict(list)
        for i, doc in enumerate(docs):
            length = math.sqrt(sum((f * self.idf[t]) ** 2 for t, f in doc.items())) or 1.0
            for t, f in doc.items():
                self.index[t].append((i, f * self.idf[t] / length))

    def search(self, query: str, k: int = 10) -> list[str]:
        scores: dict[int, float] = collections.defaultdict(float)
        for t, f in collections.Counter(normalize(query)).items():
            weight = f * self.idf.get(t, 0.0)
            if not weight:
                continue
            for i, value in self.index.get(t, []):
                scores[i] += weight * value
        ranked = sorted(scores.items(), key=lambda x: (-x[1], self.ids[x[0]]))[:k]
        return [self.ids[i] for i, _ in ranked]


def retrievers(passages: list[dict[str, Any]]) -> list[Retriever]:
    return [TitleExact(passages), Bm25(passages), Tfidf(passages)]


def score(
    passages: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    qrels: dict[str, dict[str, int]],
    engine: Retriever,
    *,
    k: int = 10,
) -> dict[str, dict[str, float]]:
    """検索器 1 つを全クエリに通し、kind ごとの平均を返す。"""
    buckets: dict[str, dict[str, list[float]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for query in queries:
        ranked = engine.search(query["query"], k)
        relevant = qrels.get(query["query_id"]) or {}
        bucket = buckets[query["kind"]]
        if not relevant:
            # gold が空（`no_answer`）：返さないのが正解
            bucket["false_positive_rate"].append(1.0 if ranked else 0.0)
            continue
        grades = [int(relevant.get(pid, 0)) for pid in ranked]
        bucket["ndcg@1"].append(ndcg_at_k(grades, list(relevant.values()), 1))
        bucket["ndcg@10"].append(ndcg_at_k(grades, list(relevant.values()), 10))
        n_exact = sum(1 for g in relevant.values() if g >= 2) or 1
        bucket["exact_recall@10"].append(sum(1 for pid in ranked[:k] if relevant.get(pid, 0) >= 2) / n_exact)
        bucket["mrr"].append(next((1 / (i + 1) for i, g in enumerate(grades) if g > 0), 0.0))
        docs = {pid.split("::", 1)[0] for pid, g in relevant.items() if g >= 2}
        bucket["doc@1"].append(1.0 if ranked and ranked[0].split("::", 1)[0] in docs else 0.0)
    return {
        kind: {m: round(statistics.mean(v), 4) for m, v in metrics.items()}
        for kind, metrics in buckets.items()
    }


def table(
    passages: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    qrels: dict[str, dict[str, int]],
) -> str:
    """kind ごとのベースライン表（Markdown）。`dataset/README.md` に埋め込む。

    **統計値は固定文字列で焼き込まない**（コミット 42f58b3 の教訓）。
    """
    engines = retrievers(passages)
    scored = {engine.name: score(passages, queries, qrels, engine) for engine in engines}  # type: ignore[attr-defined]
    counts = collections.Counter(q["kind"] for q in queries)
    names = list(scored)
    lines = [
        "| kind | クエリ数 | " + " | ".join(f"{n} nDCG@1" for n in names) + " | スプレッド | 判定 |",
        "|---|---:|" + "---:|" * len(names) + "---:|---|",
    ]
    for kind in sorted(counts):
        values = [scored[n].get(kind, {}).get("ndcg@1", 0.0) for n in names]
        fpr = [scored[n].get(kind, {}).get("false_positive_rate") for n in names]
        if any(f is not None for f in fpr):
            shown = " | ".join(f"FPR {f:.3f}" if f is not None else "—" for f in fpr)
            lines.append(f"| `{kind}` | {counts[kind]:,} | {shown} | — | 偽陽性を測る kind |")
            continue
        spread = max(values) - min(values)
        verdict = "**弁別力なし（飽和）**" if max(values) > SATURATED_NDCG1 and spread < 0.2 else ""
        lines.append(
            f"| `{kind}` | {counts[kind]:,} | "
            + " | ".join(f"{v:.3f}" for v in values)
            + f" | {spread:.3f} | {verdict} |"
        )
    return "\n".join(lines)
