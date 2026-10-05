"""`answer.json` から「満点の予測」を作る（docs/evaluation.md）。

2 つの役目がある：

1. **予測フォーマットの実装例**。読み取り側はこの形の JSON を出せばよい。
2. **ハーネスの自己評価**。満点の予測を入れて満点が出ること、
   わざと崩した予測で点が下がることを確かめる（`tests/unit/test_eval.py`）。
"""

from __future__ import annotations

import random
from typing import Any

from keiyaku.models import Answer


def build_prediction(answer: Answer, qa_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:  # noqa: C901
    """満点になる予測 JSON。`qa_items` を渡すと QA も満点になる。"""
    derived = answer.source.derived
    from keiyaku.build import expand_grid
    from keiyaku.lint.walk import iter_blocks
    from keiyaku.models import Table

    pages = [{"number": p.number, "text": p.text} for p in answer.pages]

    outline = [
        {
            "label": o.label,
            "title": o.title,
            "heading_text": o.heading_text,
            "kind": o.kind,
            "page": o.page,
            "citation": o.citation,
        }
        for o in answer.outline
    ]

    elements: list[dict[str, Any]] = []
    for page in answer.layout.pages:
        for element_id in page.reading_order:
            plain = derived.plain_text.get(element_id)
            info = derived.labels.get(element_id)
            if plain is None or not plain.without_label.strip():
                continue
            element = answer.layout.elements.get(element_id)
            bbox = next(
                (list(f.bbox) for f in (element.fragments if element else []) if f.page == page.number),
                None,
            )
            elements.append(
                {
                    "text": plain.without_label,
                    "page": page.number,
                    "kind": info.kind if info else None,
                    "citation": info.citation if info else "",
                    **({"bbox": bbox} if bbox else {}),
                }
            )

    # 列挙として組んだ表は `enumerations` で採点するので `tables` には出さない
    # （採点側と同じ除き方をする。docs/remaining_issues.md X3）。
    as_enumeration = {e.id for e in derived.enumerations if e.source == "table"}

    tables: list[dict[str, Any]] = []
    for block, _owner, _article in iter_blocks(answer.source):
        if not isinstance(block, Table) or block.id in as_enumeration:
            continue
        table_derived = derived.tables.get(block.id)
        grid = [
            [
                derived.plain_text[cell.id].without_label
                if cell is not None and cell.id in derived.plain_text
                else ""
                for cell in row
            ]
            for row in expand_grid(block)
        ]
        cells = []
        if table_derived:
            for cell_id, path in table_derived.header_path.items():
                value = derived.plain_text.get(cell_id)
                if value is None:
                    continue
                cells.append(
                    {
                        "row_headers": list(path.row_headers),
                        "col_headers": list(path.col_headers),
                        "value": value.without_label,
                    }
                )
        tables.append(
            {
                "caption_label": table_derived.caption_label if table_derived else None,
                "grid": grid,
                "cells": cells,
            }
        )

    figures = [
        {
            "caption_label": d.caption_label,
            "nodes": [{"id": n.id, "label": n.label, "role": n.role} for n in d.graph.nodes],
            "edges": [{"from": e.from_, "to": e.to, "relation": e.relation} for e in d.graph.edges],
            "paths": d.paths,
        }
        for d in derived.figures.values()
    ]

    enumerations = [
        {"citation": e.citation or e.id, "items": [i.text for i in e.items]} for e in derived.enumerations
    ]

    return {
        "doc_id": answer.doc_id,
        "pages": pages,
        "outline": outline,
        "elements": elements,
        "tables": tables,
        "figures": figures,
        "enumerations": enumerations,
        "qa": [{"id": item["id"], "answer": item["answer"]} for item in (qa_items or [])],
    }


def _drop_some(rows: list, rng: random.Random, rate: float) -> list:
    """`rate` で間引く。ただし **2 つ以上あるなら必ず 1 つは落とす**。

    `degrade` は「わざと崩して点差が出ることを確かめる」ための道具なので、
    乱数の巡り合わせで 1 つも落ちないと目的を果たさない（小さい表では実際に起きて、
    `teds_macro` が満点のままになった）。
    """
    kept = [row for row in rows if rng.random() > rate]
    if len(rows) > 1 and len(kept) == len(rows):
        kept = kept[:-1]
    return kept


def degrade(prediction: dict[str, Any], *, seed: int = 0, rate: float = 0.3) -> dict[str, Any]:
    """予測をわざと崩す（ハーネスが点差を出せることを確かめるため）。

    - ページ本文の一部の文字を落とす
    - 見出しを何割か落とす
    - 構造位置（citation）を空にする
    - 表の行を落とす、図のノードを落とす
    """
    rng = random.Random(seed)
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in prediction.items()}

    out["pages"] = [
        {**p, "text": "".join(c for c in p["text"] if rng.random() > rate * 0.2)} for p in out["pages"]
    ]
    out["outline"] = [o for o in out["outline"] if rng.random() > rate]
    out["elements"] = [{**e, "citation": ""} for e in out["elements"]]
    out["tables"] = [{**t, "grid": _drop_some(t["grid"], rng, rate), "cells": []} for t in out["tables"]]
    out["figures"] = [
        {**f, "nodes": _drop_some(f["nodes"], rng, rate), "edges": [], "paths": []} for f in out["figures"]
    ]
    out["enumerations"] = []
    return out


# --- 現実の読み取り誤りで崩す（docs/remaining_issues.md S6） -------------------

#: OCR がよく取り違える字形。**NFKC で吸収されない**組み合わせだけを選ぶ
#: （全角半角の揺れは `normalize()` が消すので、崩しても CER が動かない）。
GLYPH_CONFUSIONS: dict[str, str] = {
    "口": "ロ",
    "ロ": "口",
    "力": "カ",
    "カ": "力",
    "工": "エ",
    "エ": "工",
    "二": "ニ",
    "ニ": "二",
    "八": "ハ",
    "ハ": "八",
    "夕": "タ",
    "タ": "夕",
    "卜": "ト",
    "ト": "卜",
    "ー": "一",
    "一": "ー",
    "日": "目",
    "目": "日",
    "未": "末",
    "末": "未",
    "千": "干",
    "干": "千",
}


class _Dice:
    """`rate` に依らない乱数列。**崩しが rate について入れ子になる**ようにする。

    先に一様乱数を引いてから `rate` と比べるので、`rate=0.1` で壊れた箇所は
    `rate=0.3` でも必ず壊れる。これで「崩すほど点が下がる」を単調性として
    テストで固定できる（rate ごとに乱数を引き直すと単調にならない）。

    **引く回数を rate に依存させてはならない。** 条件式の短絡や、間引いた要素の
    ぶんだけ draw を飛ばすと乱数列がずれ、入れ子でなくなる（実際に τ と QA が
    単調に下がらなくなった）。`hit()` は必ず無条件に呼ぶ。
    """

    def __init__(self, seed: int, rate: float) -> None:
        self._rng = random.Random(seed)
        self._rate = rate

    def hit(self, weight: float = 1.0) -> bool:
        return self._rng.random() < self._rate * weight


def _confuse(text: str, dice: _Dice, *, swap: float = 1.0, drop: float = 0.05) -> str:
    """字形の取り違えと脱字。取り違えられる字はそれを、それ以外はまれに落とす。"""
    out: list[str] = []
    for char in text:
        swapped = dice.hit(swap)
        dropped = dice.hit(drop)
        if char in GLYPH_CONFUSIONS and swapped:
            out.append(GLYPH_CONFUSIONS[char])
        elif not dropped:
            out.append(char)
    return "".join(out)


def _shorten_citation(citation: str) -> str:
    """「第2章 第1条 (1)」→「第2章 第1条」。項の取りこぼしを模す。"""
    parts = citation.split(" ")
    return " ".join(parts[:-1]) if len(parts) > 1 else ""


def _merge_rows(grid: list[list[str]], dice: _Dice) -> list[list[str]]:
    """隣り合う行を結合する。結合セルの展開に失敗した読み取りを模す。

    対を (0,1) (2,3) … に固定するので、どの対を壊すかは rate に対して入れ子になる。
    """
    out: list[list[str]] = []
    for i in range(0, len(grid), 2):
        pair = grid[i : i + 2]
        merge = dice.hit(0.5)
        if len(pair) == 2 and merge:
            out.append([a + b for a, b in zip(pair[0], pair[1], strict=False)])
        else:
            out.extend(pair)
    return out


def misread(prediction: dict[str, Any], *, seed: int = 0, rate: float = 0.3) -> dict[str, Any]:
    """**現実の読み取りが起こす誤り**で予測を崩す（`degrade` より現実に近い）。

    - 字形の取り違え（「口」と「ロ」など、NFKC で吸収されないもの）と脱字
    - 表の行の結合（結合セルの展開に失敗する）と端の列の取りこぼし
    - 見出しの取りこぼし（項・号のような深い見出しほど落ちやすい）
    - 構造位置の浅い読み（「第2章 第1条 (1)」→「第2章 第1条」）
    - 段組の取り違え（左段と右段を交互に読む）
    - 図のノード・エッジの取りこぼし

    `rate` を上げると崩れが増え、**壊す箇所は前の rate の上位集合**になる。
    `tests/unit/test_eval.py` が指標の単調性を固定している。
    """
    dice = _Dice(seed, rate)
    out: dict[str, Any] = dict(prediction)

    out["pages"] = [
        {**p, "text": _confuse(p["text"], dice, swap=0.9, drop=0.02)} for p in prediction.get("pages") or []
    ]

    outline: list[dict[str, Any]] = []
    for entry in prediction.get("outline") or []:
        # 深い見出し（項・号）ほど本文と見分けがつかず、落ちやすい
        weight = 1.0 if entry.get("kind") in ("paragraph", "item", "subitem", "subsubitem") else 0.3
        drop = dice.hit(weight)
        title = _confuse(entry.get("title") or "", dice, swap=0.5, drop=0.0)
        if not drop:
            outline.append({**entry, "title": title})
    out["outline"] = outline

    elements: list[dict[str, Any]] = []
    for element in prediction.get("elements") or []:
        citation = element.get("citation") or ""
        if dice.hit(0.8):
            citation = _shorten_citation(citation)
        elements.append({**element, "citation": citation})
    # 段組の取り違え：ページごとに、前半と後半を交互に読んだ並びにする
    by_page: dict[Any, list[dict[str, Any]]] = {}
    for element in elements:
        by_page.setdefault(element.get("page"), []).append(element)
    shuffled: list[dict[str, Any]] = []
    for page in sorted(by_page, key=lambda p: (p is None, p)):
        rows = by_page[page]
        swap = dice.hit(0.6)
        if len(rows) > 3 and swap:
            half = len(rows) // 2
            left, right = rows[:half], rows[half:]
            rows = [x for pair in zip(left, right, strict=False) for x in pair]
            rows += left[len(right) :] + right[len(left) :]
        shuffled.extend(rows)
    out["elements"] = shuffled

    tables: list[dict[str, Any]] = []
    for table in prediction.get("tables") or []:
        grid = _merge_rows([list(row) for row in table.get("grid") or []], dice)
        narrow = dice.hit(0.4)
        if grid and len(grid[0]) > 1 and narrow:
            grid = [row[:-1] for row in grid]  # 端の列を取りこぼす
        cells = [c for c in table.get("cells") or [] if not dice.hit(0.5)]
        tables.append({**table, "grid": grid, "cells": cells})
    out["tables"] = tables

    figures: list[dict[str, Any]] = []
    for figure in prediction.get("figures") or []:
        nodes: list[dict[str, Any]] = []
        for node in figure.get("nodes") or []:
            drop = dice.hit(0.3)
            label = _confuse(node.get("label") or "", dice, swap=0.5, drop=0.0)
            if not drop:
                nodes.append({**node, "label": label})
        kept = {n.get("id") for n in nodes}
        edges: list[dict[str, Any]] = []
        for edge in figure.get("edges") or []:
            drop = dice.hit(0.5)
            if not drop and edge.get("from") in kept and edge.get("to") in kept:
                edges.append(edge)
        paths: list[list[str]] = []
        for path in figure.get("paths") or []:
            drop = dice.hit(0.5)
            labels = [_confuse(x, dice, swap=0.5, drop=0.0) for x in path]
            if not drop:
                paths.append(labels)
        figures.append({**figure, "nodes": nodes, "edges": edges, "paths": paths})
    out["figures"] = figures

    out["enumerations"] = [
        {**e, "items": [x for x in e.get("items") or [] if not dice.hit(0.4)]}
        for e in prediction.get("enumerations") or []
    ]

    qa: list[dict[str, Any]] = []
    for item in prediction.get("qa") or []:
        answer = item.get("answer")
        broken = dice.hit(0.5)
        if isinstance(answer, str) and broken:
            answer = answer[:-1] if len(answer) > 1 else ""
        qa.append({**item, "answer": answer})
    out["qa"] = qa
    return out
