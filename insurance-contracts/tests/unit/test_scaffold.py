"""scaffold と compose の接続（CLAUDE.md §7.2）。"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from yakkan.blueprints import available_genres
from yakkan.compose import count_todos, load_draft, raw_document
from yakkan.scaffold import TODO_KEY, scaffold

GENRES = available_genres()


@pytest.fixture(params=GENRES)
def built(request, tmp_path: Path):
    genre = request.param
    result = scaffold(genre, f"{genre}-test", seed=7, root=tmp_path)
    return genre, result


def test_7ジャンルすべてscaffoldできる(built) -> None:
    genre, result = built
    assert result.content_dir.is_dir()
    assert (result.content_dir / "doc.json").is_file()
    assert result.todo_count > 0, "埋める箇所が 0 件では執筆指示にならない"


def test_composeで読み込める(built) -> None:
    """`_todo` を落として SourceDraft として妥当であること。"""
    _genre, result = built
    draft = load_draft(result.content_dir)
    assert draft.body, "body が空"
    assert draft.meta.numbering_scheme in ("nonlife", "life", "teikan", "group", "jyusetsu")


def test_TODOが残っていることを数えられる(built) -> None:
    _genre, result = built
    raw = raw_document(result.content_dir)
    assert count_todos(raw) > 0


def test_番号ラベルの直書きが無い(built) -> None:
    """scaffold が入れる定型条にも番号ラベルがあってはいけない。"""
    _genre, result = built
    literal = re.compile(r"第[0-9０-９]+[条章節項号]")
    for path in (result.content_dir / "parts").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for match in literal.finditer(json.dumps(data, ensure_ascii=False)):
            pytest.fail(f"{path.name} に番号ラベル: {match.group()}")


def test_定型条の参照が解決済み(built) -> None:
    """`{ref:$pN}` のプレースホルダが残っていないこと。"""
    _genre, result = built
    for path in (result.content_dir / "parts").glob("*.json"):
        assert "$p" not in path.read_text(encoding="utf-8"), f"{path.name} に $pN が残っている"


def test_定型条の定数と用語が枠として入っている(built) -> None:
    genre, result = built
    draft = load_draft(result.content_dir)
    text = json.dumps([n.model_dump(mode="json") for n in draft.body], ensure_ascii=False)
    for key in re.findall(r"\{const:([a-z_]+)\}", text):
        assert key in draft.meta.constants, f"{genre}: {key} が meta.constants に無い"
    for term_id in re.findall(r"\{term:([a-z_]+)\}", text):
        assert term_id in {t.id for t in draft.defined_terms}, f"{genre}: {term_id} の枠が無い"


def test_seedが同じなら同じ結果になる(tmp_path: Path) -> None:
    a = scaffold("auto", "auto-a", seed=3, root=tmp_path / "a")
    b = scaffold("auto", "auto-b", seed=3, root=tmp_path / "b")
    # content_id だけが違うはずなので、それを揃えて比べる
    doc_a = json.dumps(a.doc, ensure_ascii=False).replace("auto-a", "X")
    doc_b = json.dumps(b.doc, ensure_ascii=False).replace("auto-b", "X")
    assert doc_a == doc_b
    assert a.parts.keys() == b.parts.keys()
    for name in a.parts:
        assert json.dumps(a.parts[name], ensure_ascii=False) == json.dumps(b.parts[name], ensure_ascii=False)


def test_seedが違えば選択が変わる(tmp_path: Path) -> None:
    docs = {
        seed: json.dumps(
            scaffold("auto", "auto-x", seed=seed, root=tmp_path / str(seed)).parts, ensure_ascii=False
        )
        for seed in (1, 2, 3, 4, 5)
    }
    assert len(set(docs.values())) > 1, "seed を変えても中身が変わらない"


def test_TODOキーはアンダースコア始まり() -> None:
    assert TODO_KEY.startswith("_"), "compose が落とせるよう _ 始まりにする"
