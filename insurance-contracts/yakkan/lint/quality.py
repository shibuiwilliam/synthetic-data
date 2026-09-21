"""L10（文体・digit_style）・L11（数値整合）・L12（定義語）・L15（類似度）。"""

from __future__ import annotations

import re
from collections.abc import Iterator

from yakkan.lint.base import Finding, LintContext, rule
from yakkan.lint.walk import iter_texts
from yakkan.richtext import RichTextError, Term, iter_tokens, parse, raw_text

#: 敬体・常体の文末形
POLITE = re.compile(r"(ます|ません|です|ましょう)[。、）]")
PLAIN = re.compile(r"(する|とする|できる|ある|ない|よる|する。)。")
#: genre ごとの期待文体
POLITE_SCHEMES = {"nonlife", "life"}
#: 文体判定の最小サンプル
MIN_SENTENCES = 20
#: 逸脱を許す割合
STYLE_TOLERANCE = 0.15

#: 全角・半角の数字
FULLWIDTH_DIGIT = re.compile(r"[０-９]")
HALFWIDTH_DIGIT = re.compile(r"(?<![A-Za-z])[0-9](?![A-Za-z])")
#: 数値らしい表現（L11 の突合対象）
AMOUNT = re.compile(r"[0-9０-９][0-9０-９,，]*\s*(?:万円|円|日|年|か月|ヶ月|％|%|級|倍)")


@rule("L10", "文体（敬体/常体）と digit_style の一貫性")
def l10_style(ctx: LintContext) -> Iterator[Finding]:
    polite = plain = 0
    fullwidth = halfwidth = 0
    for owned in iter_texts(ctx.draft):
        text = _plain_source(owned.text) if owned.rich else owned.text
        polite += len(POLITE.findall(text))
        plain += len(PLAIN.findall(text))
        fullwidth += len(FULLWIDTH_DIGIT.findall(text))
        halfwidth += len(HALFWIDTH_DIGIT.findall(text))

    total = polite + plain
    if total >= MIN_SENTENCES:
        scheme = ctx.draft.meta.numbering_scheme
        if scheme in POLITE_SCHEMES and plain / total > STYLE_TOLERANCE:
            yield Finding(
                "L10",
                "warn",
                f"{scheme} は敬体だが常体の文末が {plain}/{total} 件ある",
                path="文体",
            )
        if scheme == "teikan" and polite / total > STYLE_TOLERANCE:
            yield Finding(
                "L10",
                "warn",
                f"teikan は常体だが敬体の文末が {polite}/{total} 件ある",
                path="文体",
            )

    digits = fullwidth + halfwidth
    if digits >= 10:
        expected = ctx.draft.meta.digit_style
        wrong = halfwidth if expected == "fullwidth" else fullwidth
        if wrong / digits > STYLE_TOLERANCE:
            yield Finding(
                "L10",
                "warn",
                f"digit_style は {expected} だが、逆の数字が {wrong}/{digits} 文字ある",
                path="meta.digit_style",
            )


@rule("L11", "数値整合：同じ意味の数値が文書内でばらついていない")
def l11_constants(ctx: LintContext) -> Iterator[Finding]:
    """`meta.constants` に宣言した値と同じ意味の数値が、素の文字列で書かれていないかを見る。

    宣言された値そのものが本文に直書きされていたら `{const:}` を使うべき箇所。
    """
    declared = {v.strip(): k for k, v in ctx.draft.meta.constants.items() if v.strip()}
    if not declared:
        return
    for owned in iter_texts(ctx.draft):
        if not owned.rich:
            continue
        literal = _plain_source(owned.text)
        for value, key in declared.items():
            if len(value) >= 2 and value in literal:
                yield Finding(
                    "L11",
                    "warn",
                    f"meta.constants['{key}'] と同じ値 {value!r} が直書きされている"
                    f"（{{const:{key}}} を使う）",
                    element_id=owned.owner_id,
                    path=owned.path,
                )


@rule("L12", "定義語：未定義の {term:} が無い／定義した語が使われている")
def l12_terms(ctx: LintContext) -> Iterator[Finding]:
    known = {t.id for t in ctx.draft.defined_terms}
    used: set[str] = set()
    for owned in iter_texts(ctx.draft):
        if not owned.rich:
            continue
        try:
            tokens = parse(owned.text)
        except RichTextError:
            continue
        for token in iter_tokens(tokens):
            if isinstance(token, Term):
                used.add(token.term_id)
                if token.term_id not in known:
                    yield Finding(
                        "L12",
                        "warn",
                        f"{{term:{token.term_id}}} が defined_terms に無い",
                        element_id=owned.owner_id,
                        path=owned.path,
                    )
    for term in ctx.draft.defined_terms:
        if term.id not in used:
            yield Finding(
                "L12",
                "warn",
                f"定義した語が本文で一度も使われていない: {term.id}",
                element_id=term.id,
            )


@rule("L15", "既存 content との文単位の重複が 30% を超えない", quick=False)
def l15_similarity(ctx: LintContext) -> Iterator[Finding]:
    from yakkan.lint.similarity import compare_with_existing

    for other_id, ratio, samples in compare_with_existing(ctx.draft):
        yield Finding(
            "L15",
            "warn",
            f"{other_id} と文単位で {ratio:.0%} 重複している（30% 超）",
            path=" / ".join(s[:24] for s in samples[:2]),
        )


def _plain_source(text: str) -> str:
    """トークンを除いた地の文（`{const:}` などの記号を数えないため）。"""
    try:
        return raw_text(parse(text))
    except RichTextError:
        return text
