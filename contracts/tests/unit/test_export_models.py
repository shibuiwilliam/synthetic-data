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

from keiyaku.export_models import ElementRow, Passage, Qrel, Query

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
        doctype="auto",
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
    """`keiyaku schema export` を忘れて `schema/` が古くなるのを防ぐ。"""
    from keiyaku.models import EXPORTED_SCHEMAS, json_schema

    stale: list[str] = []
    for name, model in EXPORTED_SCHEMAS.items():
        path = SCHEMA / f"{name}.schema.json"
        if not path.is_file():
            stale.append(f"{path} が無い")
            continue
        want = json.dumps(json_schema(model), ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        if path.read_text(encoding="utf-8") != want:
            stale.append(f"{path} が古い")
    assert not stale, f"{stale}（`uv run keiyaku schema export` を実行する）"


# --- 予測の形（docs/remaining_issues.md W3・W5） ------------------------------


def test_予測のkindの語彙はNodeKindを包含する() -> None:
    """語彙が二重管理になると、片方だけ増えて読み取り側が当てられなくなる。

    予測の語彙は `NodeKind` を**包含**する。差分は「節点ではないが紙面に出て、
    本文と区別して書き起こしてほしい要素」だけで、`PREDICTION_ONLY_KINDS` に明示する
    （いまは逐条解説。docs/evaluation.md §4.5）。
    """
    import typing

    from keiyaku.export_models import PREDICTION_ONLY_KINDS, NodeKindName
    from keiyaku.models import NodeKind

    predicted = set(typing.get_args(NodeKindName))
    nodes = set(typing.get_args(NodeKind))
    assert nodes <= predicted, f"予測語彙に無い kind がある: {sorted(nodes - predicted)}"
    assert predicted - nodes == set(PREDICTION_ONLY_KINDS), (
        f"予測だけの語彙は PREDICTION_ONLY_KINDS に明示する（差分: {sorted(predicted - nodes)}）"
    )


def test_予測モデルは全キー任意() -> None:
    """「出さない観点はその指標が 0 になるだけ」という約束をモデルでも守る。"""
    from keiyaku.export_models import Prediction

    empty = Prediction.model_validate({})
    assert empty.pages == [] and empty.outline == [] and empty.qa == []
    Prediction.model_validate({"pages": [{"number": 1, "text": "あ"}]})


def test_予測モデルは知らないkindを弾く() -> None:
    """VLM が `subsection` と出して種別正解率 0.0 になった（W5）。黙って 0 にしない。"""
    import pytest as _pytest
    from pydantic import ValidationError

    from keiyaku.export_models import Prediction

    with _pytest.raises(ValidationError):
        Prediction.model_validate({"outline": [{"label": "1", "kind": "subsection"}]})
    Prediction.model_validate({"outline": [{"label": "1", "kind": "chapter"}]})
    Prediction.model_validate({"outline": [{"label": "1", "kind": None}]}), "分からなければ null"


def test_予測の警告は採点を止めない() -> None:
    from keiyaku.cli import _prediction_warnings

    assert _prediction_warnings({"pages": [{"number": 1, "text": "あ"}]}) == []
    problems = _prediction_warnings({"outline": [{"label": "1", "kind": "subsection"}]})
    assert problems and any("kind" in p for p in problems)
    assert any("docs/evaluation.md" in p for p in problems), "直し方の案内を添える"


def test_図のエッジはfromとtoで書ける() -> None:
    """`from` は Python の予約語。予測 JSON では `from` のまま書けること。"""
    from keiyaku.export_models import PredictionFigure

    figure = PredictionFigure.model_validate(
        {
            "caption_label": "図1",
            "nodes": [{"id": "a", "label": "甲"}, {"id": "b", "label": "乙"}],
            "edges": [{"from": "a", "to": "b", "relation": "flow"}],
            "paths": [["甲", "乙"]],
        }
    )
    assert figure.edges[0].from_ == "a"
