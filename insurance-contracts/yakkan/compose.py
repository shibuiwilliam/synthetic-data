"""`content/<content_id>/` の読み書き（docs/schema.md §5.11）。

執筆は 1 文書を複数ファイルに割って進める（CLAUDE.md §7.2）。

    content/<content_id>/
      doc.json            # meta・front_matter・back_matter・part の並び
      parts/00_front.json # { "target": "...", ... } 断片
      parts/10_terms.json
      source.json         # build の出力（このモジュールは読まない）

`doc.json` の `parts` に書いた順で読み込み、`target` ごとに連結して `SourceDraft` を組む。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from yakkan.models import SourceDraft

#: part ファイルが書き込める先
PART_TARGETS = ("body", "appendices", "defined_terms", "preface", "colophon", "contact")

#: `_` 始まりのキーは scaffold が埋めた執筆メモ（`_todo`）。モデルへ渡す前に落とす
META_PREFIX = "_"

DOC_FILENAME = "doc.json"
PARTS_DIRNAME = "parts"


class ComposeError(ValueError):
    """content ディレクトリの構造エラー。"""

    def __init__(self, message: str, path: Path) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path


def _load_json(path: Path) -> Any:
    if not path.is_file():
        raise ComposeError("ファイルが無い", path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ComposeError(f"JSON として読めない: {exc}", path) from exc


def strip_notes(value: Any) -> Any:
    """`_todo` のような執筆メモを再帰的に取り除く（SourceDraft は未知フィールドを許さない）。"""
    if isinstance(value, dict):
        return {k: strip_notes(v) for k, v in value.items() if not k.startswith(META_PREFIX)}
    if isinstance(value, list):
        return [strip_notes(v) for v in value]
    return value


def count_todos(value: Any) -> int:
    """残っている執筆メモの数（lint が「未執筆」を報告するのに使う）。"""
    if isinstance(value, dict):
        return sum((1 if k.startswith(META_PREFIX) else 0) + count_todos(v) for k, v in value.items())
    if isinstance(value, list):
        return sum(count_todos(v) for v in value)
    return 0


def compose_dict(content_dir: Path) -> dict[str, Any]:
    """`doc.json` と `parts/*.json` を 1 つの dict にまとめる（検証はしない）。"""
    doc_path = content_dir / DOC_FILENAME
    doc = _load_json(doc_path)
    if not isinstance(doc, dict):
        raise ComposeError("doc.json はオブジェクトであること", doc_path)

    part_names = doc.pop("parts", [])
    if not isinstance(part_names, list):
        raise ComposeError("doc.json の parts は配列であること", doc_path)

    merged: dict[str, Any] = strip_notes(doc)
    merged.setdefault("body", [])
    merged.setdefault("appendices", [])
    merged.setdefault("defined_terms", [])

    for name in part_names:
        part_path = content_dir / PARTS_DIRNAME / name
        part = _load_json(part_path)
        if not isinstance(part, dict):
            raise ComposeError("part はオブジェクトであること", part_path)
        target = part.get("target")
        if target not in PART_TARGETS:
            raise ComposeError(f"target は {PART_TARGETS} のいずれか（指定: {target!r}）", part_path)
        part = strip_notes(part)
        items = part.get("items")
        if not isinstance(items, list):
            raise ComposeError("part の items は配列であること", part_path)
        match target:
            case "body" | "appendices" | "defined_terms":
                merged[target].extend(items)
            case "preface":
                merged.setdefault("front_matter", {}).setdefault("preface", []).extend(items)
            case "colophon" | "contact":
                merged.setdefault("back_matter", {}).setdefault(target, []).extend(items)
    return merged


def raw_document(content_dir: Path) -> dict[str, Any]:
    """執筆メモを落とす前の生データ（TODO の数を数えるのに使う）。"""
    doc = _load_json(content_dir / DOC_FILENAME)
    parts = [_load_json(content_dir / PARTS_DIRNAME / n) for n in doc.get("parts", [])]
    return {"doc": doc, "parts": parts}


def load_draft(content_dir: Path) -> SourceDraft:
    """content ディレクトリを `SourceDraft` として読む。`derived` があれば検証エラー。"""
    return SourceDraft.model_validate(compose_dict(content_dir))


def load_draft_or_errors(content_dir: Path) -> tuple[SourceDraft | None, list[str]]:
    """lint 用。検証に失敗しても例外を投げず、メッセージの一覧を返す。"""
    try:
        data = compose_dict(content_dir)
    except ComposeError as exc:
        return None, [str(exc)]
    try:
        return SourceDraft.model_validate(data), []
    except ValidationError as exc:
        messages: list[str] = []
        for error in exc.errors():
            location = ".".join(str(p) for p in error["loc"])
            messages.append(f"{location}: {error['msg']}")
        return None, messages
