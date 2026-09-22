"""評価向けの派生成果物を書き出す（docs/eval_dataset_plan.md P5・P8）。

`source.json` / `layout.json` / `answer.json` は正解の一次資料で、形を変えない。
評価スクリプトが最初に読むための**平らな索引**をここで作る。

- `elements.jsonl`：1 行 1 要素。テキスト・構造位置（citation）・ページ・bbox・
  表や図や列挙の中での位置を 1 か所にまとめる。
- `passages.jsonl` / `queries.jsonl` / `qrels.jsonl`：検索評価用（`yakkan.search_set`）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from yakkan.answer import load_answer
from yakkan.models import Answer

#: 表のセル id（`<table_id>__r{row}c{col}`）
CELL_ID = re.compile(r"^(?P<table>.+)__r(?P<row>\d+)c(?P<col>\d+)$")

#: 本文として扱う region（ヘッダ・フッタは furniture）
BODY_REGIONS = frozenset({"body", "table", "margin_note"})


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


def element_rows(answer: Answer) -> list[dict[str, Any]]:
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

    rows: list[dict[str, Any]] = []
    ids = sorted(set(derived.plain_text) | set(layout.elements))
    for element_id in ids:
        element = layout.elements.get(element_id)
        plain = derived.plain_text.get(element_id)
        label_info = derived.labels.get(element_id)
        fragments = element.fragments if element else []
        row: dict[str, Any] = {
            "doc_id": answer.doc_id,
            "content_id": source.content_id,
            "style_id": layout.style_id,
            "genre": source.genre,
            "element_id": element_id,
            "kind": element.kind if element else "unrendered",
            "region": regions.get(element_id, "body"),
            "text": plain.without_label if plain else "",
            "text_with_label": plain.with_label if plain else "",
            "label": (label_info.label if label_info else None) or (element.label if element else None),
            "heading_text": label_info.heading_text if label_info else None,
            "node_kind": label_info.kind if label_info else None,
            "citation": label_info.citation if label_info else "",
            "parent_id": label_info.parent_id if label_info else None,
            "path_ids": list(label_info.path_ids) if label_info else [],
            "pages": sorted({f.page for f in fragments}),
            "bboxes": [list(f.bbox) for f in fragments],
            "bboxes_norm": [_normalize_bbox(list(f.bbox), size) for f in fragments],
            "repeated": any(f.repeated for f in fragments),
        }
        match = CELL_ID.match(element_id)
        if match and match.group("table") in derived.tables:
            table_id = match.group("table")
            path = header_paths.get(element_id)
            row["table"] = {
                "table_id": table_id,
                "caption_label": caption_of.get(table_id),
                "row": int(match.group("row")),
                "col": int(match.group("col")),
                "row_headers": list(path.row_headers) if path else [],
                "col_headers": list(path.col_headers) if path else [],
            }
        if element_id in caption_of and element_id in derived.figures:
            figure = derived.figures[element_id]
            row["figure"] = {
                "caption_label": figure.caption_label,
                "node_count": len(figure.graph.nodes),
                "edge_count": len(figure.graph.edges),
                "paths": figure.paths,
            }
        if element_id in enums:
            row["enumeration"] = enums[element_id]
        rows.append(row)

    # 図のノードは layout.elements に出ないので、別の行として足す
    for key, info in _figure_index(answer).items():
        rows.append(
            {
                "doc_id": answer.doc_id,
                "content_id": source.content_id,
                "style_id": layout.style_id,
                "genre": source.genre,
                "element_id": key,
                "kind": "figure_node",
                "region": "figure",
                "text": info["label"],
                "text_with_label": info["label"],
                "label": None,
                "heading_text": None,
                "node_kind": None,
                "citation": derived.labels.get(info["figure_id"], None).citation
                if info["figure_id"] in derived.labels
                else "",
                "parent_id": info["figure_id"],
                "path_ids": [],
                "pages": [info["page"]] if info["page"] else [],
                "bboxes": [info["bbox"]] if info["bbox"] else [],
                "bboxes_norm": [_normalize_bbox(info["bbox"], size)] if info["bbox"] else [],
                "repeated": False,
                "figure_node": {
                    "figure_id": info["figure_id"],
                    "node_id": info["node_id"],
                    "role": info["role"],
                },
            }
        )
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def export_dataset(dataset_dir: Path) -> dict[str, int]:
    """1 文書ぶんの評価向け派生成果物を書き出す。"""
    from yakkan.search_set import build_passages

    answer = load_answer(dataset_dir)
    counts = {"elements": write_jsonl(element_rows(answer), dataset_dir / "elements.jsonl")}
    counts["passages"] = write_jsonl(build_passages(answer), dataset_dir / "passages.jsonl")
    return counts


README = """# dataset/ — 生成した約款データセットの読み方

**このファイルは `yakkan export` が生成する。手で編集しない**（CLAUDE.md §0.4-3）。
仕様は `docs/evaluation.md`（予測の形と採点）と `docs/eval_dataset_plan.md`（設計の経緯）。

## 並び

```
dataset/
  manifest.json            全文書の一覧（ページ数・QA 数・成果物・checksums・status）
  search/                  検索評価セット（コーパス全体。content ごとに 1 スタイル）
    passages.jsonl           検索エンジンに登録する単位
    queries.jsonl            クエリ（term / heading / scoped / qa）
    qrels.jsonl              適合判定（grade 2 = 答えがある / 1 = 関連する）
  <content_id>--<style_id>/
    doc.pdf                  PDF（フォント埋め込み・テキスト層あり）
    pages/page-001.png …     150dpi のページ画像（VLM の入力）
    source.json              内容＋構造＋意味（レイアウト非依存）＋ derived
    layout.json              描画結果（ページ・要素の bbox・読み順・ヘッダ/フッタ）
    answer.json              ページ別テキスト ＋ outline（**source と layout は内包しない**）
    qa.json                  45 問（自動 30 ＋ 執筆 15）
    elements.jsonl           **1 行 1 要素の平らな索引。評価スクリプトはまずこれを読む**
    passages.jsonl           この文書ぶんの検索パッセージ
    render.html              デバッグ用の中間 HTML
```

## どのファイルを使うか

| やりたいこと | 読むファイル |
|---|---|
| ページ画像から本文を読み取る精度 | `pages/*.png` ＋ `answer.json` の `pages[].text` |
| 文章の**構造内の位置づけ**（第2章 第1条 (1)） | `elements.jsonl` の `citation` / `node_kind` / `path_ids` |
| 見出しツリー | `answer.json` の `outline`（`kind` / `parent_id` / `citation` つき） |
| 表の構造 | `source.json` の `grid` ＋ `derived.tables[].header_path` / `records` |
| 図の構造 | `derived.figures[].graph`（6 種共通の nodes / edges）＋ `paths` |
| 列挙の「N 番目」 | `derived.enumerations` |
| 読み順 | `layout.json` の `pages[].reading_order`（**内容の単位**。ラベルと本文の内訳は含まない） |
| 検索の評価 | `search/passages.jsonl` ＋ `queries.jsonl` ＋ `qrels.jsonl` |

## 注意点

- **`answer.json` は `source` と `layout` を内包しない。** 同じディレクトリに実体があるので
  参照で足りる（内包すると同じ正解が 3 か所に並び、どれが正か分からなくなる）。
  3 つをまとめて扱いたいときは `yakkan.answer.load_answer(dataset_dir)` を使う。
- **座標は pt・原点は左上。** `elements.jsonl` には正規化 [0,1] の `bboxes_norm` も入れてある。
  PNG は 150dpi なので、pt × 150/72 でピクセル座標になる。
- **繰り返し表頭とヘッダ/フッタは PDF のテキスト層に何度も出る。**
  `answer.json` の `pages[].text` からは除いてある（`text_with_furniture` が除く前）。
  `elements.jsonl` の `repeated` が true の fragment は表頭の再掲。
- **段組では 1 つの要素が複数の fragment に割れる。** `bboxes` は配列。
- **同じ content を 2 つのスタイルで描いた文書がある。** 本文は同一で版面だけが違うので、
  レイアウト頑健性の評価に使える。**検索コーパスは重複を避けて content ごとに 1 スタイルだけ**採っている。
- **qrels の grade 1 は 1 クエリ 20 件で打ち切ってある。** 打ち切ると qrels に出ないので
  評価上は非適合と同じ扱いになる。どのクエリで切ったかは `queries.jsonl` の
  `related_truncated` と `n_related_total` でわかる（1,944 クエリ中 28 件、
  おもに「事故」のような頻出の定義語）。**この 28 件で Recall@k を解釈しない。**
- すべて架空の会社・商品である（各文書の奥付に明記）。

## 採点

```
uv run yakkan eval dataset/<doc_id> --pred pred.json     # 読み取り
uv run yakkan eval --search-run run.json                 # 検索
uv run yakkan eval dataset/<doc_id> --oracle             # ハーネスの自己評価
uv run yakkan eval dataset/<doc_id> --oracle --misread 0.3   # 現実の読み取り誤りで崩して採点
```
"""


def write_readme(dataset_dir: Path) -> Path:
    path = dataset_dir / "README.md"
    path.write_text(README, encoding="utf-8")
    return path
