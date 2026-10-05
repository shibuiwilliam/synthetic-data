"""dataset/manifest.json の生成（CLAUDE.md §1.2 / §11）。

    uv run keiyaku manifest update

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

from keiyaku.models import Model

DATASET_DIR = Path("dataset")
MANIFEST_NAME = "manifest.json"
#: manifest に載せるファイルとチェックサムの対象
CHECKSUM_FILES = ("source.json", "layout.json", "answer.json", "doc.pdf", "qa.json")
#: 1 文書ぶんの成果物（manifest に一覧を載せる。docs/eval_dataset_plan.md P9）
ARTIFACT_FILES = (
    "doc.pdf",
    "source.json",
    "layout.json",
    "answer.json",
    "qa.json",
    "elements.jsonl",
    "passages.jsonl",
    "render.html",
)


class DocumentEntry(Model):
    doc_id: str
    content_id: str
    doctype: str
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
    #: この文書のディレクトリにある成果物（相対パス）。利用者が何を読めばよいか分かるようにする
    artifacts: list[str] = Field(default_factory=list)
    #: ページ画像の枚数
    page_images: int = 0
    errors: list[str] = Field(default_factory=list)


class Manifest(Model):
    schema_version: Literal["1.0"] = "1.0"
    #: コーパス全体の成果物（検索評価セット）。docs/evaluation.md §2
    corpus_artifacts: list[str] = Field(default_factory=list)
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
        from keiyaku.verify.checks import verify_dataset

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
        doctype=source["doctype"],
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
        artifacts=[name for name in ARTIFACT_FILES if (doc_dir / name).is_file()],
        page_images=len(list((doc_dir / "pages").glob("*.png"))) if (doc_dir / "pages").is_dir() else 0,
        errors=errors[:5],
    )


def build(dataset_dir: Path | None = None, *, verify: bool = True) -> tuple[Manifest, Path]:
    """`dataset/` を走査して一覧を組み立てる（**書き出しはしない**）。"""
    base = dataset_dir or DATASET_DIR
    base.mkdir(parents=True, exist_ok=True)
    entries = []
    for doc_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        entry = scan_document(doc_dir, verify=verify)
        if entry is not None:
            entries.append(entry)
    corpus = [
        f"search/{name}"
        for name in ("passages.jsonl", "queries.jsonl", "qrels.jsonl")
        if (base / "search" / name).is_file()
    ]
    return Manifest(corpus_artifacts=corpus, documents=entries), base / MANIFEST_NAME


def update(dataset_dir: Path | None = None, *, verify: bool = True) -> ScanResult:
    manifest, path = build(dataset_dir, verify=verify)
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return ScanResult(manifest=manifest, path=path)


def check(dataset_dir: Path | None = None, *, verify: bool = True) -> list[str]:
    """`manifest.json` が実ファイルと合っているかを見る（書き換えない）。

    生成し直したあと `manifest update` を忘れると、`checksums` と `qa_items` が
    古いまま残る。配布物は manifest を目次として読まれるので、黙って陳腐化させない
    （docs/remaining_issues.md S8）。**実際に 19 件の checksum 差分を見つけた。**

    食い違いの説明を返す。空なら一致している。
    """
    fresh, path = build(dataset_dir, verify=verify)
    if not path.is_file():
        return [f"{path} が無い（`keiyaku manifest update` を実行する）"]
    try:
        stored = Manifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError, ValueError) as error:
        return [f"{path} が読めない: {error}"]

    problems: list[str] = []
    if stored.corpus_artifacts != fresh.corpus_artifacts:
        problems.append(f"corpus_artifacts が違う: {stored.corpus_artifacts} → {fresh.corpus_artifacts}")
    stored_by_id = {d.doc_id: d for d in stored.documents}
    fresh_by_id = {d.doc_id: d for d in fresh.documents}
    for doc_id in sorted(set(fresh_by_id) - set(stored_by_id)):
        problems.append(f"{doc_id}: manifest に無い")
    for doc_id in sorted(set(stored_by_id) - set(fresh_by_id)):
        problems.append(f"{doc_id}: manifest にあるが dataset に無い")
    for doc_id in sorted(set(stored_by_id) & set(fresh_by_id)):
        old_entry, new_entry = stored_by_id[doc_id], fresh_by_id[doc_id]
        fields = [
            ("pages", old_entry.pages, new_entry.pages),
            ("qa_items", old_entry.qa_items, new_entry.qa_items),
            ("artifacts", old_entry.artifacts, new_entry.artifacts),
            ("page_images", old_entry.page_images, new_entry.page_images),
        ]
        # verify を省くと status は必ず unverified になるので、比べても意味がない
        if verify:
            fields.append(("status", old_entry.status, new_entry.status))
        for name, was, now in fields:
            if was != now:
                problems.append(f"{doc_id}: {name} が古い（{was} → {now}）")
        for name in sorted(set(old_entry.checksums) | set(new_entry.checksums)):
            if old_entry.checksums.get(name) != new_entry.checksums.get(name):
                problems.append(f"{doc_id}: {name} の checksum が古い")
    return problems
