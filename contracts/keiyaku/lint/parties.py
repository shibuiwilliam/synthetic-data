"""L19（当事者整合）・L20（契約書の骨格）・L21（逐条解説）。

契約書に固有の 3 ルール（CLAUDE.md §8、docs/schema.md §9、docs/lint_rules.md）。

**L19 が検出できないこと**：甲乙の**論理の取り違え**（乙が負うべき義務を甲に書いた）。
呼称が揃っていても意味は機械で見られない。reviewer サブエージェントと目視の担当
（`docs/authoring_checklist.md` §5）。
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from keiyaku.lint.base import Finding, LintContext, rule
from keiyaku.lint.walk import document_nodes, iter_blocks, iter_nodes, iter_texts
from keiyaku.models import BoxBlock, CommentaryBlock, PartiesBlock
from keiyaku.richtext import Party, RichTextError, iter_tokens, parse

#: `{party:key|full}` を使ってよい場所（当事者を導入するところ）。
#: 前文・当事者表示以外で使うと、同じ当事者が何度も正式名称で紹介される不自然な文になる。
_FULL_INTRO_KINDS = frozenset({"preamble"})


def _parties(ctx: LintContext) -> dict[str, object]:
    return {p.key: p for p in ctx.draft.meta.parties}


def _party_tokens(ctx: LintContext) -> Iterator[tuple[str, Party]]:
    """文書に現れる `{party:}` を (場所, トークン) で返す。"""
    for owned in iter_texts(ctx.draft):
        if not owned.rich:
            continue
        try:
            nodes = parse(owned.text)
        except RichTextError:
            continue  # 書式の誤りは L00/L03 の担当
        for token in iter_tokens(nodes):
            if isinstance(token, Party):
                yield owned.path or owned.owner_id, token


# --- L19 当事者整合 -----------------------------------------------------------


@rule("L19", "当事者整合（{party:} の存在・呼称と名称の一致・alias の直書き禁止）")
def l19_parties(ctx: LintContext) -> Iterator[Finding]:
    parties = ctx.draft.meta.parties
    known = {p.key for p in parties}

    # 1. key・alias・name が一意（取り違えの温床になる）
    for field_name, values in (
        ("key", [p.key for p in parties]),
        ("alias", [p.alias for p in parties]),
        ("name", [p.name for p in parties]),
    ):
        seen: set[str] = set()
        for value in values:
            if value in seen:
                yield Finding(
                    "L19",
                    "error",
                    f"meta.parties の {field_name} が重複している: {value!r}",
                    path="meta.parties",
                )
            seen.add(value)

    # 2. `{party:}` の key が存在し、modifier に必要な宣言があること
    full_uses: dict[str, int] = {}
    for where, token in _party_tokens(ctx):
        if token.key not in known:
            yield Finding(
                "L19",
                "error",
                f"{{party:{token.key}}} が meta.parties に無い（あるのは {'、'.join(sorted(known))}）",
                path=where,
            )
            continue
        party = next(p for p in parties if p.key == token.key)
        if token.mode == "role" and not party.role_label:
            yield Finding(
                "L19",
                "error",
                f"{{party:{token.key}|role}} だが role_label が宣言されていない",
                path=where,
            )
        if token.mode == "full":
            full_uses[token.key] = full_uses.get(token.key, 0) + 1

    # 3. `|full`（導入形）は 1 当事者につき 1 回。2 回以上は不自然
    for key, count in full_uses.items():
        if count > 1:
            yield Finding(
                "L19",
                "warn",
                f"{{party:{key}|full}} が {count} 回使われている"
                "（正式名称の導入は前文か当事者表示で 1 回。以降は alias で指す）",
                path="meta.parties",
            )

    # 4. parties ブロックの keys が meta.parties の部分集合
    for block, _owner, _article in iter_blocks(ctx.draft):
        if isinstance(block, PartiesBlock):
            for key in block.keys:
                if key not in known:
                    yield Finding(
                        "L19",
                        "error",
                        f"当事者表示が知らない当事者を指している: {key}",
                        element_id=block.id,
                    )

    # 5. alias の直書き（「甲」「乙」を生文字列で書く）
    yield from _direct_alias_writes(ctx)


#: 呼称に隣接すると「熟語の一部」と判断する文字（漢字・英字・数字）。
#: **日本語では語境界（`\b`）が使えない**——`\w` に漢字も仮名も入るので、
#: 「甲は」（正しい直書き）と「甲板」（一般語）を区別できない。
_COMPOUND = r"\u4e00-\u9fff\u3005\u3007A-Za-z0-9"


def _direct_alias_writes(ctx: LintContext) -> Iterator[Finding]:
    """「甲」「乙」の直書きを拾う（docs/lint_rules.md §L19）。

    判定：呼称の**連なり**（「甲」「甲乙」「甲乙丙」）を取り出し、
    - 直前が漢字・英数字なら熟語の一部とみなして無視する（「委託者甲」は拾わない）
    - 連なりが 1 文字で、直後が漢字・英数字なら一般語とみなす（**「甲板」「乙種」を通す**）
    - 連なりが 2 文字以上なら、直後が漢字でも拾う（「甲乙間」は当事者の直書き）

    **拾えないもの**：呼称 1 文字＋漢字の複合（「甲側」「乙宛」）。ここを厳しくすると
    「甲板」「乙種」を誤検出するので、reviewer と目視の担当に回す
    （docs/authoring_checklist.md §5）。
    """
    parties = ctx.draft.meta.parties
    aliases = [p.alias for p in parties if p.alias]
    if not aliases:
        return
    run = re.compile(rf"(?<![{_COMPOUND}])((?:" + "|".join(re.escape(a) for a in aliases) + r")+)")
    trailing = re.compile(rf"[{_COMPOUND}]")
    box_ids = {b.id for b, _o, _a in iter_blocks(ctx.draft) if isinstance(b, BoxBlock)}
    for owned in iter_texts(ctx.draft):
        path = owned.path or ""
        # `meta.*` は当事者の**宣言そのもの**（alias に「甲」と書くのが正しい）。
        # 欄外注・前付け・奥付は当事者を平文で説明することがあるので、いずれも対象外にする。
        if path.startswith(("meta.", "front_matter.", "back_matter.")):
            continue
        if path.split(".", 1)[0] in box_ids:
            continue
        for match in run.finditer(owned.text):
            found = match.group(1)
            after = owned.text[match.end() : match.end() + 1]
            if len(found) == 1 and after and trailing.match(after):
                continue  # 「甲板」「乙種」のような熟語
            yield Finding(
                "L19",
                "error",
                f"当事者の呼称を直書きしている: {found!r}"
                "（{party:<key>} で書く。build が meta.parties から解決する）",
                path=owned.path,
            )


# --- L20 契約書の骨格 ---------------------------------------------------------

#: body の先頭にしか置けない種別と、置ける数
_AT_MOST_ONE_IN_BODY = ("preamble", "head_matter")


def _signature_policy(draft) -> str:
    """blueprint の `signature` 宣言。読めなければ既定（required）。"""
    from keiyaku.blueprints import load_blueprint

    try:
        return load_blueprint(draft.doctype).signature
    except (FileNotFoundError, ValueError):
        return "required"


@rule("L20", "契約書の骨格（前文・頭書・記名押印欄の位置と数）")
def l20_skeleton(ctx: LintContext) -> Iterator[Finding]:
    draft = ctx.draft
    top = draft.body
    kinds = [node.kind for node in top]

    # 1. 前文は body の先頭にちょうど 1 つ（様式型は前文を持たない → 0 も許す）
    if kinds.count("preamble") > 1:
        yield Finding("L20", "error", "preamble が 2 つ以上ある（body の先頭に 1 つ）", path="body")
    if "preamble" in kinds and kinds.index("preamble") != 0:
        yield Finding("L20", "error", "preamble が body の先頭にない", path="body")

    # 2. 頭書は前文の直後にだけ置ける
    if kinds.count("head_matter") > 1:
        yield Finding("L20", "error", "head_matter が 2 つ以上ある", path="body")
    if "head_matter" in kinds:
        want = 1 if "preamble" in kinds else 0
        if kinds.index("head_matter") != want:
            yield Finding(
                "L20",
                "error",
                "head_matter の位置が不正（前文があればその直後、無ければ body の先頭）",
                path="body",
            )

    for kind in _AT_MOST_ONE_IN_BODY:
        for node, ancestors in iter_nodes(draft.body):
            if node.kind == kind and ancestors:
                yield Finding("L20", "error", f"{kind} を入れ子にしている", element_id=node.id)

    # 3. 記名押印欄は back_matter にちょうど 1 つ。
    #    ただし **blueprint が `signature: forbidden` と宣言していたら 0 件が正しい**
    #    （様式型の労働条件通知書は押印欄を持たない。docs/decisions.md 65）。
    signatures = [node for node in draft.back_matter.signature]
    wanted = _signature_policy(draft)
    if wanted == "forbidden":
        if signatures:
            yield Finding(
                "L20",
                "error",
                f"この doctype は記名押印欄を持たない（blueprint の signature: forbidden）"
                f"のに {len(signatures)} 件ある",
                path="back_matter.signature",
            )
    elif len(signatures) != 1:
        yield Finding(
            "L20",
            "error",
            f"記名押印欄（signature）は back_matter にちょうど 1 つ置く（いまは {len(signatures)} 件）",
            path="back_matter.signature",
        )

    # scaffold が生成する後文は「各 1 通を保有する」と明記するため、作成通数は
    # 記名する当事者数と一致しなければならない。通数だけを別に変えると、例えば
    # 「本書 1 通を作成し、両当事者が各 1 通を保有する」という不可能な後文になる。
    if wanted != "forbidden" and signatures:
        party_count = len(draft.meta.parties)
        if draft.meta.copies != party_count:
            yield Finding(
                "L20",
                "error",
                f"後文が各当事者 1 通の保有を定めるため、meta.copies は当事者数と一致させる"
                f"（通数 {draft.meta.copies}、当事者数 {party_count}）",
                path="meta.copies",
            )

    # 4. 記名欄が全当事者を覆っているか（漏れも余りも error）
    for node in signatures:
        declared = {p.key for p in draft.meta.parties}
        listed = set(node.parties or declared)
        missing = declared - listed
        extra = listed - declared
        if missing:
            yield Finding(
                "L20",
                "error",
                f"記名押印欄に載っていない当事者がいる: {'、'.join(sorted(missing))}",
                element_id=node.id,
            )
        if extra:
            yield Finding(
                "L20",
                "error",
                f"記名押印欄が知らない当事者を載せている: {'、'.join(sorted(extra))}",
                element_id=node.id,
            )

    # 5. 別紙・附則の置き場所
    for node in draft.body:
        if node.kind in ("appendix", "supplement"):
            yield Finding(
                "L20",
                "error",
                f"{node.kind} は appendices に置く（body ではない）",
                element_id=node.id,
            )


# --- L21 逐条解説 -------------------------------------------------------------

_SENTENCE = re.compile(r"[^。]+。")


#: 逐条解説が指してよいノード。P1 の実測で、**項を指す解説**が実在した
#: （国交省の標準賃貸借契約書の解説は段落ごとに `【第N項】` のバッジを持つ。CT20・decisions 61）。
_COMMENTARY_ANCHOR_KINDS = frozenset({"article", "paragraph"})


@rule("L21", "逐条解説（anchor の存在・本文の複製でないこと）")
def l21_commentary(ctx: LintContext) -> Iterator[Finding]:
    draft = ctx.draft
    articles = {node.id: node for node, _a in iter_nodes(document_nodes(draft))}
    seen_anchors: set[str] = set()

    for block, _owner, _article in iter_blocks(draft):
        if not isinstance(block, CommentaryBlock):
            continue
        target = articles.get(block.anchor)
        if target is None:
            yield Finding(
                "L21",
                "error",
                f"逐条解説の anchor が存在しない: {block.anchor}",
                element_id=block.id,
            )
            continue
        if target.kind not in _COMMENTARY_ANCHOR_KINDS:
            yield Finding(
                "L21",
                "error",
                f"逐条解説の anchor は条または項を指す（{block.anchor} は {target.kind}）",
                element_id=block.id,
            )
        if block.anchor in seen_anchors:
            yield Finding(
                "L21",
                "error",
                f"同じ条に逐条解説が 2 つ付いている: {block.anchor}",
                element_id=block.id,
            )
        seen_anchors.add(block.anchor)

        # 解説が本文の文をそのまま抱えていないか（解説が本文のコピーになっている兆候）。
        # anchor が項のときは、その項自身の文も見る（条のときは子の項を見る）。
        sources = [target, *target.children] if target.kind != "article" else list(target.children)
        body_sentences = {
            s.strip()
            for child in sources
            for s in _SENTENCE.findall(child.text or "")
            if len(s.strip()) >= 20
        }
        for text in block.text:
            for sentence in _SENTENCE.findall(text):
                if sentence.strip() in body_sentences:
                    yield Finding(
                        "L21",
                        "warn",
                        "逐条解説が本文と同じ文を含んでいる"
                        f"（{sentence.strip()[:24]}…）。解説は本文の言い換えではなく背景や運用を書く",
                        element_id=block.id,
                    )
                    break
