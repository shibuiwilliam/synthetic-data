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
import re
from pathlib import Path
from typing import Any

from keiyaku.answer import load_answer
from keiyaku.eval.metrics import cer, iou, kendall_tau, normalize, set_f1, teds
from keiyaku.models import Answer


def _pred_list(pred: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = pred.get(key) or []
    return [v for v in value if isinstance(v, dict)]


def _occurrence_keys_pairs(keys: list[tuple[str, str]]) -> list[tuple[tuple[str, str], int]]:
    """`_occurrence_keys` の (label, title) 版。見出しの突合に使う。"""
    seen: dict[tuple[str, str], int] = {}
    out: list[tuple[tuple[str, str], int]] = []
    for key in keys:
        index = seen.get(key, 0)
        seen[key] = index + 1
        out.append((key, index))
    return out


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

    # 同じ (label, title) の見出しは複数ある（「(1)」や、章をまたいで同名の条）。
    # 鍵をテキストだけにすると満点の予測でも取り違え、page_acc が 0.39 まで落ちていた。
    # 出現回数を鍵に混ぜて、n 番目の予測を n 番目の gold に当てる（docs/remaining_issues.md S7）。
    gold_by_key: dict[tuple[str, str, int], Any] = dict(
        zip(
            [(k[0][0], k[0][1], k[1]) for k in _occurrence_keys_pairs(gold)],
            answer.outline,
            strict=False,
        )
    )
    pred_keys = _occurrence_keys_pairs(got)
    kind_ok = page_ok = cite_ok = matched = 0
    for item, ((label, title), occurrence) in zip(pred_items, pred_keys, strict=False):
        entry = gold_by_key.get((label, title, occurrence))
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

    pred_items = _pred_list(pred, "elements")
    pred_texts = [normalize(item.get("text", "")) for item in pred_items]
    hit = cite_ok = kind_ok = 0
    for key, item in zip(_occurrence_keys(pred_texts), pred_items, strict=True):
        info = gold.get(key)
        if info is None:
            continue
        hit += 1
        cite_ok += int(normalize(item.get("citation", "")) == normalize(info.citation))
        kind_ok += int(item.get("kind") == info.kind)

    # **段落の切り方は読み取り側でかならずずれる。** 全文一致だけだと、位置づけを
    # 当てられたかが測れない（素朴な読み取り器で coverage 0.375）。
    # gold の本文を含む予測要素があれば当たったとみなす指標を併記する
    # （docs/remaining_issues.md T9）。厳密一致の数値は変えない。
    contains_hit = contains_cite = 0
    used: set[int] = set()
    for (text, _occurrence), info in gold.items():
        for i, candidate in enumerate(pred_texts):
            if i in used or not candidate or text not in candidate:
                continue
            used.add(i)
            contains_hit += 1
            contains_cite += int(normalize(pred_items[i].get("citation", "")) == normalize(info.citation))
            break
    return {
        "gold_elements": len(gold),
        "matched": hit,
        "coverage": round(hit / len(gold), 4) if gold else 0.0,
        "citation_acc": round(cite_ok / hit, 4) if hit else 0.0,
        "kind_acc": round(kind_ok / hit, 4) if hit else 0.0,
        #: 包含での対応づけ（段落の切り方のずれを許す）
        "matched_contains": contains_hit,
        "coverage_contains": round(contains_hit / len(gold), 4) if gold else 0.0,
        "citation_acc_contains": round(contains_cite / contains_hit, 4) if contains_hit else 0.0,
    }


# --- 表 -----------------------------------------------------------------------


def _gold_tables(answer: Answer) -> list[dict[str, Any]]:
    from keiyaku.build import expand_grid
    from keiyaku.lint.walk import iter_blocks
    from keiyaku.models import Table

    # **列挙として組んだ表は「表」として採点しない。**
    # 「次に掲げる事由」の受けなどは、紙面では格子に組まれているが読み手には箇条書きで、
    # 実際に VLM は `enumerations` に出した。両方に出すことを求めると同じ中身を二重に
    # 数えることになり、正しく読めた予測の TEDS が下がる（golf-0001 で 13 表中 6 表が
    # これに当たり、TEDS が 0.27 まで落ちた。docs/remaining_issues.md X3）。
    # 中身は `derived.enumerations` で採点されるので、取りこぼしにはならない。
    as_enumeration = {e.id for e in answer.source.derived.enumerations if e.source == "table"}

    out = []
    for block, _owner, _article in iter_blocks(answer.source):
        if not isinstance(block, Table) or block.id in as_enumeration:
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


#: 表を中身で突き合わせるときに要求する重なり（セルの文字の Jaccard）
TABLE_CONTENT_MIN = 0.3


def _table_by_content(
    gold: list[dict[str, Any]], grid: list[list[str]], used: set[int]
) -> dict[str, Any] | None:
    """まだ使っていない gold のうち、セルの文字がいちばん重なる表。"""
    mine = {c for row in grid for c in row if c}
    if not mine:
        return None
    best, best_score = None, 0.0
    for target in gold:
        if id(target) in used:
            continue
        theirs = {c for row in target["grid"] for c in row if c}
        if not theirs:
            continue
        score = len(mine & theirs) / len(mine | theirs)
        if score > best_score:
            best, best_score = target, score
    return best if best_score >= TABLE_CONTENT_MIN else None


def score_tables(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    """表の採点。**キャプション → 中身 → 位置**の順に 1 対 1 で対応づける。

    位置（並び順）だけで対応づけていたため、**紙面にはあるが gold では表ではないもの**
    （罫線で囲まれた当事者表示など）を 1 つ余分に出しただけで以降がすべてずれ、
    TEDS が 0.36 まで落ちた（2026-10-03 の盲検）。測っているのは表の読み取りであって
    並べ方ではないので、中身（セルの文字の重なり）での突合を間に挟む。
    """
    gold = _gold_tables(answer)
    pred_items = _pred_list(pred, "tables")
    grids = [[[normalize(c) for c in row] for row in (item.get("grid") or [])] for item in pred_items]
    # キャプションは**正規化して**突き合わせる。全角の文書は gold が「表１」、
    # 読み取り側は「表1」と出すのが自然で、生の文字列比較だと当たらない
    # （docs/remaining_issues.md X3）。
    by_caption = {normalize(t["caption_label"]): t for t in gold if t["caption_label"]}
    pair: dict[int, dict[str, Any]] = {}
    used: set[int] = set()

    for i, item in enumerate(pred_items):  # 1. キャプション
        target = by_caption.get(normalize(item.get("caption_label") or ""))
        if target is not None and id(target) not in used:
            pair[i] = target
            used.add(id(target))

    candidates: list[tuple[float, int, int]] = []  # 2. 中身（重なりの大きい順）
    for i, grid in enumerate(grids):
        if i in pair:
            continue
        mine = {c for row in grid for c in row if c}
        if not mine:
            continue
        for j, target in enumerate(gold):
            theirs = {c for row in target["grid"] for c in row if c}
            if not theirs:
                continue
            score = len(mine & theirs) / len(mine | theirs)
            if score >= TABLE_CONTENT_MIN:
                candidates.append((score, i, j))
    for _score, i, j in sorted(candidates, key=lambda x: (-x[0], x[1], x[2])):
        if i in pair or id(gold[j]) in used:
            continue
        pair[i] = gold[j]
        used.add(id(gold[j]))

    remaining = [t for t in gold if id(t) not in used]  # 3. 位置（残り物どうし）
    for i in range(len(pred_items)):
        if i in pair or not remaining:
            continue
        target = remaining.pop(0)
        pair[i] = target
        used.add(id(target))

    scores: list[float] = []
    triple_gold: list[tuple[str, str, str]] = []
    triple_pred: list[tuple[str, str, str]] = []
    for i, item in enumerate(pred_items):
        target = pair.get(i)
        if target is None:
            continue
        scores.append(teds(target["grid"], grids[i]))
        triple_gold.extend(target["triples"])
        for record in item.get("cells") or []:
            triple_pred.append(
                (
                    "|".join(normalize(h) for h in record.get("row_headers", [])),
                    "|".join(normalize(h) for h in record.get("col_headers", [])),
                    normalize(record.get("value", "")),
                )
            )
    for target in gold:  # 当てられなかった gold は 0 点として数える
        if id(target) not in used:
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
    by_caption = {normalize(g["caption_label"]): g for g in gold if g["caption_label"]}
    nodes_g: list[str] = []
    nodes_p: list[str] = []
    edges_g: list[str] = []
    edges_p: list[str] = []
    paths_g: list[str] = []
    paths_p: list[str] = []
    used: set[int] = set()
    for i, item in enumerate(pred_items):
        target = by_caption.get(normalize(item.get("caption_label") or ""))
        if target is None and i < len(gold):
            target = gold[i]
        if target is None:
            continue
        used.add(id(target))
        nodes_g.extend(target["nodes"])
        edges_g.extend(target["edges"])
        paths_g.extend(target["paths"])
        # `id` は任意。**無ければラベルそのものを鍵にする**（鍵を None にまとめると
        # ノードが 1 件に潰れる。2026-10-02 の V-D で実害）。
        labels = {}
        for node in item.get("nodes") or []:
            label = normalize(node.get("label", ""))
            labels[node.get("id") or label] = label
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


#: 行頭の列挙番号。**紙面に出る形（「（１）取締役会」）でも、番号を落とした形でも同じ点にする**
#: （docs/remaining_issues.md T8）。読み取り側に「番号を落とせ」と求めるのは紙面から離れた要求。
ENUM_LABEL = re.compile(r"^(?:[（(][0-9０-９a-zA-Zａ-ｚア-ン]{1,3}[）)]|[①-⑳]|[❶-❿]|[0-9０-９]{1,2}[.．、])")


def strip_enum_label(text: str) -> str:
    """行頭の列挙番号を落とす。**正規化の前に呼ぶこと。**

    NFKC は ① を「1」にしてしまうので、正規化のあとでは丸数字と
    「10日以内に…」の 1 を見分けられない。
    """
    return ENUM_LABEL.sub("", text, count=1)


#: 列挙を中身で突き合わせるときに要求する重なり（Jaccard）。
#: これ未満なら「別の列挙」とみなす。
ENUM_CONTENT_MIN = 0.5


def score_enumerations(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    """列挙の順番一致。**まず citation で、合わなければ中身で**突き合わせる。

    citation だけで突き合わせていたため、**項目を完全に読めていても条番号を外すと 0**
    になっていた（2026-09-28 の P7-1：`con-0001` は 6 列挙すべて正しく読めているのに
    coverage 0。約款型は条見出しが条番号の上に来るので、行単位の読み取りでは条番号を
    拾いにくい）。測っているのは「列挙の順番を保てるか」なので、条番号の当てはめとは
    切り離す（`docs/decisions.md` 119。HITL の H6 で承認済みの指標定義の変更）。
    """
    gold = {
        e.citation or e.id: [normalize(strip_enum_label(i.text)) for i in e.items]
        for e in answer.source.derived.enumerations
    }
    pred_items = _pred_list(pred, "enumerations")
    exact = 0
    matched = 0
    by_citation = 0
    used: set[str] = set()
    for item in pred_items:
        key = normalize(item.get("citation", "")) or item.get("id", "")
        got = [normalize(strip_enum_label(x)) for x in item.get("items") or []]
        hit = next((k for k in gold if normalize(k) == key and k not in used), None)
        if hit is not None:
            by_citation += 1
        else:
            hit = _enum_by_content(gold, got, used)
        if hit is None:
            continue
        used.add(hit)
        matched += 1
        exact += int(got == gold[hit])
    return {
        "gold_enumerations": len(gold),
        "matched": matched,
        "matched_by_citation": by_citation,
        "order_exact": round(exact / matched, 4) if matched else 0.0,
        "coverage": round(matched / len(gold), 4) if gold else 0.0,
    }


def _enum_by_content(gold: dict[str, list[str]], got: list[str], used: set[str]) -> str | None:
    """まだ使っていない gold のうち、項目の重なりがいちばん大きいもの。"""
    if not got:
        return None
    mine = set(got)
    best, best_score = None, 0.0
    for key, items in gold.items():
        if key in used:
            continue
        theirs = set(items)
        if not theirs:
            continue
        score = len(mine & theirs) / len(mine | theirs)
        if score > best_score:
            best, best_score = key, score
    return best if best_score >= ENUM_CONTENT_MIN else None


# --- bbox（画像からの読み取りの位置あわせ） -----------------------------------

#: 「当たり」とみなす IoU の下限
IOU_HIT = 0.5


def score_layout(answer: Answer, pred: dict[str, Any]) -> dict[str, Any]:
    """予測が `bbox` を出しているとき、gold の fragment と重なっているかを測る。

    突合は本文テキスト（出現回数つき）。`bbox` を出さない予測では `predicted` が 0 になる。
    """
    # bbox は**同じ本文がどこに出ていても当たりでよい**ので、テキストだけを鍵にして
    # すべての fragment を候補にする（citation とは違い、何回目かを問う必要がない）。
    gold: dict[str, list[tuple[int, list[float]]]] = {}
    for element_id, plain in answer.source.derived.plain_text.items():
        element = answer.layout.elements.get(element_id)
        key = normalize(plain.without_label)
        if not key or element is None or not element.fragments:
            continue
        gold.setdefault(key, []).extend((f.page, list(f.bbox)) for f in element.fragments)

    pred_items = [i for i in _pred_list(pred, "elements") if i.get("bbox")]
    scores: list[float] = []
    for item in pred_items:
        boxes = gold.get(normalize(item.get("text", "")))
        if not boxes:
            continue
        page = item.get("page")
        candidates = [b for p, b in boxes if page is None or p == page] or [b for _p, b in boxes]
        scores.append(max(iou(b, item["bbox"]) for b in candidates))
    return {
        "gold_elements": len(gold),
        "predicted": len(pred_items),
        "matched": len(scores),
        "iou_mean": round(sum(scores) / len(scores), 4) if scores else 0.0,
        f"hit@iou{IOU_HIT}": round(sum(1 for s in scores if s >= IOU_HIT) / len(scores), 4)
        if scores
        else 0.0,
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
    answer = load_answer(dataset_dir)
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
        "layout": score_layout(answer, prediction),
        "reading_order": score_reading_order(answer, prediction),
        "qa": score_qa(qa_items, prediction),
    }
