"""dataset/manifest.json の生成（CLAUDE.md §1.2 / §11）。

    uv run yakkan manifest update

`dataset/<doc_id>/` を走査し、doc_id・ジャンル・スタイル・ページ数・seed・チェックサム・
status（ready / failed）を一覧にする。**status は verify の結果から決める**（自己申告しない）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field

from yakkan.models import Model

DATASET_DIR = Path("dataset")
MANIFEST_NAME = "manifest.json"
#: manifest に載せるファイルとチェックサムの対象
CHECKSUM_FILES = ("source.json", "layout.json", "doc.pdf", "qa.json")


class DocumentEntry(Model):
    doc_id: str
    content_id: str
    genre: str
    style_id: str
    seed: int
    pages: int
    status: Literal["ready", "failed", "unverified"]
    chars: int = 0
    tables: int = 0
    figures: int = 0
    footnotes: int = 0
    refs: int = 0
    qa_items: int = 0
    checksums: dict[str, str] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class Manifest(Model):
    schema_version: Literal["1.0"] = "1.0"
    documents: list[DocumentEntry] = Field(default_factory=list)

    @property
    def ready(self) -> int:
        return sum(1 for d in self.documents if d.status == "ready")


@dataclass
class ScanResult:
    manifest: Manifest
    path: Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scan_document(doc_dir: Path, *, verify: bool = True) -> DocumentEntry | None:
    """1 文書ぶんの情報を集める。source.json と layout.json が無ければ対象外。"""
    source_path = doc_dir / "source.json"
    layout_path = doc_dir / "layout.json"
    if not source_path.is_file() or not layout_path.is_file():
        return None

    source = json.loads(source_path.read_text(encoding="utf-8"))
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    derived = source.get("derived", {})

    errors: list[str] = []
    status: Literal["ready", "failed", "unverified"] = "unverified"
    if verify:
        from yakkan.verify.checks import verify_dataset

        try:
            results = verify_dataset(doc_dir)
            errors = [r.format() for r in results if r.severity == "error"]
            status = "failed" if errors else "ready"
        except Exception as exc:  # noqa: BLE001 - 検証自体が落ちたら failed として残す
            errors = [f"verify が例外で落ちた: {type(exc).__name__}: {exc}"]
            status = "failed"

    qa_path = doc_dir / "qa.json"
    qa_items = 0
    if qa_path.is_file():
        qa_items = len(json.loads(qa_path.read_text(encoding="utf-8")).get("items", []))

    return DocumentEntry(
        doc_id=layout["doc_id"],
        content_id=source["content_id"],
        genre=source["genre"],
        style_id=layout["style_id"],
        seed=source["seed"],
        pages=layout["page_count"],
        status=status,
        chars=sum(len(v.get("without_label", "")) for v in derived.get("plain_text", {}).values()),
        tables=len(derived.get("tables", {})),
        figures=len(derived.get("figures", {})),
        footnotes=len(derived.get("footnote_index", [])),
        refs=len(derived.get("refs", [])),
        qa_items=qa_items,
        checksums={name: sha256(doc_dir / name) for name in CHECKSUM_FILES if (doc_dir / name).is_file()},
        errors=errors[:5],
    )


def update(dataset_dir: Path | None = None, *, verify: bool = True) -> ScanResult:
    base = dataset_dir or DATASET_DIR
    base.mkdir(parents=True, exist_ok=True)
    entries = []
    for doc_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        entry = scan_document(doc_dir, verify=verify)
        if entry is not None:
            entries.append(entry)
    manifest = Manifest(documents=entries)
    path = base / MANIFEST_NAME
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return ScanResult(manifest=manifest, path=path)
