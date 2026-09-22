"""`answer.json` から「満点の予測」を作る（docs/evaluation.md）。

2 つの役目がある：

1. **予測フォーマットの実装例**。読み取り側はこの形の JSON を出せばよい。
2. **ハーネスの自己評価**。満点の予測を入れて満点が出ること、
   わざと崩した予測で点が下がることを確かめる（`tests/unit/test_eval.py`）。
"""

from __future__ import annotations

import random
from typing import Any

from yakkan.models import Answer


def build_prediction(answer: Answer, qa_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:  # noqa: C901
    """満点になる予測 JSON。`qa_items` を渡すと QA も満点になる。"""
    derived = answer.source.derived
    from yakkan.build import expand_grid
    from yakkan.lint.walk import iter_blocks
    from yakkan.models import Table

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
            elements.append(
                {
                    "text": plain.without_label,
                    "page": page.number,
                    "kind": info.kind if info else None,
                    "citation": info.citation if info else "",
                }
            )

    tables: list[dict[str, Any]] = []
    for block, _owner, _article in iter_blocks(answer.source):
        if not isinstance(block, Table):
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
    out["tables"] = [
        {**t, "grid": [row for row in t["grid"] if rng.random() > rate], "cells": []} for t in out["tables"]
    ]
    out["figures"] = [
        {
            **f,
            "nodes": [n for n in f["nodes"] if rng.random() > rate],
            "edges": [],
            "paths": [],
        }
        for f in out["figures"]
    ]
    out["enumerations"] = []
    return out
