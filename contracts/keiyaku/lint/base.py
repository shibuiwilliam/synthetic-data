"""lint の基盤：検査結果の型とルール登録（CLAUDE.md §8）。

- ルールは `@rule("L01", "...")` で登録する純関数。`LintContext` を受け取り `Finding` を yield する。
- `--quick`（`quick=True`）では重いルール（フォント被覆など）を飛ばす。
- 重大度は error / warn。error が 1 件でもあれば CLI は非ゼロ終了。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from keiyaku.models import SourceDraft

Severity = Literal["error", "warn"]


@dataclass(frozen=True)
class Finding:
    """1 件の指摘。`element_id` と `path` で場所を示す。"""

    code: str
    severity: Severity
    message: str
    element_id: str | None = None
    path: str | None = None

    def format(self) -> str:
        where = self.element_id or self.path or "-"
        return f"[{self.severity.upper():5}] {self.code} {where}: {self.message}"


@dataclass
class LintContext:
    """ルールが参照する材料。重い派生物は遅延で作る。"""

    draft: SourceDraft
    quick: bool = False
    #: compose / スキーマ検証の失敗メッセージ（draft が無いときに使う）
    schema_errors: list[str] = field(default_factory=list)
    #: content ディレクトリ。`qa_authored.json` のように draft の外にある成果物を見る規則が使う
    content_dir: Path | None = None
    _index: object | None = field(default=None, repr=False)
    _caption_labels: dict[str, str] | None = field(default=None, repr=False)

    @property
    def index(self):
        """`DocumentIndex`（ラベル・参照解決）。初回アクセスで構築する。"""
        if self._index is None:
            from keiyaku.numbering import DocumentIndex, NumberingContext

            ctx = NumberingContext(
                scheme=self.draft.meta.numbering_scheme,
                digit_style=self.draft.meta.digit_style,
                article_heading=self.draft.meta.article_heading,
                footnote_style=self.draft.meta.footnote_style,
            )
            self._index = DocumentIndex(
                ctx, self.draft.body, self.draft.appendices, self.draft.back_matter.signature
            )
        return self._index

    @property
    def caption_labels(self) -> dict[str, str]:
        """build が実際に振る「表１」「図２」。**番号が付く表・図の集合**でもある。

        `caption_numbering: chapter` では章に属さない表・図に番号を振らないので
        （docs/remaining_issues.md S2）、キャプションの有無だけでは
        `{ref:}` の参照先になれるかを判定できない。
        """
        if self._caption_labels is None:
            from keiyaku.build import assign_caption_labels

            self._caption_labels = assign_caption_labels(self.draft, self.index.ctx)
        return self._caption_labels


Rule = Callable[[LintContext], Iterator[Finding]]


@dataclass(frozen=True)
class RegisteredRule:
    code: str
    title: str
    func: Rule
    quick: bool  # --quick でも走らせるか


_RULES: list[RegisteredRule] = []


def rule(code: str, title: str, *, quick: bool = True) -> Callable[[Rule], Rule]:
    """ルールを登録するデコレータ。"""

    def decorator(func: Rule) -> Rule:
        _RULES.append(RegisteredRule(code=code, title=title, func=func, quick=quick))
        return func

    return decorator


def registered_rules() -> list[RegisteredRule]:
    return sorted(_RULES, key=lambda r: r.code)


def run_rules(ctx: LintContext, only: Iterable[str] | None = None) -> list[Finding]:
    """登録済みルールを順に実行する。"""
    wanted = set(only) if only else None
    findings: list[Finding] = []
    for registered in registered_rules():
        if wanted is not None and registered.code not in wanted:
            continue
        if ctx.quick and not registered.quick:
            continue
        findings.extend(registered.func(ctx))
    return findings
