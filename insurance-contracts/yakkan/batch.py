"""バッチ生成（CLAUDE.md §11・§12 P5）。

`specs/*.yaml` に並べた content を、1 本ずつ

    lint → build → render（style ごと）→ verify → qa

の順に通す。**失敗しても止まらず次へ進み、最後に原因別に集計する**。
どの段で落ちたかと例外の要旨を残すので、原因の切り分けに使える。

`scaffold` はここでは呼ばない。骨組みだけの content を描いても意味が無く、
執筆が済んでいるかは `lint`（L04 の必須要素・TODO の残り）が判断するため。
"""

from __future__ import annotations

import traceback
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

#: どの段で落ちたか
Stage = Literal["missing", "lint", "build", "render", "verify", "qa"]


@dataclass
class DocResult:
    content_id: str
    genre: str
    style_id: str
    status: Literal["ready", "failed", "skipped"]
    stage: Stage | None = None
    pages: int = 0
    qa_count: int = 0
    reason: str = ""


@dataclass
class BatchResult:
    name: str
    results: list[DocResult] = field(default_factory=list)

    @property
    def ready(self) -> list[DocResult]:
        return [r for r in self.results if r.status == "ready"]

    @property
    def failed(self) -> list[DocResult]:
        return [r for r in self.results if r.status == "failed"]

    def by_stage(self) -> Counter[str]:
        """失敗を段ごとに数える。"""
        return Counter(r.stage or "?" for r in self.failed)

    def by_reason(self) -> Counter[str]:
        """失敗を原因の要旨ごとに数える。"""
        return Counter(_reason_key(r.reason) for r in self.failed)


def _reason_key(reason: str) -> str:
    """原因を集計しやすい短い鍵にまとめる。"""
    if not reason:
        return "（理由なし）"
    for needle, key in (
        ("AssertionError", "WeasyPrint のレイアウト破綻（AssertionError）"),
        ("IndexError", "WeasyPrint のレイアウト破綻（IndexError）"),
        ("欠落", "描画時の内容欠落"),
        ("ページ数", "ページ数が上限超過"),
        ("TODO", "執筆が未完（TODO 残り）"),
        ("必須要素", "blueprint の必須要素を満たさない"),
    ):
        if needle in reason:
            return key
    return reason.splitlines()[0][:60]


def load_spec(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "documents" not in data:
        raise ValueError(f"{path}: documents が無い")
    return data


def _styles_for(entry: dict[str, Any]) -> list[str]:
    explicit = entry.get("styles")
    if explicit:
        return list(explicit)
    from yakkan.blueprints import load_blueprint

    blueprint = load_blueprint(entry["genre"])
    return [blueprint.default_style]


def run(
    spec_path: Path,
    *,
    content_root: Path = Path("content"),
    dataset_root: Path = Path("dataset"),
    only: str | None = None,
) -> BatchResult:
    """spec を回す。`only` を渡すとその content_id だけ処理する。"""
    from yakkan.answer import build_answer
    from yakkan.build import build_content
    from yakkan.compose import count_todos, raw_document
    from yakkan.lint.runner import lint_content
    from yakkan.models import Layout, QASet, Source, dump_json
    from yakkan.qa.auto import generate as generate_qa
    from yakkan.qa.validate import validate as validate_qa
    from yakkan.render.weasy import render_source
    from yakkan.styles import load_style
    from yakkan.verify.checks import verify_dataset

    spec = load_spec(spec_path)
    defaults = spec.get("defaults") or {}
    qa_count = int(defaults.get("qa_count", 30))
    qa_seed = int(defaults.get("qa_seed", 0))
    result = BatchResult(name=str(spec.get("name") or spec_path.stem))

    for entry in spec["documents"]:
        content_id = entry["content_id"]
        genre = entry["genre"]
        if only and content_id != only:
            continue
        content_dir = content_root / content_id
        styles = _styles_for(entry)

        if not (content_dir / "doc.json").exists():
            result.results.append(
                DocResult(content_id, genre, styles[0], "skipped", "missing", reason="content が無い")
            )
            continue

        # --- lint ---
        try:
            todos = count_todos(raw_document(content_dir))
            if todos:
                raise RuntimeError(f"執筆が未完：TODO が {todos} 件残っている")
            findings = lint_content(content_dir)
            errors = [f for f in findings if f.severity == "error"]
            if errors:
                raise RuntimeError("lint error: " + "; ".join(str(f) for f in errors[:3]))
        except Exception as error:  # noqa: BLE001 — 落ちても次の content へ進む
            result.results.append(
                DocResult(content_id, genre, styles[0], "failed", "lint", reason=_brief(error))
            )
            continue

        # --- build ---
        try:
            source = build_content(content_dir)
        except Exception as error:  # noqa: BLE001
            result.results.append(
                DocResult(content_id, genre, styles[0], "failed", "build", reason=_brief(error))
            )
            continue

        for style_id in styles:
            out_dir = dataset_root / f"{content_id}--{style_id}"
            # --- render ---
            try:
                style = load_style(style_id)
                render = render_source(source, style, out_dir)
            except Exception as error:  # noqa: BLE001
                result.results.append(
                    DocResult(content_id, genre, style_id, "failed", "render", reason=_brief(error))
                )
                continue

            # --- verify ---
            try:
                checks = verify_dataset(out_dir)
                bad = [c for c in checks if c.severity == "error"]
                if bad:
                    raise RuntimeError("verify error: " + "; ".join(str(c) for c in bad[:3]))
            except Exception as error:  # noqa: BLE001
                result.results.append(
                    DocResult(
                        content_id,
                        genre,
                        style_id,
                        "failed",
                        "verify",
                        pages=render.layout.page_count,
                        reason=_brief(error),
                    )
                )
                continue

            # --- qa ---
            try:
                layout = Layout.model_validate_json((out_dir / "layout.json").read_text(encoding="utf-8"))
                stored = Source.model_validate_json((out_dir / "source.json").read_text(encoding="utf-8"))
                answer = build_answer(stored, layout)
                dump_json(answer, out_dir / "answer.json")
                qa_path = out_dir / "qa.json"
                from yakkan.cli import _load_authored, _localize_authored

                authored = _localize_authored(_load_authored(content_id, qa_path, content_root), answer)
                generated = generate_qa(answer, count=qa_count, seed=qa_seed)
                qa_set = QASet(doc_id=answer.doc_id, items=generated.items + authored)
                dump_json(qa_set, qa_path)
                qa_errors = [f for f in validate_qa(qa_set, answer) if f.severity == "error"]
                if qa_errors:
                    raise RuntimeError("QA error: " + "; ".join(str(f) for f in qa_errors[:3]))
                # 評価向けの派生成果物（docs/eval_dataset_plan.md P5）。
                # 検索評価セットはコーパス全体で作るので `yakkan export` 側で組む。
                from yakkan.export import export_dataset

                export_dataset(out_dir)
            except Exception as error:  # noqa: BLE001
                result.results.append(
                    DocResult(
                        content_id,
                        genre,
                        style_id,
                        "failed",
                        "qa",
                        pages=render.layout.page_count,
                        reason=_brief(error),
                    )
                )
                continue

            result.results.append(
                DocResult(
                    content_id,
                    genre,
                    style_id,
                    "ready",
                    pages=render.layout.page_count,
                    qa_count=len(qa_set.items),
                )
            )
    return result


def _brief(error: Exception) -> str:
    """例外の要旨（1〜2 行）。長いスタックは残さない。"""
    text = str(error).strip()
    if not text:
        text = traceback.format_exception_only(type(error), error)[-1].strip()
    lines = [line for line in text.splitlines() if line.strip()]
    return " / ".join(lines[:2])[:300]
