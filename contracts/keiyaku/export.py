"""評価向けの派生成果物を書き出す（docs/eval_dataset_plan.md P5・P8）。

`source.json` / `layout.json` / `answer.json` は正解の一次資料で、形を変えない。
評価スクリプトが最初に読むための**平らな索引**をここで作る。

- `elements.jsonl`：1 行 1 要素。テキスト・構造位置（citation）・ページ・bbox・
  表や図や列挙の中での位置を 1 か所にまとめる。
- `passages.jsonl` / `queries.jsonl` / `qrels.jsonl`：検索評価用（`keiyaku.search_set`）。
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from keiyaku.answer import load_answer
from keiyaku.export_models import (
    ElementEnumeration,
    ElementFigure,
    ElementFigureNode,
    ElementRow,
    ElementTable,
    ExportRow,
)
from keiyaku.models import Answer

#: 表のセル id（`<table_id>__r{row}c{col}`）
CELL_ID = re.compile(r"^(?P<table>.+)__r(?P<row>\d+)c(?P<col>\d+)$")

#: 本文として扱う region（ヘッダ・フッタは furniture）
#: **逐条解説（`commentary`）も含める**——紙面にあるものは正解テキストに入れる原則
#: （`docs/schema.md` §11.3）。本文と区別したい側は `region` を見る。
BODY_REGIONS = frozenset({"body", "table", "margin_note", "commentary"})


def _regions(answer: Answer) -> dict[str, str]:
    """要素 id → その要素が最初に現れた行の region。"""
    out: dict[str, str] = {}
    for page in answer.layout.pages:
        for line in page.text_lines:
            if line.element_id and line.element_id not in out:
                out[line.element_id] = line.region
    return out


def _normalize_bbox(bbox: list[float], size: tuple[float, float]) -> list[float]:
    width, height = size
    if not width or not height:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        round(bbox[0] / width, 6),
        round(bbox[1] / height, 6),
        round(bbox[2] / width, 6),
        round(bbox[3] / height, 6),
    ]


def _enum_index(answer: Answer) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for enum in answer.source.derived.enumerations:
        for item in enum.items:
            out[item.id] = {
                "enum_id": enum.id,
                "enum_source": enum.source,
                "enum_owner_id": enum.owner_id,
                "index": item.index,
                "label": item.label,
            }
    return out


def _figure_index(answer: Answer) -> dict[str, dict[str, Any]]:
    """図のノード id → 図の情報。ノード bbox は `layout.figures[].nodes` にある。"""
    out: dict[str, dict[str, Any]] = {}
    for figure_id, derived in answer.source.derived.figures.items():
        layout = answer.layout.figures.get(figure_id)
        for node in derived.graph.nodes:
            box = (layout.nodes.get(node.id) if layout else None) or None
            out[f"{figure_id}::{node.id}"] = {
                "figure_id": figure_id,
                "node_id": node.id,
                "role": node.role,
                "label": node.label,
                "page": layout.page if layout else 0,
                "bbox": list(box) if box else None,
            }
    return out


def element_rows(answer: Answer) -> list[ElementRow]:
    """`elements.jsonl` の行を作る。**テキストか bbox のどちらかを持つ要素**をすべて出す。"""
    source = answer.source
    layout = answer.layout
    derived = source.derived
    regions = _regions(answer)
    enums = _enum_index(answer)
    size = tuple(layout.page_size_pt)
    header_paths = {
        cell_id: path for table in derived.tables.values() for cell_id, path in table.header_path.items()
    }
    caption_of = {tid: t.caption_label for tid, t in derived.tables.items()}
    caption_of |= {fid: f.caption_label for fid, f in derived.figures.items()}

    rows: list[ElementRow] = []
    ids = sorted(set(derived.plain_text) | set(layout.elements))
    for element_id in ids:
        element = layout.elements.get(element_id)
        plain = derived.plain_text.get(element_id)
        label_info = derived.labels.get(element_id)
        fragments = element.fragments if element else []
        row = ElementRow(
            doc_id=answer.doc_id,
            content_id=source.content_id,
            style_id=layout.style_id,
            doctype=source.doctype,
            element_id=element_id,
            kind=element.kind if element else "unrendered",
            region=regions.get(element_id, "body"),
            text=plain.without_label if plain else "",
            text_with_label=plain.with_label if plain else "",
            label=(label_info.label if label_info else None) or (element.label if element else None),
            heading_text=label_info.heading_text if label_info else None,
            node_kind=label_info.kind if label_info else None,
            citation=label_info.citation if label_info else "",
            parent_id=label_info.parent_id if label_info else None,
            path_ids=list(label_info.path_ids) if label_info else [],
            pages=sorted({f.page for f in fragments}),
            bboxes=[list(f.bbox) for f in fragments],
            bboxes_norm=[_normalize_bbox(list(f.bbox), size) for f in fragments],
            repeated=any(f.repeated for f in fragments),
        )
        match = CELL_ID.match(element_id)
        if match and match.group("table") in derived.tables:
            table_id = match.group("table")
            path = header_paths.get(element_id)
            row.table = ElementTable(
                table_id=table_id,
                caption_label=caption_of.get(table_id),
                row=int(match.group("row")),
                col=int(match.group("col")),
                row_headers=list(path.row_headers) if path else [],
                col_headers=list(path.col_headers) if path else [],
            )
        if element_id in caption_of and element_id in derived.figures:
            figure = derived.figures[element_id]
            row.figure = ElementFigure(
                caption_label=figure.caption_label,
                node_count=len(figure.graph.nodes),
                edge_count=len(figure.graph.edges),
                paths=figure.paths,
            )
        if element_id in enums:
            row.enumeration = ElementEnumeration(**enums[element_id])
        rows.append(row)

    # 図のノードは layout.elements に出ないので、別の行として足す
    for key, info in _figure_index(answer).items():
        owner = derived.labels.get(info["figure_id"])
        rows.append(
            ElementRow(
                doc_id=answer.doc_id,
                content_id=source.content_id,
                style_id=layout.style_id,
                doctype=source.doctype,
                element_id=key,
                kind="figure_node",
                region="figure",
                text=info["label"],
                text_with_label=info["label"],
                citation=owner.citation if owner else "",
                parent_id=info["figure_id"],
                pages=[info["page"]] if info["page"] else [],
                bboxes=[info["bbox"]] if info["bbox"] else [],
                bboxes_norm=[_normalize_bbox(info["bbox"], size)] if info["bbox"] else [],
                figure_node=ElementFigureNode(
                    figure_id=info["figure_id"],
                    node_id=info["node_id"],
                    role=info["role"],
                ),
            )
        )
    return rows


def write_jsonl(rows: Sequence[ExportRow], path: Path) -> int:
    """1 行 1 モデルで書き出す。行の形はモデルの `jsonl_row()` が決める。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.jsonl_row(), ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def export_dataset(dataset_dir: Path) -> dict[str, int]:
    """1 文書ぶんの評価向け派生成果物を書き出す。"""
    from keiyaku.search_set import build_passages

    answer = load_answer(dataset_dir)
    counts = {"elements": write_jsonl(element_rows(answer), dataset_dir / "elements.jsonl")}
    counts["passages"] = write_jsonl(build_passages(answer), dataset_dir / "passages.jsonl")
    return counts


def write_readme(dataset_dir: Path, queries: Sequence[Any] = ()) -> Path:
    """`dataset/README.md`（Hugging Face のデータセットカード）を書き出す。

    **本体は `keiyaku/publish.py` が持つ**（カードは frontmatter・配布条件・ライセンスまで含み、
    公開の宣言 `specs/publish.yaml` に依存するため。`docs/publishing.md` §3）。ここは
    `keiyaku export` からの入口として残してある。

    grade 1 の打ち切り件数（qrels の解釈に直結する）は文書構成が変わるたびに動くので、
    文字列に固定値を焼き込むと `keiyaku export` を再実行しても更新されない
    （実際に auto-0001/quake-0002/travel-0003 の caption 修正だけで 1,944→1,946 に動いた）。
    呼び出し側の `build_search_set` が返す `queries` から都度数える。
    """
    from keiyaku.publish import write_readme as write_card

    return write_card(dataset_dir, queries)
