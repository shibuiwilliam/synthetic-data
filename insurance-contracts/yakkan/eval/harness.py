"""予測 JSON を `answer.json` と突き合わせて採点する（CLAUDE.md §9・docs/evaluation.md）。

**予測に内部 id は無い前提**で、突合はすべて中身で行う：

| 観点 | 突合のしかた | 指標 |
|---|---|---|
| ページ本文 | ページ番号 | CER（文字誤り率。小さいほど良い） |
| 見出しツリー | (label, title) の多重集合 | F1 ／ 一致した見出しの kind・page の正解率 |
| 構造位置 | 本文テキストの正規化一致 | citation の正解率（**「第2章 第1条 (1)」を当てられるか**） |
| 表 | caption_label、無ければ出現順 | TEDS ／ セル値 F1（header_path 経由の 3 つ組） |
| 図 | caption_label、無ければ出現順 | ノード F1 ／ エッジ F1 ／ 経路 F1 |
| 列挙 | 親の citation | 項目の順番つき一致率 |
| 読み順 | ページごと、テキストで対応づけ | Kendall の τ |
| QA | id | 完全一致 ／ 部分一致 |
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from yakkan.eval.metrics import cer, kendall_tau, normalize, set_f1, teds
from yakkan.models import Answer


def _pred_list(pred: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = pred.get(key) or []
    return [v for v in value if isinstance(v, dict)]


def _occurrence_keys(texts: list[str]) -> list[tuple[str, int]]:
    """同じ本文が複数あっても取り違えないよう、(テキスト, 何回目) の鍵にする。

    約款には同じ一文が別の条に現れる（「なお従前の例による。」など）。
    テキストだけを鍵にすると、満点の予測でも取り違えて点が下がる。
    """
    seen: dict[str, int] = {}
    out: list[tuple[str, int]] = []
    for text in texts:
        index = seen.get(text, 0)
        seen[text] = index + 1
        out.append((text, index))
    return out


# --- ページ本文 ---------------------------------------------------------------


def score_pages(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    by_number = {p.get("number"): p.get("text", "") for p in _pred_list(pred, "pages")}
    scores = [cer(page.text, by_number.get(page.number, "")) for page in answer.pages]
    return {
        "pages": len(scores),
        "pages_predicted": len(by_number),
        "cer_macro": round(sum(scores) / len(scores), 4) if scores else 1.0,
        "cer_worst": round(max(scores), 4) if scores else 1.0,
    }


# --- 見出しツリー -------------------------------------------------------------


def score_outline(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    gold = [(normalize(o.label), normalize(o.title)) for o in answer.outline]
    pred_items = _pred_list(pred, "outline")
    got = [(normalize(o.get("label", "")), normalize(o.get("title", ""))) for o in pred_items]
    result = set_f1(gold, got)

    gold_by_key: dict[tuple[str, str], Any] = {}
    for entry in answer.outline:
        gold_by_key.setdefault((normalize(entry.label), normalize(entry.title)), entry)
    kind_ok = page_ok = cite_ok = matched = 0
    for item in pred_items:
        key = (normalize(item.get("label", "")), normalize(item.get("title", "")))
        entry = gold_by_key.get(key)
        if entry is None:
            continue
        matched += 1
        kind_ok += int(item.get("kind") == entry.kind)
        page_ok += int(item.get("page") == entry.page)
        cite_ok += int(normalize(item.get("citation", "")) == normalize(entry.citation))
    result |= {
        "matched": matched,
        "kind_acc": round(kind_ok / matched, 4) if matched else 0.0,
        "page_acc": round(page_ok / matched, 4) if matched else 0.0,
        "citation_acc": round(cite_ok / matched, 4) if matched else 0.0,
    }
    return result


# --- 構造位置（本文テキスト → citation） --------------------------------------


def score_citations(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    """**この文はどこに属するか**を当てられたかを測る。

    gold は本文ノード（項・号）。予測のテキストを正規化して gold と突き合わせ、
    当たったものについて citation の一致を見る。
    """
    infos: list[Any] = []
    texts: list[str] = []
    for element_id, plain in answer.source.derived.plain_text.items():
        info = answer.source.derived.labels.get(element_id)
        if info is None or info.kind not in ("paragraph", "item", "subitem", "subsubitem"):
            continue
        key = normalize(plain.without_label)
        if not key:
            continue
        texts.append(key)
        infos.append(info)
    gold = dict(zip(_occurrence_keys(texts), infos, strict=True))

    pred_texts = [normalize(item.get("text", "")) for item in _pred_list(pred, "elements")]
    hit = cite_ok = kind_ok = 0
    for key, item in zip(_occurrence_keys(pred_texts), _pred_list(pred, "elements"), strict=True):
        info = gold.get(key)
        if info is None:
            continue
        hit += 1
        cite_ok += int(normalize(item.get("citation", "")) == normalize(info.citation))
        kind_ok += int(item.get("kind") == info.kind)
    return {
        "gold_elements": len(gold),
        "matched": hit,
        "coverage": round(hit / len(gold), 4) if gold else 0.0,
        "citation_acc": round(cite_ok / hit, 4) if hit else 0.0,
        "kind_acc": round(kind_ok / hit, 4) if hit else 0.0,
    }


# --- 表 -----------------------------------------------------------------------


def _gold_tables(answer: Answer) -> list[dict[str, Any]]:
    from yakkan.build import expand_grid
    from yakkan.lint.walk import iter_blocks
    from yakkan.models import Table

    out = []
    for block, _owner, _article in iter_blocks(answer.source):
        if not isinstance(block, Table):
            continue
        derived = answer.source.derived.tables.get(block.id)
        grid = [
            [
                normalize(answer.source.derived.plain_text.get(cell.id, None).without_label)
                if cell is not None and cell.id in answer.source.derived.plain_text
                else ""
                for cell in row
            ]
            for row in expand_grid(block)
        ]
        triples = []
        if derived:
            for cell_id, path in derived.header_path.items():
                value = answer.source.derived.plain_text.get(cell_id)
                if value is None:
                    continue
                triples.append(
                    (
                        "|".join(normalize(h) for h in path.row_headers),
                        "|".join(normalize(h) for h in path.col_headers),
                        normalize(value.without_label),
                    )
                )
        out.append(
            {
                "caption_label": derived.caption_label if derived else None,
                "grid": grid,
                "triples": triples,
            }
        )
    return out


def score_tables(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    gold = _gold_tables(answer)
    pred_items = _pred_list(pred, "tables")
    by_caption = {t["caption_label"]: t for t in gold if t["caption_label"]}
    used: set[int] = set()
    scores: list[float] = []
    triple_gold: list[tuple[str, str, str]] = []
    triple_pred: list[tuple[str, str, str]] = []
    for i, item in enumerate(pred_items):
        target = by_caption.get(item.get("caption_label"))
        if target is None and i < len(gold):
            target = gold[i]
        if target is None:
            continue
        used.add(id(target))
        grid = [[normalize(c) for c in row] for row in (item.get("grid") or [])]
        scores.append(teds(target["grid"], grid))
        triple_gold.extend(target["triples"])
        for record in item.get("cells") or []:
            triple_pred.append(
                (
                    "|".join(normalize(h) for h in record.get("row_headers", [])),
                    "|".join(normalize(h) for h in record.get("col_headers", [])),
                    normalize(record.get("value", "")),
                )
            )
    missed = [t for t in gold if id(t) not in used]
    for target in missed:
        scores.append(0.0)
        triple_gold.extend(target["triples"])
    return {
        "gold_tables": len(gold),
        "pred_tables": len(pred_items),
        "teds_macro": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "cell_f1": set_f1(triple_gold, triple_pred),
    }


# --- 図 -----------------------------------------------------------------------


def score_figures(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    derived = answer.source.derived.figures
    gold = [
        {
            "caption_label": d.caption_label,
            "nodes": [normalize(n.label) for n in d.graph.nodes],
            "edges": [f"{normalize(_label(d, e.from_))}>{normalize(_label(d, e.to))}" for e in d.graph.edges],
            "paths": ["|".join(normalize(x) for x in path) for path in d.paths],
        }
        for d in derived.values()
    ]
    pred_items = _pred_list(pred, "figures")
    by_caption = {g["caption_label"]: g for g in gold if g["caption_label"]}
    nodes_g: list[str] = []
    nodes_p: list[str] = []
    edges_g: list[str] = []
    edges_p: list[str] = []
    paths_g: list[str] = []
    paths_p: list[str] = []
    used: set[int] = set()
    for i, item in enumerate(pred_items):
        target = by_caption.get(item.get("caption_label"))
        if target is None and i < len(gold):
            target = gold[i]
        if target is None:
            continue
        used.add(id(target))
        nodes_g.extend(target["nodes"])
        edges_g.extend(target["edges"])
        paths_g.extend(target["paths"])
        labels = {n.get("id"): normalize(n.get("label", "")) for n in item.get("nodes") or []}
        nodes_p.extend(labels.values())
        for edge in item.get("edges") or []:
            src = labels.get(edge.get("from"), normalize(edge.get("from", "")))
            dst = labels.get(edge.get("to"), normalize(edge.get("to", "")))
            edges_p.append(f"{src}>{dst}")
        paths_p.extend("|".join(normalize(x) for x in path) for path in item.get("paths") or [])
    for target in gold:
        if id(target) not in used:
            nodes_g.extend(target["nodes"])
            edges_g.extend(target["edges"])
            paths_g.extend(target["paths"])
    return {
        "gold_figures": len(gold),
        "pred_figures": len(pred_items),
        "node_f1": set_f1(nodes_g, nodes_p),
        "edge_f1": set_f1(edges_g, edges_p),
        "path_f1": set_f1(paths_g, paths_p),
    }


def _label(derived: Any, node_id: str) -> str:
    for node in derived.graph.nodes:
        if node.id == node_id:
            return node.label
    return node_id


# --- 列挙 ---------------------------------------------------------------------


def score_enumerations(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    gold = {
        e.citation or e.id: [normalize(i.text) for i in e.items] for e in answer.source.derived.enumerations
    }
    pred_items = _pred_list(pred, "enumerations")
    exact = 0
    matched = 0
    for item in pred_items:
        key = normalize(item.get("citation", "")) or item.get("id", "")
        target = next((v for k, v in gold.items() if normalize(k) == key), None)
        if target is None:
            continue
        matched += 1
        got = [normalize(x) for x in item.get("items") or []]
        exact += int(got == target)
    return {
        "gold_enumerations": len(gold),
        "matched": matched,
        "order_exact": round(exact / matched, 4) if matched else 0.0,
        "coverage": round(matched / len(gold), 4) if gold else 0.0,
    }


# --- 読み順 -------------------------------------------------------------------


def score_reading_order(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    text_of = {
        element_id: normalize(plain.without_label)
        for element_id, plain in answer.source.derived.plain_text.items()
    }
    taus: list[float] = []
    for page in answer.layout.pages:
        gold = [t for t in (text_of.get(e, "") for e in page.reading_order) if t]
        got = [
            normalize(item.get("text", ""))
            for item in _pred_list(pred, "elements")
            if item.get("page") == page.number
        ]
        got = [t for t in got if t]
        if len(gold) < 2 or not got:
            continue
        # 同じ本文が同じページに 2 回出ることがあるので、出現回数で区別する
        taus.append(
            kendall_tau(
                [f"{t}#{i}" for t, i in _occurrence_keys(gold)],
                [f"{t}#{i}" for t, i in _occurrence_keys(got)],
            )
        )
    return {"pages_scored": len(taus), "tau_macro": round(sum(taus) / len(taus), 4) if taus else 0.0}


# --- QA -----------------------------------------------------------------------


def score_qa(qa_items: list[dict[str, Any]], pred: dict[str, Any]) -> dict[str, Any]:
    gold = {item["id"]: item for item in qa_items}
    got = {item.get("id"): item for item in _pred_list(pred, "qa")}
    exact = partial = 0
    for qa_id, item in gold.items():
        prediction = got.get(qa_id)
        if prediction is None:
            continue
        answer_text = item["answer"]
        expected = (
            [normalize(str(x)) for x in answer_text]
            if isinstance(answer_text, list)
            else [normalize(str(answer_text))]
        )
        value = prediction.get("answer")
        actual = (
            [normalize(str(x)) for x in value]
            if isinstance(value, list)
            else [normalize(str(value if value is not None else ""))]
        )
        if actual == expected:
            exact += 1
            partial += 1
        elif set(actual) & set(expected):
            partial += 1
    total = len(gold)
    return {
        "gold_qa": total,
        "answered": len(got),
        "exact_match": round(exact / total, 4) if total else 0.0,
        "partial_match": round(partial / total, 4) if total else 0.0,
    }


# --- まとめ -------------------------------------------------------------------


def evaluate(dataset_dir: Path, prediction: dict[str, Any]) -> dict[str, Any]:
    answer = Answer.model_validate_json((dataset_dir / "answer.json").read_text(encoding="utf-8"))
    qa_path = dataset_dir / "qa.json"
    qa_items = json.loads(qa_path.read_text(encoding="utf-8"))["items"] if qa_path.exists() else []
    return {
        "doc_id": answer.doc_id,
        "text": score_pages(answer, prediction),
        "outline": score_outline(answer, prediction),
        "citation": score_citations(answer, prediction),
        "tables": score_tables(answer, prediction),
        "figures": score_figures(answer, prediction),
        "enumerations": score_enumerations(answer, prediction),
        "reading_order": score_reading_order(answer, prediction),
        "qa": score_qa(qa_items, prediction),
    }
