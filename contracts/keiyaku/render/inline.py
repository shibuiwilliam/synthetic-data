"""RichText → HTML（docs/schema.md §5.3 / docs/rendering.md §6.3）。

平文（`derived.plain_text`）と **同じ解決結果** を返さなければならない。
両者がずれると往復検証（§6.9）が落ちるので、参照・用語・定数の解決は
`keiyaku.build.BuildContext` が作る解決関数をそのまま使う。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from html import escape

from keiyaku.richtext import (
    AutoLabel,
    Bold,
    Br,
    Const,
    Fn,
    Inline,
    Party,
    Ref,
    Ruby,
    Term,
    Text,
    Underline,
    parse,
)


@dataclass
class InlineContext:
    """インライン描画に必要な解決関数。`to_plain` と同じ結果を返すこと。"""

    resolve_ref: Callable[[str, str], str]
    resolve_term: Callable[[str], str]
    resolve_const: Callable[[str], str]
    footnote_marker: Callable[[int], str]
    #: 当事者の呼称を解決する（`{party:}`）。build の `to_plain` と同じ文字列を返すこと。
    resolve_party: Callable[[str, str], str] = lambda _key, _mode: ""
    auto_label: str = ""
    element_id: str = ""


def render_inline(source: str, ctx: InlineContext) -> str:
    return _render(parse(source), ctx)


def _render(nodes: tuple[Inline, ...], ctx: InlineContext) -> str:
    out: list[str] = []
    for node in nodes:
        match node:
            case Text(value):
                out.append(escape(value))
            case Ref(target, mode):
                rendered = escape(ctx.resolve_ref(target, mode))
                out.append(f'<a class="ref" href="#{escape(target)}" data-kind="ref">{rendered}</a>')
            case Fn(n):
                marker = escape(ctx.footnote_marker(n))
                out.append(f'<span class="fnref" data-kind="footnote_ref" data-n="{n}">{marker}</span>')
            case Term(term_id):
                word = escape(ctx.resolve_term(term_id))
                out.append(f'<span class="term" data-kind="term" data-term="{escape(term_id)}">{word}</span>')
            case Bold(children):
                out.append(f'<span class="b">{_render(children, ctx)}</span>')
            case Underline(children):
                out.append(f'<span class="u">{_render(children, ctx)}</span>')
            case Ruby(base, reading):
                # <ruby> は WeasyPrint 70.0 非対応。inline-block で読みを上に積む（docs/decisions.md）
                out.append(
                    f'<span class="ruby" data-kind="ruby"><span class="rt">{escape(reading)}</span>'
                    f'<span class="rb">{escape(base)}</span></span>'
                )
            case Br():
                out.append("<br>")
            case Const(key):
                value = escape(ctx.resolve_const(key))
                out.append(f'<span class="const" data-const="{escape(key)}">{value}</span>')
            case AutoLabel():
                out.append(escape(ctx.auto_label))
            case Party(key, mode):
                # 当事者の呼称。`to_plain` と同じ文字列を出す（V03 の往復比較が通るように）。
                rendered = escape(ctx.resolve_party(key, mode))
                out.append(
                    f'<span class="party" data-kind="party" data-party="{escape(key)}">{rendered}</span>'
                )
    return "".join(out)
