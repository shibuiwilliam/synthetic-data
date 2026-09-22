"""lint の入口（`yakkan lint content/<cid>`）。"""

from __future__ import annotations

from pathlib import Path

from yakkan.compose import load_draft_or_errors
from yakkan.lint import qa_authored as _qa_authored  # noqa: F401

# ルール登録の副作用のために読み込む
from yakkan.lint import quality as _quality  # noqa: F401
from yakkan.lint import rules as _rules  # noqa: F401
from yakkan.lint import structure as _structure  # noqa: F401
from yakkan.lint.base import Finding, LintContext, run_rules
from yakkan.models import SourceDraft


def lint_draft(
    draft: SourceDraft,
    *,
    quick: bool = False,
    only: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[Finding]:
    """読み込み済みの執筆物を検査する（`content_dir` を伴わないので L16 は動かない）。"""
    findings = run_rules(LintContext(draft=draft, quick=quick), only=only)
    return _filter(findings, exclude)


def lint_content(
    content_dir: Path,
    *,
    quick: bool = False,
    only: list[str] | None = None,
    exclude: list[str] | None = None,
) -> list[Finding]:
    """content ディレクトリを読み込んで検査する。読み込みに失敗したら L00 だけを返す。

    `exclude` は文書全体を対象にする規則（L04 の必須要素、L09 のページ数、L15 の類似度）を
    外したいときに使う。抜粋やテスト用の断片を検査する場合に必要になる。
    """
    draft, errors = load_draft_or_errors(content_dir)
    if draft is None:
        empty = LintContext(draft=None, quick=quick, schema_errors=errors)  # type: ignore[arg-type]
        return run_rules(empty, only=["L00"])
    findings = run_rules(LintContext(draft=draft, quick=quick, content_dir=content_dir), only=only)
    return _filter(findings, exclude)


def _filter(findings: list[Finding], exclude: list[str] | None) -> list[Finding]:
    if not exclude:
        return findings
    skip = set(exclude)
    return [f for f in findings if f.code not in skip]


def summarize(findings: list[Finding]) -> tuple[int, int]:
    """(error 件数, warn 件数)。"""
    errors = sum(1 for f in findings if f.severity == "error")
    return errors, len(findings) - errors
