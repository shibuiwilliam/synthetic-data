"""評価向け成果物の型（docs/remaining_issues.md S9）。

`elements.jsonl` と検索評価セットは、以前は素の dict で組み立てていた。
**形が宣言されていないと、利用者が検証できず、フィールドを足しても記録が残らない。**
ここでは (1) 生成物がモデルを通ること、(2) `schema/*.schema.json` が最新であること、
(3) 行の形（任意の入れ子だけ出し分ける）が変わっていないことを固定する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yakkan.export_models import ElementRow, Passage, Qrel, Query

DATASET = Path("dataset")
SCHEMA = Path("schema")


def _first_dataset() -> Path | None:
    if not DATASET.is_dir():
        return None
    for directory in sorted(DATASET.iterdir()):
        if (directory / "elements.jsonl").exists():
            return directory
    return None


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_書き出した行はモデルを通る() -> None:
    directory = _first_dataset()
    if directory is None:
        pytest.skip("dataset/ が無い")
    for row in _rows(directory / "elements.jsonl"):
        ElementRow.model_validate(row)
    for row in _rows(directory / "passages.jsonl"):
        Passage.model_validate(row)


def test_検索評価セットの行はモデルを通る() -> None:
    if not (DATASET / "search" / "qrels.jsonl").exists():
        pytest.skip("検索評価セットが無い")
    for row in _rows(DATASET / "search" / "passages.jsonl"):
        Passage.model_validate(row)
    for row in _rows(DATASET / "search" / "queries.jsonl"):
        Query.model_validate(row)
    for row in _rows(DATASET / "search" / "qrels.jsonl"):
        Qrel.model_validate(row)


def test_任意の入れ子だけを出し分ける() -> None:
    """スカラは null でも行に出す（利用者が `row["parent_id"]` と書けるように）。"""
    row = ElementRow(
        doc_id="d",
        content_id="c",
        style_id="s",
        genre="auto",
        element_id="e",
        kind="paragraph",
        region="body",
        text="あ",
        text_with_label="あ",
    ).jsonl_row()
    assert row["parent_id"] is None
    assert row["heading_text"] is None
    assert "table" not in row
    assert "figure" not in row
    assert "enumeration" not in row
    assert "figure_node" not in row


def test_スキーマが最新である() -> None:
    """`yakkan schema export` を忘れて `schema/` が古くなるのを防ぐ。"""
    from yakkan.models import EXPORTED_SCHEMAS, json_schema

    stale: list[str] = []
    for name, model in EXPORTED_SCHEMAS.items():
        path = SCHEMA / f"{name}.schema.json"
        if not path.is_file():
            stale.append(f"{path} が無い")
            continue
        want = json.dumps(json_schema(model), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        if path.read_text(encoding="utf-8") != want:
            stale.append(f"{path} が古い")
    assert not stale, f"{stale}（`uv run yakkan schema export` を実行する）"
