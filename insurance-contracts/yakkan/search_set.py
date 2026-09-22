"""検索エンジンの評価セットを作る（docs/eval_dataset_plan.md P8）。

全文検索・ベクトル検索・ハイブリッド・ランク学習のいずれも、必要なのは
**(1) 登録する単位（パッセージ）** と **(2) クエリ** と **(3) 適合判定（qrels）** の 3 つ。
QA は「1 つの答え」を採点するもので、「このクエリにどのパッセージが適合するか」という
多対多の判定ではないので、別に作る。

パッセージの単位：
- **条（article）が 1 パッセージ**。長い条は項ごとに割る（`MAX_CHARS`）。
- **表は 1 表 1 パッセージ**（キャプション＋行ごとの「見出し：値」＋表注）。
- **図は 1 図 1 パッセージ**（キャプション＋ alt ＋ facts）。
- **定義語は 1 語 1 パッセージ**（項目検索の主役）。
- 前付け・奥付など、条に属さない本文も拾う。

適合度（grade）は 3 段階：**2 = 答えがそこにある / 1 = 関連する（同じ条の別の項など） / 0 = 非適合**。
qrels には grade 1 以上だけを書く（書かれていないものは 0）。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from yakkan.models import Answer, Figure, Table

#: 1 パッセージの目安の長さ。これを超える条は項ごとに割る
MAX_CHARS = 600


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


# --- パッセージ ---------------------------------------------------------------


def _iter_blocks(answer: Answer) -> Iterable[tuple[Any, str]]:
    from yakkan.lint.walk import iter_blocks

    for block, owner_id, _article in iter_blocks(answer.source):
        yield block, owner_id


def _pages_of(answer: Answer, element_ids: list[str]) -> list[int]:
    pages: set[int] = set()
    for element_id in element_ids:
        element = answer.layout.elements.get(element_id)
        if element:
            pages.update(f.page for f in element.fragments)
    return sorted(pages)


def _passage(
    answer: Answer,
    passage_id: str,
    kind: str,
    title: str,
    text: str,
    element_ids: list[str],
    citation: str,
) -> dict[str, Any]:
    return {
        "passage_id": f"{answer.doc_id}::{passage_id}",
        "doc_id": answer.doc_id,
        "content_id": answer.source.content_id,
        "genre": answer.source.genre,
        "product_name": answer.source.meta.product_name,
        "issuer": answer.source.meta.issuer.name,
        "kind": kind,
        "title": title,
        "citation": citation,
        "text": text,
        "element_ids": element_ids,
        "pages": _pages_of(answer, element_ids),
    }


def _text_of(answer: Answer, element_id: str, *, with_label: bool = True) -> str:
    entry = answer.source.derived.plain_text.get(element_id)
    if entry is None:
        return ""
    return entry.with_label if with_label else entry.without_label


def _table_text(answer: Answer, table: Table) -> str:
    """表を検索できる平文にする。行ごとに「行見出し：セル」を並べる。"""
    derived = answer.source.derived.tables.get(table.id)
    lines: list[str] = []
    if table.caption:
        prefix = f"{derived.caption_label}　" if derived and derived.caption_label else ""
        lines.append(f"{prefix}{table.caption}")
    for row in table.grid:
        cells = [c for c in row if hasattr(c, "id")]
        values = [_text_of(answer, c.id, with_label=False) for c in cells]
        values = [v for v in values if v]
        if values:
            lines.append("　".join(values))
    for i, _note in enumerate(table.notes):
        lines.append(_text_of(answer, f"{table.id}__note{i}", with_label=False))
    return "\n".join(x for x in lines if x)


def _figure_text(answer: Answer, figure: Figure) -> str:
    derived = answer.source.derived.figures.get(figure.id)
    labels = derived.resolved_labels if derived else {}

    def resolve(value: str) -> str:
        return labels.get(value, value)

    lines: list[str] = []
    if figure.caption:
        prefix = f"{derived.caption_label}　" if derived and derived.caption_label else ""
        lines.append(f"{prefix}{resolve(figure.caption)}")
    lines.append(resolve(figure.alt))
    lines.extend(resolve(f) for f in figure.facts)
    if derived:
        lines.extend("　→　".join(path) for path in derived.paths[:8])
    return "\n".join(x for x in lines if x)


def build_passages(answer: Answer) -> list[dict[str, Any]]:  # noqa: C901 - 単位ごとの分岐が本質
    """1 文書ぶんのパッセージ。**検索エンジンに登録する単位**。"""
    derived = answer.source.derived
    out: list[dict[str, Any]] = []
    covered: set[str] = set()

    # 条（長い条は項ごとに割る）
    def walk(nodes: list) -> None:
        for node in nodes:
            if node.kind == "article":
                info = derived.labels.get(node.id)
                citation = info.citation if info else ""
                title = info.heading_text if info else (node.title or "")
                parts = [(c.id, _text_of(answer, c.id)) for c in node.children]
                parts = [(i, t) for i, t in parts if t]
                total = sum(len(t) for _i, t in parts)
                if total <= MAX_CHARS or len(parts) <= 1:
                    ids = [node.id, *[i for i, _t in parts]]
                    out.append(
                        _passage(
                            answer,
                            node.id,
                            "article",
                            title,
                            "\n".join([title, *[t for _i, t in parts]]),
                            ids,
                            citation,
                        )
                    )
                    covered.update(ids)
                else:
                    for child_id, text in parts:
                        child = derived.labels.get(child_id)
                        out.append(
                            _passage(
                                answer,
                                child_id,
                                "paragraph",
                                title,
                                f"{title}\n{text}",
                                [child_id],
                                child.citation if child else citation,
                            )
                        )
                        covered.add(child_id)
                    covered.add(node.id)
            walk(node.children or [])

    walk(answer.source.body)
    walk(answer.source.appendices)

    # 表・図
    for block, owner_id in _iter_blocks(answer):
        if isinstance(block, Table):
            info = derived.labels.get(owner_id)
            out.append(
                _passage(
                    answer,
                    block.id,
                    "table",
                    block.caption or (info.heading_text if info else ""),
                    _table_text(answer, block),
                    [block.id],
                    info.citation if info else "",
                )
            )
        elif isinstance(block, Figure):
            info = derived.labels.get(owner_id)
            out.append(
                _passage(
                    answer,
                    block.id,
                    "figure",
                    block.caption or (info.heading_text if info else ""),
                    _figure_text(answer, block),
                    [block.id],
                    info.citation if info else "",
                )
            )

    # 定義語
    for term in answer.source.defined_terms:
        entry = derived.plain_text.get(f"term_{term.id}")
        definition = entry.without_label if entry else term.definition
        out.append(
            _passage(
                answer,
                f"term::{term.id}",
                "definition",
                term.term,
                f"{term.term}\n{definition}",
                [],
                "",
            )
        )

    # 条に属さない本文（前付け・奥付・囲み）
    for element_id, plain in derived.plain_text.items():
        if element_id in covered or not plain.without_label.strip():
            continue
        element = answer.layout.elements.get(element_id)
        if element is None or element.kind not in ("paragraph", "list_item", "footnote"):
            continue
        if element_id.startswith(("tbl_", "fig_")):
            continue
        info = derived.labels.get(element_id)
        out.append(
            _passage(
                answer,
                element_id,
                "other",
                "",
                plain.with_label,
                [element_id],
                info.citation if info else "",
            )
        )
    return out


# --- クエリと qrels -----------------------------------------------------------

#: 適合度。2 = 答えがそこにある / 1 = 関連する
GRADE_EXACT = 2
GRADE_RELATED = 1


def _passage_of_element(passages: list[dict[str, Any]]) -> dict[str, str]:
    """要素 id → パッセージ id。表のセル・図のノードは容れ物のパッセージに寄せる。"""
    out: dict[str, str] = {}
    for passage in passages:
        for element_id in passage["element_ids"]:
            out.setdefault(element_id, passage["passage_id"])
    # 表のセル（`<table>__r1c2`）と表注は、その表のパッセージに寄せる
    for passage in passages:
        if passage["kind"] in ("table", "figure"):
            base = passage["element_ids"][0] if passage["element_ids"] else ""
            if base:
                out.setdefault(base, passage["passage_id"])
    return out


def _resolve_evidence(evidence: str, index: dict[str, str]) -> str | None:
    if evidence in index:
        return index[evidence]
    # 表のセル・表注・脚注は接頭辞で寄せる
    for sep in ("__",):
        if sep in evidence:
            base = evidence.split(sep)[0]
            if base in index:
                return index[base]
    return None


def build_search_set(
    passages: list[dict[str, Any]], qa_by_doc: dict[str, list[dict[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """コーパス全体のクエリと qrels を作る。

    3 系統：
    - `term`：定義語そのもの。正解はその語の定義パッセージ（**全文書ぶん**）。
    - `heading`：条の見出し文言。**同じ見出しは複数の文書にあるので、弁別力の検査になる**。
    - `qa`：既存 QA の問い。正解は evidence を含むパッセージ。
    - `scoped`：「商品名＋見出し」。正解はその文書のパッセージだけ（絞り込みの検査）。
    """
    by_id = {p["passage_id"]: p for p in passages}
    element_index = _passage_of_element(passages)
    queries: list[dict[str, Any]] = []
    qrels: list[dict[str, Any]] = []

    def add(query_id: str, kind: str, text: str, hits: dict[str, int], note: str = "") -> None:
        hits = {pid: g for pid, g in hits.items() if pid in by_id and g > 0}
        if not hits:
            return
        queries.append(
            {
                "query_id": query_id,
                "kind": kind,
                "query": text,
                "note": note,
                "n_relevant": len(hits),
            }
        )
        for passage_id, grade in sorted(hits.items()):
            qrels.append({"query_id": query_id, "passage_id": passage_id, "grade": grade})

    # --- term ---------------------------------------------------------------
    definitions: dict[str, list[dict[str, Any]]] = {}
    for passage in passages:
        if passage["kind"] == "definition" and passage["title"]:
            definitions.setdefault(passage["title"], []).append(passage)
    for i, (term, hits) in enumerate(sorted(definitions.items()), start=1):
        add(
            f"q_term_{i:04d}",
            "term",
            term,
            {p["passage_id"]: GRADE_EXACT for p in hits},
            note="用語の定義を引く項目検索",
        )

    # --- heading -------------------------------------------------------------
    headings: dict[str, list[dict[str, Any]]] = {}
    for passage in passages:
        if passage["kind"] != "article":
            continue
        title = passage["title"]
        matched = re.search(r"（(.+)）$", title) or re.search(r"\((.+)\)$", title)
        name = matched.group(1) if matched else title
        if name and len(name) >= 3:
            headings.setdefault(name, []).append(passage)
    for i, (name, hits) in enumerate(sorted(headings.items()), start=1):
        grades = {p["passage_id"]: GRADE_EXACT for p in hits}
        # その条に属する表・図は「関連する」
        owners = {p["passage_id"] for p in hits}
        for passage in passages:
            if passage["kind"] in ("table", "figure") and passage["citation"]:
                for hit in hits:
                    if passage["doc_id"] == hit["doc_id"] and passage["citation"] == hit["citation"]:
                        grades.setdefault(passage["passage_id"], GRADE_RELATED)
        add(
            f"q_head_{i:04d}",
            "heading",
            name,
            grades,
            note=f"見出しの項目検索（{len(owners)} 文書に同名の条がある）",
        )

    # --- scoped（商品名で絞り込む） --------------------------------------------
    scoped = 0
    for name, hits in sorted(headings.items()):
        if len(hits) < 2:
            continue  # 複数文書にある見出しだけが絞り込みの検査になる
        for hit in sorted(hits, key=lambda p: p["passage_id"])[:1]:
            scoped += 1
            add(
                f"q_scope_{scoped:04d}",
                "scoped",
                f"{hit['product_name']}の{name}",
                {hit["passage_id"]: GRADE_EXACT},
                note="商品名で絞り込む項目検索（同名の条が他文書にもある）",
            )

    # --- qa ------------------------------------------------------------------
    n = 0
    for doc_id, items in sorted(qa_by_doc.items()):
        for item in items:
            evidence = [e for e in item.get("evidence", []) if e]
            if not evidence:
                continue
            grades: dict[str, int] = {}
            for element_id in evidence:
                passage_id = _resolve_evidence(f"{element_id}", element_index)
                if passage_id:
                    grades[passage_id] = GRADE_EXACT
            if not grades:
                continue
            # 同じ条の別のパッセージは「関連する」
            citations = {by_id[p]["citation"] for p in grades if by_id[p]["citation"]}
            for passage in passages:
                if passage["doc_id"] != doc_id or passage["passage_id"] in grades:
                    continue
                if passage["citation"] and passage["citation"] in citations:
                    grades[passage["passage_id"]] = GRADE_RELATED
            n += 1
            add(
                f"q_qa_{n:04d}",
                "qa",
                item["question"],
                grades,
                note=f"{item['type']} の問い（{doc_id}）",
            )
    return queries, qrels
