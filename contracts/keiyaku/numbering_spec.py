"""番号方式の宣言（`numbering/<scheme>.yaml`）の読み込みと解釈（docs/schema.md §7）。

doctype を足すたびに Python を書き換えないために、番号方式は**宣言で持つ**
（docs/architecture.md §2「番号方式の解釈器はコア、定義はファミリー」）。
このモジュールが解釈器で、`keiyaku/numbering.py` がそれを使ってラベルを組む。

宣言で書けない規則が出たら、**まず宣言スキーマの表現力を疑う**。
どうしても書けないものは理由を `docs/decisions.md` に記録してから逃がす。

## YAML の形

```yaml
scheme: contract-standard
levels:
  article:    { format: "第{n}条", counter: arabic }
  paragraph:  { format: "{n}",    counter: arabic, skip_first: true }
  item:       { format: "({n})",  counter: arabic }
appendix:
  kind_label: 別表            # 既定の呼び名（Node.kind_label で上書きできる）
  bare_when_first: false      # 「附則」のように 1 つ目は番号を付けない方式なら true
appendix_levels:              # 別表の中の独立体系（省略すると levels を使う）
  appendix_section: { format: "第{n}", counter: arabic }
footnote:
  inline: "（*{n}）"          # 条末脚注のマーカー
continuous_articles: true     # 条を章ごとに振り直さず全編通し
paragraph_ref_style: written  # 印字が無番号でも参照は「第N項」と書き下す
ref: { article_with_title: true, no_chapter_prefix: true }
```

### `format` の約束

- `{n}` は `counter` で描いた番号に置き換わる。
- `{kind_label}` は別表の呼び名（`appendix.kind_label` または `Node.kind_label`）。
- **半角括弧 `(` `)` は `meta.digit_style` に従って全角化する**（`fullwidth` なら `（` `）`）。
  全角括弧を直接書いた場合は常に全角のまま。
- 空文字の `format` は「番号を持たない階層」（`counter: none` と同義）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

#: 宣言の置き場。doctype と同じく、ファイルの存在が正本。
NUMBERING_DIR = Path(__file__).resolve().parent.parent / "numbering"

DigitStyle = Literal["fullwidth", "halfwidth"]

_FULLWIDTH = str.maketrans("0123456789", "０１２３４５６７８９")

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
KATAKANA = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"
ROMAN = "ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ"
BLACK_CIRCLED = "❶❷❸❹❺❻❼❽❾❿"

#: 使えるカウンタ。`kanji` は**約款型の条番号**（「第一条」）に使う——P1 の実測で、
#: 公共工事標準請負契約約款など 3 件が漢数字だった（CT23・`docs/decisions.md` 60）。
#: `iroha` は法令（docsynth の statute）用で、契約書では使わない。
COUNTERS = frozenset({"arabic", "circled", "katakana", "roman", "kanji", "none"})


class NumberingSpecError(ValueError):
    """宣言の形が不正、または宣言が見つからない。"""


@dataclass(frozen=True)
class LevelSpec:
    """1 階層（kind）のラベル生成規則。"""

    format: str = ""
    counter: str = "arabic"
    #: 第1項を無番号にする（印字上は 2 から始まる方式。定款・団体保険・契約書）
    skip_first: bool = False
    #: 同じ親の下にその階層が 1 つしかなければ無番号にする（損保・生保の項）
    skip_when_single: bool = False
    #: この階層をその方式では使わない。使われたらこの文言で警告する
    unsupported: str | None = None


@dataclass(frozen=True)
class AppendixSpec:
    """別紙・別表・附則のラベル規則。"""

    kind_label: str = "別表"
    #: 「附則」のように 1 つ目だけ番号を付けない方式
    bare_when_first: bool = False


@dataclass(frozen=True)
class FootnoteSpec:
    """条末脚注のマーカー。`remarks_box` は黒丸数字（方式に依らない）。"""

    inline: str = "（*{n}）"


@dataclass(frozen=True)
class RefSpec:
    """`{ref:}` の相対表記の規則（docs/schema.md §7）。"""

    #: 他条参照に見出し文言を添える（「第4条（機密情報の返還）」）
    article_with_title: bool = True
    #: 条が通し番号なので参照に章を冠さない
    no_chapter_prefix: bool = False


@dataclass(frozen=True)
class SchemeSpec:
    """1 つの番号方式の宣言ぜんぶ。"""

    scheme: str
    levels: dict[str, LevelSpec] = field(default_factory=dict)
    appendix: AppendixSpec = field(default_factory=AppendixSpec)
    appendix_levels: dict[str, LevelSpec] = field(default_factory=dict)
    #: 頭書の中の独立体系（省略すると `levels` を使う）。実物の頭書は号を括弧なしの
    #: 算用数字で振る（`docs/reference_structures.md` §4 の #5）。
    head_matter_levels: dict[str, LevelSpec] = field(default_factory=dict)
    footnote: FootnoteSpec = field(default_factory=FootnoteSpec)
    continuous_articles: bool = False
    #: `written` は印字が無番号でも参照を「第N項」「第N号」と書き下す
    paragraph_ref_style: str = "printed"
    ref: RefSpec = field(default_factory=RefSpec)

    def level(self, kind: str, scope: str = "body") -> LevelSpec | None:
        """その kind の規則を引く。`scope` は "body" / "appendix" / "head_matter"。

        別表や頭書は本文と別の番号体系を持つので、その scope の宣言を先に見て、
        無ければ `levels` に落ちる（宣言側で全階層を書かなくてよいようにするため）。
        """
        by_scope = {"appendix": self.appendix_levels, "head_matter": self.head_matter_levels}
        overrides = by_scope.get(scope)
        if overrides and kind in overrides:
            return overrides[kind]
        return self.levels.get(kind)


# --- カウンタ -----------------------------------------------------------------


def to_digits(n: int, style: DigitStyle) -> str:
    s = str(n)
    return s.translate(_FULLWIDTH) if style == "fullwidth" else s


#: 漢数字の桁。約款の条番号は 3 桁（「第二百三十三条」）まで出るので万までは要らない。
_KANJI_DIGITS = "〇一二三四五六七八九"
_KANJI_UNITS = ((1000, "千"), (100, "百"), (10, "十"))


def to_kanji(n: int) -> str:
    """算用数字を漢数字にする（法令・約款の流儀）。

    「十一」「二十」「百」「二百三十三」のように、**1 の位の「一」は単位の前で落とす**
    （「一十」ではなく「十」）。0 と負数は扱わない（番号は 1 から振るため）。
    """
    if n <= 0:
        return _KANJI_DIGITS[0]
    out: list[str] = []
    rest = n
    for value, unit in _KANJI_UNITS:
        count, rest = divmod(rest, value)
        if count:
            # 「一十」「一百」とは書かない。「一千」も約款では「千」
            out.append(("" if count == 1 else _KANJI_DIGITS[count]) + unit)
    if rest:
        out.append(_KANJI_DIGITS[rest])
    return "".join(out)


def render_counter(
    counter: str,
    n: int,
    style: DigitStyle,
    on_fallback: object | None = None,
) -> str:
    """番号 1 つを文字にする。表の外に出たら括弧数字へ落として `on_fallback` を呼ぶ。

    `on_fallback(message)` は警告の受け口（丸数字が ⑳ を超えた等）。
    """
    match counter:
        case "none":
            return ""
        case "arabic":
            return to_digits(n, style)
        case "circled":
            if 1 <= n <= len(CIRCLED):
                return CIRCLED[n - 1]
            if callable(on_fallback):
                on_fallback(f"丸数字は{len(CIRCLED)}までしか無いため {n} は括弧数字にフォールバックした")
            return _paren(to_digits(n, style), style)
        case "katakana":
            return KATAKANA[n - 1] if 1 <= n <= len(KATAKANA) else to_digits(n, style)
        case "roman":
            return ROMAN[n - 1] if 1 <= n <= len(ROMAN) else to_digits(n, style)
        case "kanji":
            # 漢数字は全角・半角の別を持たない（`digit_style` に依らない）
            return to_kanji(n)
    raise NumberingSpecError(f"未知の counter: {counter}（使えるのは {sorted(COUNTERS)}）")


def _paren(body: str, style: DigitStyle) -> str:
    return f"（{body}）" if style == "fullwidth" else f"({body})"


def apply_format(
    spec: LevelSpec,
    n: int,
    style: DigitStyle,
    kind_label: str | None = None,
    on_fallback: object | None = None,
) -> str:
    """`format` に番号を埋める。半角括弧は digit_style に従って全角化する。"""
    if not spec.format:
        return ""
    body = render_counter(spec.counter, n, style, on_fallback)
    out = spec.format.replace("{n}", body)
    if kind_label is not None:
        out = out.replace("{kind_label}", kind_label)
    if style == "fullwidth":
        out = out.replace("(", "（").replace(")", "）")
    return out


def black_circled(n: int, style: DigitStyle, on_fallback: object | None = None) -> str:
    """`footnote_style: remarks_box` のマーカー（❶〜❿）。方式に依らない。"""
    if 1 <= n <= len(BLACK_CIRCLED):
        return BLACK_CIRCLED[n - 1]
    if callable(on_fallback):
        on_fallback(f"備考のマーカーは {len(BLACK_CIRCLED)} 件まで（{n} 件目）")
    return f"({n})"


# --- 読み込み -----------------------------------------------------------------


def _level(raw: object, where: str) -> LevelSpec:
    if raw is None:
        return LevelSpec(format="", counter="none")
    if not isinstance(raw, dict):
        raise NumberingSpecError(f"{where} は辞書で書く: {raw!r}")
    unknown = set(raw) - {"format", "counter", "skip_first", "skip_when_single", "unsupported"}
    if unknown:
        raise NumberingSpecError(f"{where} に未知のキー: {sorted(unknown)}")
    counter = str(raw.get("counter", "arabic"))
    if counter not in COUNTERS:
        raise NumberingSpecError(f"{where}.counter が不正: {counter}（使えるのは {sorted(COUNTERS)}）")
    return LevelSpec(
        format=str(raw.get("format", "")),
        counter=counter,
        skip_first=bool(raw.get("skip_first", False)),
        skip_when_single=bool(raw.get("skip_when_single", False)),
        unsupported=raw.get("unsupported"),
    )


def parse_scheme(data: dict, name: str | None = None) -> SchemeSpec:
    """辞書から `SchemeSpec` を組む（YAML を読まずに検査したいときにも使う）。"""
    if not isinstance(data, dict):
        raise NumberingSpecError("numbering の宣言は辞書で書く")
    unknown = set(data) - {
        "scheme",
        "levels",
        "appendix",
        "appendix_levels",
        "head_matter_levels",
        "footnote",
        "continuous_articles",
        "paragraph_ref_style",
        "ref",
        "counters_available",
        "digit_style_from_meta",
        "description",
    }
    if unknown:
        raise NumberingSpecError(f"numbering の宣言に未知のキー: {sorted(unknown)}")

    scheme = str(data.get("scheme") or name or "")
    if not scheme:
        raise NumberingSpecError("scheme が空")
    if name and scheme != name:
        raise NumberingSpecError(f"ファイル名 {name}.yaml と scheme: {scheme} が食い違う")

    levels = {k: _level(v, f"levels.{k}") for k, v in (data.get("levels") or {}).items()}
    appendix_levels = {
        k: _level(v, f"appendix_levels.{k}") for k, v in (data.get("appendix_levels") or {}).items()
    }
    head_matter_levels = {
        k: _level(v, f"head_matter_levels.{k}") for k, v in (data.get("head_matter_levels") or {}).items()
    }

    raw_appendix = data.get("appendix") or {}
    if not isinstance(raw_appendix, dict):
        raise NumberingSpecError("appendix は辞書で書く")
    appendix = AppendixSpec(
        kind_label=str(raw_appendix.get("kind_label", "別表")),
        bare_when_first=bool(raw_appendix.get("bare_when_first", False)),
    )

    raw_footnote = data.get("footnote") or {}
    if not isinstance(raw_footnote, dict):
        raise NumberingSpecError("footnote は辞書で書く")
    footnote = FootnoteSpec(inline=str(raw_footnote.get("inline", "（*{n}）")))

    raw_ref = data.get("ref") or {}
    if not isinstance(raw_ref, dict):
        raise NumberingSpecError("ref は辞書で書く")
    ref = RefSpec(
        article_with_title=bool(raw_ref.get("article_with_title", True)),
        no_chapter_prefix=bool(raw_ref.get("no_chapter_prefix", False)),
    )

    style = str(data.get("paragraph_ref_style", "printed"))
    if style not in ("printed", "written"):
        raise NumberingSpecError(f"paragraph_ref_style が不正: {style}（printed / written）")

    return SchemeSpec(
        scheme=scheme,
        levels=levels,
        appendix=appendix,
        appendix_levels=appendix_levels,
        head_matter_levels=head_matter_levels,
        footnote=footnote,
        continuous_articles=bool(data.get("continuous_articles", False)),
        paragraph_ref_style=style,
        ref=ref,
    )


_CACHE: dict[tuple[str, str], SchemeSpec] = {}


def load_scheme(name: str, numbering_dir: Path | None = None) -> SchemeSpec:
    """`numbering/<name>.yaml` を読む。同じパスは覚えておく（build は何度も引く）。"""
    directory = numbering_dir or NUMBERING_DIR
    key = (str(directory), name)
    if key in _CACHE:
        return _CACHE[key]
    path = directory / f"{name}.yaml"
    if not path.is_file():
        raise NumberingSpecError(f"numbering の宣言が無い: {path}")
    spec = parse_scheme(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, name)
    _CACHE[key] = spec
    return spec


def available_schemes(numbering_dir: Path | None = None) -> list[str]:
    directory = numbering_dir or NUMBERING_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def clear_cache() -> None:
    """テストで宣言を差し替えるとき用。"""
    _CACHE.clear()
