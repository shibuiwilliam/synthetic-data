"""L10（文体・digit_style）・L11（数値整合）・L12（定義語）・L15（類似度）。"""

from __future__ import annotations

import re
from collections.abc import Iterator

from keiyaku.lint.base import Finding, LintContext, rule
from keiyaku.lint.walk import iter_blocks, iter_texts
from keiyaku.models import BoxBlock
from keiyaku.richtext import RichTextError, Term, iter_tokens, parse, raw_text

#: 敬体・常体の文末形
POLITE = re.compile(r"(ます|ません|です|ましょう)[。、）]")
PLAIN = re.compile(r"(する|とする|できる|ある|ない|よる|する。)。")
#: 期待文体。**契約書は全 doctype 常体**（CLAUDE.md §4、docs/style_guide.md §3）。
#: 様式型（`employment`）は体言止め・名詞句が主体で文末形が拾いにくいので、
#: 判定に使う文の下限（MIN_SENTENCES）で自然に外れる。
#: 敬体を期待する doctype が将来できたら、blueprint の `tone` を見る形に変える。
PLAIN_IS_EXPECTED = True
#: 文体判定の最小サンプル
MIN_SENTENCES = 20
#: 逸脱を許す割合
STYLE_TOLERANCE = 0.15

#: 全角・半角の数字
FULLWIDTH_DIGIT = re.compile(r"[０-９]")
HALFWIDTH_DIGIT = re.compile(r"(?<![A-Za-z])[0-9](?![A-Za-z])")
#: 定数の直書きを探すとき、**日付の一部を期間と取り違えない**ための境界。
#: 「２０２７年６月２１日」の「２１日」は期間の「２１日」ではない。
#: 直前が「年」「月」なら日付の構成要素とみなす（2026-09-27：`lic-0001` で
#: 「９月３０日」が定数の「３０日」と衝突した）。
_DATE_PREFIX = ("年", "月")


#: 文体の判定から外す場所（docs/style_guide.md §3）。
#: 依頼形・敬体を使ってよいのは**欄外注・前付け・奥付の定型文**だけなので、そこは数えない。
#: `digit_style` の検査は全文を対象にする（全角半角の混在はどこで起きても困る）。
_TONE_EXEMPT_PREFIXES = ("front_matter.", "back_matter.")

#: `digit_style` の検査から外す meta（ISO 形式の日付。描画時に整形される）
_DIGIT_EXEMPT_PATHS = frozenset({"meta.contract_date", "meta.effective_date"})


def _tone_exempt(owned, box_ids: frozenset[str]) -> bool:
    path = owned.path or ""
    if path.startswith(_TONE_EXEMPT_PREFIXES):
        return True
    return path.split(".", 1)[0] in box_ids


@rule("L10", "文体（敬体/常体）と digit_style の一貫性")
def l10_style(ctx: LintContext) -> Iterator[Finding]:
    polite = plain = 0
    fullwidth = halfwidth = 0
    box_ids = frozenset(b.id for b, _owner, _article in iter_blocks(ctx.draft) if isinstance(b, BoxBlock))
    for owned in iter_texts(ctx.draft):
        text = _plain_source(owned.text) if owned.rich else owned.text
        # ISO 形式の日付（`meta.contract_date` 等）は**入力の形**であり紙面の表記ではない。
        # 描画時に `digit_style` に従って「２０２６年４月１日」に整形されるので、数えない。
        if (owned.path or "") not in _DIGIT_EXEMPT_PATHS:
            fullwidth += len(FULLWIDTH_DIGIT.findall(text))
            halfwidth += len(HALFWIDTH_DIGIT.findall(text))
        if _tone_exempt(owned, box_ids):
            continue
        polite += len(POLITE.findall(text))
        plain += len(PLAIN.findall(text))

    total = polite + plain
    if total >= MIN_SENTENCES and PLAIN_IS_EXPECTED and polite / total > STYLE_TOLERANCE:
        yield Finding(
            "L10",
            "warn",
            f"契約書は常体で書くが、敬体の文末が {polite}/{total} 件ある"
            "（依頼形・敬体を使えるのは欄外注と前付けだけ。docs/style_guide.md §3）",
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
            if len(value) >= 2 and _written_literally(literal, value):
                yield Finding(
                    "L11",
                    "warn",
                    f"meta.constants['{key}'] と同じ値 {value!r} が直書きされている"
                    f"（{{const:{key}}} を使う）",
                    element_id=owned.owner_id,
                    path=owned.path,
                )


def _written_literally(text: str, value: str) -> bool:
    """`value` が `text` に**それ自体として**書かれているか。

    日付の一部（「９月３０日」の中の「３０日」）は期間の直書きではないので数えない。
    """
    start = 0
    while True:
        at = text.find(value, start)
        if at < 0:
            return False
        if at == 0 or text[at - 1] not in _DATE_PREFIX:
            return True
        start = at + 1


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

    yield from _definitions_on_paper(ctx)


#: 定義文が紙面に載っているとみなす一致の下限（語尾の「〜をいう。」の差を吸収する）
_DEFINITION_MATCH = 0.7


def _definitions_on_paper(ctx: LintContext) -> Iterator[Finding]:
    """`defined_terms` の定義文が**紙面のどこにも現れない**語を拾う。

    `{term:}` は語を強調するだけで、定義の文そのものは描画されない。
    定義条も定義表も置かないと、**読み手には語の意味が分からない**まま
    `definition` の QA も作れない（2026-09-26 の nda-0001、2026-09-27 の ots-0001 で 2 度踏んだ）。
    定義条（散文）でも定義表でもよいので、定義の実質が本文にあることだけを見る。
    """
    # `defined_terms` の text は `owner_id` が語の id になる（path は "<id>.definition"）。
    # **定義文そのものを照合対象に入れると必ず一致してしまう**ので、語の id で外す。
    term_ids = {t.id for t in ctx.draft.defined_terms}
    body: list[str] = []
    for owned in iter_texts(ctx.draft):
        if owned.owner_id in term_ids:
            continue
        body.append(_plain_source(owned.text) if owned.rich else owned.text)
    haystack = "".join(body)
    for term in ctx.draft.defined_terms:
        core = _definition_core(_plain_source(term.definition))
        if core and core not in haystack:
            yield Finding(
                "L12",
                "warn",
                f"定義語 {term.id} の定義文が紙面に現れない"
                "（定義条か定義表を置く。置かないと読み手に語の意味が伝わらない）",
                element_id=term.id,
            )


def _definition_core(definition: str) -> str:
    """定義文から、言い回しの差が出にくい中核部分を取り出す。

    末尾の「〜をいう。」「〜とする。」は条文に組み込むときに変わるので落とし、
    残りの前方 `_DEFINITION_MATCH` を照合に使う。**トークンは両側で解いてから**渡すこと
    （定義文も本文も `{party:}` `{term:}` を含むので、生の文字列どうしでは一致しない）。
    """
    core = re.sub(r"(をいう|とする|をいい.*)。?$", "", definition.strip().rstrip("。"))
    if len(core) < 10:
        return ""
    return core[: max(10, int(len(core) * _DEFINITION_MATCH))]


@rule("L15", "既存 content との文単位の重複が 30% を超えない", quick=False)
def l15_similarity(ctx: LintContext) -> Iterator[Finding]:
    from keiyaku.lint.similarity import compare_with_existing

    for other_id, ratio, samples in compare_with_existing(ctx.draft):
        yield Finding(
            "L15",
            "warn",
            f"{other_id} と文単位で {ratio:.0%} 重複している（30% 超）",
            path=" / ".join(s[:24] for s in samples[:2]),
        )


#: 本文に紛れ込みやすい Markdown の記法。RichText の強調は `{b:}` `{u:}` だけ
_MARKDOWN_RESIDUE = (
    ("**", "太字は {b:…} で書く"),
    ("__", "下線は {u:…} で書く"),
    ("`", "等幅の記法は使わない"),
)


@rule("L25", "本文に Markdown の名残（** __ `）が無い")
def l25_markdown_residue(ctx: LintContext) -> Iterator[Finding]:
    """`**強調**` のような Markdown 記法は**そのまま紙面に印字される**。

    RichText の強調は `{b:}` `{u:}` だけで、`**` は素通りする。lint も verify も
    文字として正しいので通してしまい、**PNG を見るまで気づけなかった**
    （2026-10-02：`sys-0002` の第3条第2項に `**みなし承諾の定めは置かない。**` が出ていた）。
    """
    for owned in iter_texts(ctx.draft):
        if not owned.rich:
            continue
        for token, hint in _MARKDOWN_RESIDUE:
            if token in owned.text:
                yield Finding(
                    "L25",
                    "error",
                    f"Markdown の記法 '{token}' が本文に残っている（{hint}）",
                    element_id=owned.owner_id,
                )


def _plain_source(text: str) -> str:
    """トークンを除いた地の文（`{const:}` などの記号を数えないため）。"""
    try:
        return raw_text(parse(text))
    except RichTextError:
        return text
