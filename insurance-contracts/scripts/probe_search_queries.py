"""検索クエリの弁別力を測る（docs/search_query_design.md の根拠）。

`dataset/search/{passages,queries,qrels}.jsonl` を読み、クエリが
**対象の文書・パッセージを一意に決められるか**を 6 通りに測る。

1. 字面の曖昧さ：クエリ文字列がコーパスの何パッセージ・何文書に出現し、
   そのうち何件が qrels で grade 0（＝返すと誤答と採点される）か
2. gold の広がり：grade 2 が何文書にまたがるか
3. クエリの重複：同一 kind・同一文字列で gold が食い違うクエリ
4. qa の gold 誤配：gold が出題元の文書に 1 件も無いクエリ（element_id の衝突）
5. 打ち切り：`MAX_RELATED` で qrels から落ちた grade 1 の量
6. 飽和：素朴な文字 2-gram BM25 のスコア（nDCG / Recall / MRR / doc@1）

    uv run python scripts/probe_search_queries.py [--dataset dataset]

**外部依存なし**（標準ライブラリのみ）。BM25 は「約款の字面をそのまま引く」
だけの最低限の検索器で、これで満点近くが出る種別は弁別力が無い。
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
import statistics
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: 字面一致が何文書に散ったら「広く使われる語」とみなすか（docs/search_query_design.md AA-4）
WIDE_DF_DOCS = 10
#: 素朴な BM25 でこれを超える種別は「弁別力なし」と印を付ける
SATURATED_NDCG1 = 0.85

BM25_K1 = 1.2
BM25_B = 0.75
#: title は見出し一致が効くように 2 回数える（素朴な全文検索の慣行）
TITLE_WEIGHT = 2


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def bigrams(text: str) -> list[str]:
    s = normalize(text)
    return [s[i : i + 2] for i in range(len(s) - 1)] or ([s] if s else [])


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class Corpus:
    def __init__(self, search_dir: Path) -> None:
        self.passages = read_jsonl(search_dir / "passages.jsonl")
        self.queries = read_jsonl(search_dir / "queries.jsonl")
        self.by_id = {p["passage_id"]: p for p in self.passages}
        self.doc_ids = {p["doc_id"] for p in self.passages}
        self.qrels: dict[str, dict[str, int]] = collections.defaultdict(dict)
        for row in read_jsonl(search_dir / "qrels.jsonl"):
            self.qrels[row["query_id"]][row["passage_id"]] = row["grade"]
        self.text = {p["passage_id"]: normalize(p["text"]) for p in self.passages}

    def grade2_docs(self, query_id: str) -> set[str]:
        return {p.split("::", 1)[0] for p, g in self.qrels[query_id].items() if g == 2}

    def of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [q for q in self.queries if q["kind"] == kind]


# --- 1. 字面の曖昧さ・2. gold の広がり ---------------------------------------


def report_ambiguity(corpus: Corpus, kinds: tuple[str, ...]) -> None:
    print("## 1. 字面の曖昧さ（クエリ文字列がどこまで散るか）")
    for kind in kinds:
        rows = []
        for query in corpus.of_kind(kind):
            needle = normalize(query["query"])
            if not needle:
                continue
            hits = [pid for pid, text in corpus.text.items() if needle in text]
            labelled = corpus.qrels[query["query_id"]]
            rows.append(
                {
                    "query": query["query"],
                    "literal_passages": len(hits),
                    "literal_docs": len({corpus.by_id[pid]["doc_id"] for pid in hits}),
                    "relevant": len(labelled),
                    "grade2_docs": len(corpus.grade2_docs(query["query_id"])),
                    "literal_but_zero": len([pid for pid in hits if pid not in labelled]),
                }
            )
        if not rows:
            continue
        docs = [r["literal_docs"] for r in rows]
        zeros = [r["literal_but_zero"] for r in rows]
        g2docs = [r["grade2_docs"] for r in rows]
        wide = [r for r in rows if r["literal_docs"] >= WIDE_DF_DOCS]
        print(f"  [{kind}] n={len(rows)}（コーパス {len(corpus.doc_ids)} 文書）")
        print(
            f"    字面一致パッセージ 中央値={statistics.median(r['literal_passages'] for r in rows):.0f}"
            f" 平均={statistics.mean(r['literal_passages'] for r in rows):.0f}"
            f" 最大={max(r['literal_passages'] for r in rows)}"
        )
        print(
            f"    字面一致が何文書に散るか 中央値={statistics.median(docs):.0f}"
            f" 平均={statistics.mean(docs):.1f} 最大={max(docs)}"
        )
        print(
            f"    字面一致のうち grade 0（返すと誤答）中央値={statistics.median(zeros):.0f}"
            f" 平均={statistics.mean(zeros):.0f} 最大={max(zeros)}"
        )
        print(
            f"    grade 2 がまたぐ文書数 中央値={statistics.median(g2docs):.0f}"
            f" 平均={statistics.mean(g2docs):.1f} 最大={max(g2docs)}"
        )
        share = len(wide) / len(rows)
        print(f"    字面が {WIDE_DF_DOCS} 文書以上に散るクエリ: {len(wide)}/{len(rows)}（{share:.0%}）")
        print("    ワースト 8（字面一致順）: クエリ / 一致P / 一致文書 / 適合P / grade2文書 / 一致かつ0")
        for row in sorted(rows, key=lambda r: -r["literal_passages"])[:8]:
            print(
                f"      {row['query'][:22]:<24} {row['literal_passages']:>5} {row['literal_docs']:>4}"
                f" {row['relevant']:>4} {row['grade2_docs']:>4} {row['literal_but_zero']:>6}"
            )


# --- 3. クエリの重複 ----------------------------------------------------------


def report_duplicates(corpus: Corpus) -> None:
    print("\n## 2. 同一文字列のクエリ（同じ入力に別の正解）")
    # **入力はクエリ文だけでなく `filters` も含む**（`filtered` は同じ文言をメタデータで
    # 絞り込む kind なので、filters が違えば別の入力。生成側の V-S4 と同じ判定にする）
    groups: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    for query in corpus.queries:
        facet = "|".join(f"{k}={v}" for k, v in sorted((query.get("filters") or {}).items()))
        groups[(query["kind"], normalize(query["query"]), facet)].append(query["query_id"])
    duplicated = {k: v for k, v in groups.items() if len(v) > 1}
    affected = sum(len(v) for v in duplicated.values())
    conflicting = 0
    ceilings: list[float] = []
    for ids in groups.values():
        golds = [set(p for p, g in corpus.qrels[i].items() if g == 2) for i in ids]
        if len(ids) == 1:
            ceilings.append(1.0)
            continue
        if any(g != golds[0] for g in golds):
            conflicting += len(ids)
        union = set().union(*golds) or {""}
        # 同じ文字列には同じ並びしか返せない。先頭 1 件をどれにしても、
        # それを gold に含むクエリだけが nDCG@1 = 1 になる。
        best = max(sum(1 for g in golds if p in g) for p in union) / len(ids)
        ceilings.extend([best] * len(ids))
    total = len(corpus.queries)
    print(f"  重複グループ {len(duplicated)} 件 / 影響クエリ {affected} 件（{affected / total:.0%}）")
    print(f"  うち gold が食い違うもの {conflicting} 件（{conflicting / total:.0%}）")
    ceiling = statistics.mean(ceilings)
    print(f"  重複による平均 nDCG@1 の到達上限 = {ceiling:.3f}（完璧な検索器でも超えられない）")
    by_kind = collections.Counter(k[0] for k, v in duplicated.items() for _ in v)
    print(f"  kind 別の重複クエリ数: {dict(by_kind)}")


# --- 4. qa の gold 誤配 -------------------------------------------------------


def report_qa_misassignment(corpus: Corpus) -> None:
    print("\n## 3. qa の gold が出題元の文書を指しているか")
    misassigned = []
    total = 0
    for query in corpus.of_kind("qa"):
        # note の末尾の括弧が出題元の doc_id（"count の問い（auto-0001--...）"）
        matched = re.search(r"（([^（）]+)）\s*$", query.get("note", ""))
        if not matched:
            continue
        total += 1
        docs = corpus.grade2_docs(query["query_id"])
        if docs and matched.group(1) not in docs:
            misassigned.append((query["query_id"], matched.group(1), sorted(docs)))
    if total:
        share = len(misassigned) / total
        print(f"  gold が出題元の文書に 1 件も無いクエリ: {len(misassigned)}/{total}（{share:.0%}）")
        for row in misassigned[:4]:
            print(f"    {row[0]}: 出題元 {row[1]} → gold {row[2]}")
    index: dict[str, set[str]] = collections.defaultdict(set)
    for passage in corpus.passages:
        for element_id in passage["element_ids"]:
            index[element_id].add(passage["doc_id"])
    collided = {e: len(d) for e, d in index.items() if len(d) > 1}
    worst = max(collided.values(), default=0)
    print(f"  同名 element_id が複数文書に存在: {len(collided)} 種（最大 {worst} 文書）")
    print(f"    例: {sorted(collided.items(), key=lambda x: -x[1])[:5]}")


# --- 5. 打ち切り --------------------------------------------------------------


def report_truncation(corpus: Corpus) -> None:
    print("\n## 4. grade 1 の打ち切り（MAX_RELATED）")
    truncated = [q for q in corpus.queries if q.get("related_truncated")]
    kept = sum(q.get("n_related", 0) for q in corpus.queries)
    lost = sum(q.get("n_related_total", 0) - q.get("n_related", 0) for q in truncated)
    total = len(corpus.queries)
    print(f"  打ち切られたクエリ: {len(truncated)}/{total}（{len(truncated) / total:.1%}）")
    print(f"  qrels から落ちた grade 1: {lost} 件（残存 {kept} 件の {lost / kept:.0%}）")
    print(f"  種別: {dict(collections.Counter(q['kind'] for q in truncated))}")


# --- 6. 飽和（素朴な BM25） ---------------------------------------------------


class Bm25:
    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self.ids = [p["passage_id"] for p in passages]
        docs = [bigrams((p["title"] + " ") * TITLE_WEIGHT + p["text"]) for p in passages]
        self.lengths = [len(d) for d in docs]
        self.avgdl = sum(self.lengths) / len(docs)
        self.index: dict[str, list[tuple[int, int]]] = collections.defaultdict(list)
        for i, doc in enumerate(docs):
            for token, freq in collections.Counter(doc).items():
                self.index[token].append((i, freq))
        n = len(docs)
        self.idf = {
            token: math.log(1 + (n - len(postings) + 0.5) / (len(postings) + 0.5))
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
                norm = 1 - BM25_B + BM25_B * self.lengths[i] / self.avgdl
                scores[i] += weight * freq * (BM25_K1 + 1) / (freq + BM25_K1 * norm)
        ranked = sorted(scores.items(), key=lambda x: (-x[1], self.ids[x[0]]))[:k]
        return [self.ids[i] for i, _ in ranked]


def ndcg(ranked: list[str], rel: dict[str, int], k: int) -> float:
    gain = sum((2 ** rel.get(p, 0) - 1) / math.log2(i + 2) for i, p in enumerate(ranked[:k]))
    ideal = sorted(rel.values(), reverse=True)[:k]
    best = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return gain / best if best else 0.0


class TitleExact:
    """B1：クエリと `title` が正規化後に一致するパッセージだけを返す。"""

    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self.by_title: dict[str, list[str]] = collections.defaultdict(list)
        for p in passages:
            self.by_title[normalize(p["title"])].append(p["passage_id"])

    def search(self, query: str, k: int = 10) -> list[str]:
        return sorted(self.by_title.get(normalize(query), []))[:k]


class Tfidf:
    """B3：文字 unigram の TF-IDF コサイン。2-gram BM25 とは別系統の字面照合。"""

    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self.ids = [p["passage_id"] for p in passages]
        docs = [
            collections.Counter(normalize((p["title"] + " ") * TITLE_WEIGHT + p["text"])) for p in passages
        ]
        n = len(docs)
        df: collections.Counter[str] = collections.Counter()
        for doc in docs:
            df.update(doc.keys())
        self.idf = {t: math.log(n / (1 + c)) + 1 for t, c in df.items()}
        self.index: dict[str, list[tuple[int, float]]] = collections.defaultdict(list)
        for i, doc in enumerate(docs):
            norm = math.sqrt(sum((f * self.idf[t]) ** 2 for t, f in doc.items())) or 1.0
            for t, f in doc.items():
                self.index[t].append((i, f * self.idf[t] / norm))

    def search(self, query: str, k: int = 10) -> list[str]:
        scores: dict[int, float] = collections.defaultdict(float)
        for t, f in collections.Counter(normalize(query)).items():
            weight = f * self.idf.get(t, 0.0)
            for i, value in self.index.get(t, []):
                scores[i] += weight * value
        ranked = sorted(scores.items(), key=lambda x: (-x[1], self.ids[x[0]]))[:k]
        return [self.ids[i] for i, _ in ranked]


def _score(corpus: Corpus, engine: Any, kinds: tuple[str, ...]) -> dict[str, dict[str, float]]:
    """検索器 1 つを全クエリに通し、kind ごとの平均を返す。"""
    buckets: dict[str, dict[str, list[float]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for query in corpus.queries:
        ranked = engine.search(query["query"], 10)
        rel = corpus.qrels[query["query_id"]]
        bucket = buckets[query["kind"]]
        if not rel:
            # gold が空（`no_answer`）：返さないのが正解
            bucket["false_positive_rate"].append(1.0 if ranked else 0.0)
            continue
        bucket["nDCG@1"].append(ndcg(ranked, rel, 1))
        bucket["nDCG@10"].append(ndcg(ranked, rel, 10))
        n_exact = sum(1 for g in rel.values() if g >= 2) or 1
        bucket["exact_recall@10"].append(sum(1 for p in ranked[:10] if rel.get(p, 0) >= 2) / n_exact)
        bucket["mrr"].append(next((1 / (i + 1) for i, p in enumerate(ranked) if rel.get(p, 0) > 0), 0.0))
        docs = corpus.grade2_docs(query["query_id"])
        bucket["doc@1"].append(1.0 if ranked and ranked[0].split("::", 1)[0] in docs else 0.0)
    return {
        kind: {m: statistics.mean(v) for m, v in metrics.items()}
        for kind, metrics in buckets.items()
        if kind in kinds
    }


def report_spread(corpus: Corpus, kinds: tuple[str, ...]) -> None:
    """3 つの素朴な検索器のスコア差（スプレッド）。差が出ない kind は弁別力が無い。"""
    print("\n## 6. 素朴な検索器 3 種のスプレッド（nDCG@1）")
    engines = {
        "B1 title-exact": TitleExact(corpus.passages),
        "B2 2gram BM25": Bm25(corpus.passages),
        "B3 unigram TFIDF": Tfidf(corpus.passages),
    }
    scored = {name: _score(corpus, engine, kinds) for name, engine in engines.items()}
    print(f"  {'kind':<19}" + "".join(f"{n:>18}" for n in engines) + f"{'スプレッド':>12}")
    for kind in kinds:
        values = [scored[name].get(kind, {}).get("nDCG@1") for name in engines]
        if all(v is None for v in values):
            continue
        shown = [v if v is not None else 0.0 for v in values]
        spread = max(shown) - min(shown)
        flag = "差が出ない" if spread < 0.2 and max(shown) > 0.85 else ""
        print(f"  {kind:<19}" + "".join(f"{v:>18.3f}" for v in shown) + f"{spread:>12.3f}  {flag}")


def report_baseline(corpus: Corpus, kinds: tuple[str, ...]) -> None:
    print("\n## 5. 素朴な全文検索（文字 2-gram BM25）のスコア")
    engine = Bm25(corpus.passages)
    metrics: dict[str, dict[str, list[float]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for query in corpus.queries:
        ranked = engine.search(query["query"], 10)
        rel = corpus.qrels[query["query_id"]]
        bucket = metrics[query["kind"]]
        for k in (1, 5, 10):
            bucket[f"nDCG@{k}"].append(ndcg(ranked, rel, k))
            found = len([p for p in ranked[:k] if rel.get(p, 0) > 0])
            bucket[f"R@{k}"].append(found / min(k, len(rel)) if rel else 0.0)
        bucket["mrr"].append(next((1 / (i + 1) for i, p in enumerate(ranked) if rel.get(p, 0) > 0), 0.0))
        docs = corpus.grade2_docs(query["query_id"])
        bucket["doc@1"].append(1.0 if ranked and ranked[0].split("::", 1)[0] in docs else 0.0)
    columns = ("nDCG@1", "nDCG@5", "nDCG@10", "R@10", "mrr", "doc@1")
    print(f"  {'kind':<10}{'n':>6}  " + "  ".join(f"{c:>8}" for c in columns) + "   判定")
    for kind in kinds:
        bucket = metrics.get(kind)
        if not bucket:
            continue
        values = [statistics.mean(bucket[c]) for c in columns]
        flag = "弁別力なし（飽和）" if values[0] > SATURATED_NDCG1 else ""
        print(
            f"  {kind:<10}{len(bucket['mrr']):>6}  " + "  ".join(f"{v:>8.3f}" for v in values) + f"   {flag}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "dataset")
    parser.add_argument("--skip-baseline", action="store_true", help="BM25 の計測を飛ばす（数十秒かかる）")
    args = parser.parse_args()
    search_dir = args.dataset / "search"
    if not (search_dir / "queries.jsonl").exists():
        raise SystemExit(f"見つからない: {search_dir}/queries.jsonl（先に uv run yakkan export）")
    corpus = Corpus(search_dir)
    kinds = tuple(dict.fromkeys(q["kind"] for q in corpus.queries))
    print(
        f"# 検索クエリの弁別力 — パッセージ {len(corpus.passages)} / クエリ {len(corpus.queries)}"
        f" / 文書 {len(corpus.doc_ids)}\n"
    )
    report_ambiguity(corpus, tuple(k for k in kinds if k in ("term", "heading")))
    report_duplicates(corpus)
    report_qa_misassignment(corpus)
    report_truncation(corpus)
    if not args.skip_baseline:
        report_baseline(corpus, kinds)
        report_spread(corpus, kinds)


if __name__ == "__main__":
    main()
