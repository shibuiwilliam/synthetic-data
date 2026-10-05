"""RichText のトークナイザと平文化（docs/schema.md §5.3）。

許可トークンはこれだけ。未知トークンは `RichTextError`（lint L03 が報告する）。

| トークン | 意味 |
|---|---|
| `{ref:<node_id>}`（`\\|short` `\\|full` で上書き） | 条項参照。解決は `keiyaku.numbering.resolve_ref` |
| `{fn:<n>}` | 条末脚注のマーカー（（*1）／（注1）） |
| `{term:<term_id>}` | 定義語。平文では語そのもの |
| `{b:…}` `{u:…}` | 太字・下線（入れ子可）。平文では除去 |
| `{ruby:漢字\\|よみ}` | ルビ。平文では基底文字のみ |
| `{br}` | 改行 |
| `{const:<key>}` | `meta.constants` の値（CLAUDE.md §8 L11） |
| `{auto_label}` | 列挙表の自動採番ラベル（docs/schema.md §5.4） |

エスケープは `{{` → `{`、`}}` → `}`。ただし `}}` が `}` の文字になるのは最上位だけで、
`{b:…}` `{u:…}` の中では `}` は常に閉じ括弧として扱う（入れ子を優先する）。
囲みトークンの中に文字としての `}` は書けない。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

RefMode = Literal["relative", "short", "full"]
#: `{party:key|mode}` の修飾子（docs/schema.md §4）
PartyMode = Literal["alias", "name", "full", "role"]


class RichTextError(ValueError):
    """RichText の記法エラー。`position` は文字列中の位置。"""

    def __init__(self, message: str, position: int, source: str) -> None:
        super().__init__(f"{message}（位置 {position}: {source[max(0, position - 12) : position + 12]!r}）")
        self.position = position
        self.source = source


# --- AST ---------------------------------------------------------------------


@dataclass(frozen=True)
class Text:
    value: str


@dataclass(frozen=True)
class Ref:
    target: str
    mode: RefMode = "relative"


@dataclass(frozen=True)
class Fn:
    n: int


@dataclass(frozen=True)
class Term:
    term_id: str


@dataclass(frozen=True)
class Bold:
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class Underline:
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class Ruby:
    base: str
    reading: str


@dataclass(frozen=True)
class Br:
    pass


@dataclass(frozen=True)
class Const:
    key: str


@dataclass(frozen=True)
class AutoLabel:
    pass


@dataclass(frozen=True)
class Party:
    """当事者の呼称（docs/schema.md §4）。紙面の文字列は build が `meta.parties` から解決する。

    執筆者が「甲」「乙」を直書きすると呼称の揺れ・取り違えが起きるので、番号ラベルと同じく
    トークンで書かせて計算する（CLAUDE.md §0.4-8・§2-2）。
    """

    key: str
    #: alias（「甲」）/ name（正式名称）/ full（「株式会社◯◯（以下「甲」という。）」）/ role（役割名）
    mode: PartyMode = "alias"


Inline = Text | Ref | Fn | Term | Bold | Underline | Ruby | Br | Const | AutoLabel | Party

#: 引数を取るトークン
_ARG_TOKENS = frozenset({"ref", "fn", "term", "b", "u", "ruby", "const", "party"})
#: 引数を取らないトークン
_BARE_TOKENS = frozenset({"br", "auto_label"})
#: 中に別のトークンを入れられるトークン
_CONTAINER_TOKENS = frozenset({"b", "u"})


# --- パーサ -------------------------------------------------------------------


def parse(source: str) -> tuple[Inline, ...]:
    """RichText を AST に変換する。"""
    nodes, end = _parse_until(source, 0, stop_at_close=False)
    if end != len(source):
        raise RichTextError("対応しない '}' がある", end, source)
    return nodes


def _parse_until(source: str, i: int, stop_at_close: bool) -> tuple[tuple[Inline, ...], int]:
    nodes: list[Inline] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            nodes.append(Text("".join(buffer)))
            buffer.clear()

    while i < len(source):
        char = source[i]
        if char == "{":
            if source.startswith("{{", i):
                buffer.append("{")
                i += 2
                continue
            flush()
            node, i = _parse_token(source, i)
            nodes.append(node)
            continue
        if char == "}":
            # '}}' をエスケープとして扱うのは最上位だけ。囲みトークンの中では '}' は常に閉じ括弧
            # （そうしないと {b:重要{u:な}} の末尾がエスケープに化けて入れ子が壊れる）。
            if not stop_at_close and source.startswith("}}", i):
                buffer.append("}")
                i += 2
                continue
            if stop_at_close:
                flush()
                return tuple(nodes), i
            raise RichTextError("'}' が単独で現れた（エスケープは '}}'）", i, source)
        buffer.append(char)
        i += 1

    if stop_at_close:
        raise RichTextError("閉じ '}' が無い", i, source)
    flush()
    return tuple(nodes), i


def _parse_token(source: str, start: int) -> tuple[Inline, int]:
    i = start + 1
    name_chars: list[str] = []
    while i < len(source) and (source[i].isalnum() or source[i] == "_"):
        name_chars.append(source[i])
        i += 1
    name = "".join(name_chars)
    if not name:
        raise RichTextError("トークン名が空", start, source)

    if i < len(source) and source[i] == "}":
        if name not in _BARE_TOKENS:
            if name in _ARG_TOKENS:
                raise RichTextError(f"'{{{name}:…}}' は引数が要る", start, source)
            raise RichTextError(f"未知のトークン '{{{name}}}'", start, source)
        return (Br() if name == "br" else AutoLabel()), i + 1

    if i >= len(source) or source[i] != ":":
        raise RichTextError(f"トークン '{{{name}' の書式が不正", start, source)
    i += 1

    if name not in _ARG_TOKENS:
        raise RichTextError(f"未知のトークン '{{{name}:…}}'", start, source)

    if name in _CONTAINER_TOKENS:
        children, i = _parse_until(source, i, stop_at_close=True)
        if i >= len(source) or source[i] != "}":
            raise RichTextError(f"'{{{name}:' が閉じていない", start, source)
        if not children:
            raise RichTextError(f"'{{{name}:}}' の中身が空", start, source)
        node: Inline = Bold(children) if name == "b" else Underline(children)
        return node, i + 1

    arg_chars: list[str] = []
    while i < len(source) and source[i] != "}":
        if source[i] == "{":
            raise RichTextError(f"'{{{name}:…}}' の引数にトークンは書けない", start, source)
        arg_chars.append(source[i])
        i += 1
    if i >= len(source):
        raise RichTextError(f"'{{{name}:' が閉じていない", start, source)
    arg = "".join(arg_chars)
    i += 1

    match name:
        case "ref":
            target, _, mode = arg.partition("|")
            target = target.strip()
            mode = mode.strip() or "relative"
            if not target:
                raise RichTextError("'{ref:}' の参照先が空", start, source)
            if mode not in ("relative", "short", "full"):
                raise RichTextError(
                    f"'{{ref:}}' の修飾子が不正: {mode!r}（short / full のみ）", start, source
                )
            return Ref(target, mode), i  # type: ignore[arg-type]
        case "fn":
            if not arg.isdigit() or int(arg) < 1:
                raise RichTextError(f"'{{fn:}}' は 1 以上の整数: {arg!r}", start, source)
            return Fn(int(arg)), i
        case "term":
            if not arg.strip():
                raise RichTextError("'{term:}' の用語 id が空", start, source)
            return Term(arg.strip()), i
        case "ruby":
            base, sep, reading = arg.partition("|")
            if not sep or not base.strip() or not reading.strip():
                raise RichTextError("'{ruby:漢字|よみ}' の形で書く", start, source)
            return Ruby(base.strip(), reading.strip()), i
        case "const":
            if not arg.strip():
                raise RichTextError("'{const:}' のキーが空", start, source)
            return Const(arg.strip()), i
        case "party":
            key, _, mode = arg.partition("|")
            key = key.strip()
            mode = mode.strip() or "alias"
            if not key:
                raise RichTextError("'{party:}' の当事者キーが空", start, source)
            if mode not in ("alias", "name", "full", "role"):
                raise RichTextError(
                    f"'{{party:}}' の修飾子が不正: {mode!r}（name / full / role のみ）", start, source
                )
            return Party(key, mode), i  # type: ignore[arg-type]
    raise RichTextError(f"未知のトークン '{{{name}:…}}'", start, source)


# --- 平文化 -------------------------------------------------------------------


class UnresolvedToken(KeyError):
    """参照先・用語・定数が見つからない。"""


@dataclass
class PlainContext:
    """平文化に必要な解決関数。未設定のものが現れたら `UnresolvedToken`。"""

    resolve_ref: Callable[[str, RefMode], str] | None = None
    resolve_term: Callable[[str], str] | None = None
    resolve_const: Callable[[str], str] | None = None
    resolve_party: Callable[[str, PartyMode], str] | None = None
    footnote_marker: Callable[[int], str] = lambda n: f"（*{n}）"
    auto_label: str = ""
    #: ルビを読みも含めて出すか（既定は基底文字のみ＝PDF のテキスト層に合わせる）
    ruby_with_reading: bool = False
    #: 収集した参照（平文化のついでに derived の材料を集める）
    used_refs: list[tuple[str, RefMode, str]] = field(default_factory=list)
    used_terms: list[str] = field(default_factory=list)
    used_footnotes: list[int] = field(default_factory=list)
    used_consts: list[str] = field(default_factory=list)
    used_parties: list[tuple[str, PartyMode, str]] = field(default_factory=list)
    rubies: list[tuple[str, str]] = field(default_factory=list)


def to_plain(nodes: tuple[Inline, ...], ctx: PlainContext | None = None) -> str:
    """AST を平文にする。マークアップは除去し、参照は解決する。"""
    ctx = ctx or PlainContext()
    out: list[str] = []
    for node in nodes:
        match node:
            case Text(value):
                out.append(value)
            case Ref(target, mode):
                if ctx.resolve_ref is None:
                    raise UnresolvedToken(f"参照を解決できない: {target}")
                rendered = ctx.resolve_ref(target, mode)
                ctx.used_refs.append((target, mode, rendered))
                out.append(rendered)
            case Fn(n):
                ctx.used_footnotes.append(n)
                out.append(ctx.footnote_marker(n))
            case Term(term_id):
                if ctx.resolve_term is None:
                    raise UnresolvedToken(f"用語を解決できない: {term_id}")
                ctx.used_terms.append(term_id)
                out.append(ctx.resolve_term(term_id))
            case Bold(children) | Underline(children):
                out.append(to_plain(children, ctx))
            case Ruby(base, reading):
                ctx.rubies.append((base, reading))
                out.append(f"{base}（{reading}）" if ctx.ruby_with_reading else base)
            case Br():
                out.append("\n")
            case Const(key):
                if ctx.resolve_const is None:
                    raise UnresolvedToken(f"定数を解決できない: {key}")
                ctx.used_consts.append(key)
                out.append(ctx.resolve_const(key))
            case AutoLabel():
                out.append(ctx.auto_label)
            case Party(key, mode):
                if ctx.resolve_party is None:
                    raise UnresolvedToken(f"当事者を解決できない: {key}")
                rendered = ctx.resolve_party(key, mode)
                ctx.used_parties.append((key, mode, rendered))
                out.append(rendered)
    return "".join(out)


def plain(source: str, ctx: PlainContext | None = None) -> str:
    """文字列 → 平文（parse + to_plain）。"""
    return to_plain(parse(source), ctx)


def with_label(label: str, body: str, separator: str = "") -> str:
    """ラベル付きの平文（`derived.plain_text.with_label`）。ラベルが空なら本文のみ。"""
    return f"{label}{separator}{body}" if label else body


def iter_tokens(nodes: tuple[Inline, ...]):
    """入れ子も含めて全トークンを順に返す。"""
    for node in nodes:
        yield node
        if isinstance(node, Bold | Underline):
            yield from iter_tokens(node.children)


def raw_text(nodes: tuple[Inline, ...]) -> str:
    """トークンを取り除いた地の文だけ（番号ラベル直書きの検出 L03 に使う）。"""
    return "".join(n.value for n in iter_tokens(nodes) if isinstance(n, Text))
