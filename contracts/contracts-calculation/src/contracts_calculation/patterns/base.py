"""パターンの共通基盤：下書き（RuleDraft）の型と、値・表記のヘルパ。

1 つのパターンの `sample(ctx, rng)` が、同じ乱数から
「契約書に足す内容（条のタイトル・段落・表）」と「計算仕様（inputs・steps・output）」の
両方の材料を持つ RuleDraft を返す。文言とプログラムを別々に書く経路は無い。

段落テキストの placeholders:
- `{const:<key>}`   … そのまま本体の RichText トークンとして出す（meta.constants に払い出す）
- `{party:<key>}`   … 同上
- `{TBL:<name>}`    … realize/patch が実際の表 id に置き換えて `{ref:tbl_...}` にする
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Protocol

_PACKS = Path(__file__).resolve().parents[3] / "packs"

_FW = str.maketrans("0123456789.%,-", "０１２３４５６７８９．％，－")


def fw(text: str, digit_style: str) -> str:
    """halfwidth で組んだ文字列を、文書の digit_style に合わせる。"""
    return text.translate(_FW) if digit_style == "fullwidth" else text


def money(n: int, digit_style: str) -> str:
    """整数の円 → 「80万円」「4,440円」形の表記（digit_style 反映）。"""
    from ..docmodel.numbers_ja import format_amount_yen

    return fw(format_amount_yen(n, "man"), digit_style)


@cache
def load_pack(name: str) -> dict:
    return json.loads((_PACKS / name).read_text(encoding="utf-8"))


def concept(name: str) -> dict:
    """概念語彙から InputDecl の辞書を作る。"""
    c = dict(load_pack("concepts.json")["concepts"][name])
    ja = c.pop("ja")
    c["desc"] = ja
    return c


def values_of(pattern_key: str) -> dict:
    return load_pack("values.json")[pattern_key]


@dataclass
class ParamDraft:
    """契約書に書く定数の下書き。surface は紙面の表記（digit_style 反映済み）。"""

    name: str
    type: str  # int / ratio / date
    surface: str
    value: int | str | None = None
    num: int | None = None
    den: int | None = None
    unit: str | None = None

    def to_spec(self, source: dict) -> dict:
        d: dict = {"type": self.type, "surface": self.surface, "source": source}
        if self.type == "ratio":
            d["num"], d["den"] = self.num, self.den
        else:
            d["value"] = self.value
        if self.unit:
            d["unit"] = self.unit
        return d


@dataclass
class TableRowDraft:
    label: str  # 区分の表示（「1件以上100件以下」）
    upto: int | None
    value: int
    value_text: str  # セルの表示（「500円」）


@dataclass
class TableDraft:
    """契約書に足す段階表の下書き。"""

    name: str  # 仕様内の表名（spec.tables のキー）
    caption: str
    semantic_type: str
    col_labels: tuple[str, str]  # （区分の列, 値の列）
    rows: list[TableRowDraft] = field(default_factory=list)
    unit: str = "JPY/COUNT"  # 値の列の単位（割戻率の表は "PERMILLE"）

    def to_spec_rows(self) -> list[dict]:
        return [{"upto": r.upto, "value": r.value} for r in self.rows]


@dataclass
class RuleDraft:
    """1 ルールの下書き。realize/patch が文書へ、generate が仕様へ展開する。"""

    pattern_id: str
    rule_id: str  # 仕様内のルール id（英語 slug）
    function: str
    title: str  # 条の見出し（「保管手数料」）
    kind: str  # calculation / determination
    params: dict[str, ParamDraft] = field(default_factory=dict)
    tables: dict[str, TableDraft] = field(default_factory=dict)
    inputs: dict[str, dict] = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    output: dict = field(default_factory=dict)
    obligations: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)  # 段落テキスト（placeholders 入り）
    table_paragraph: int | None = None  # 表を blocks に付ける段落の添字（L22）
    parties: dict | None = None  # {"payer": alias, "payee": alias}
    needs_calendar: bool = False
    difficulty: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    challenge: dict | None = None  # {"type": "omission"|"anomaly", "aspect": ...}（M5 の challenge モード）
    force_appendix: bool = False  # 表を必ず別紙に置く（K31 の優先順位）
    literal_surfaces: list[str] = field(default_factory=list)  # 文型に固定で現れる数量語（「1件」等）
    case_hints: list[dict] = field(
        default_factory=list
    )  # パターンが指定する境界入力（テスト生成が必ず含める）
    figure_blocks: list = field(default_factory=list)  # [(段落の添字, figure ブロック)]。規範の図（K28）
    #: 頭書分離の選択肢（頭書を持つ文書のみ）。{"param": 定数名, "title": 項目名, "body_paragraphs": 本文の差替}
    header_option: dict | None = None


class Pattern(Protocol):
    id: str
    title: str
    genres: frozenset[str]
    topics: tuple[str, ...]  # 既定の契約書に同じ事項があるかの検出語

    def applicable(self, ctx) -> bool: ...

    def sample(self, ctx, rng) -> RuleDraft: ...


@dataclass(frozen=True)
class PatternDef:
    """関数ベースでパターンを定義するための器。"""

    id: str
    title: str
    genres: frozenset[str]
    topics: tuple[str, ...]
    sampler: Callable
    extra_applicable: Callable | None = None

    def applicable(self, ctx) -> bool:
        if ctx.doctype not in self.genres:
            return False
        if ctx.has_topic(*self.topics):
            return False
        return not (self.extra_applicable and not self.extra_applicable(ctx))

    def sample(self, ctx, rng) -> RuleDraft:
        return self.sampler(ctx, rng)


# --- 式の組み立て（仕様の expr。tests/appendix_b_specs.py と同じ形） ----------------


def lit(v) -> dict:
    return {"lit": v}


def var(n: str) -> dict:
    return {"var": n}


def param(n: str) -> dict:
    return {"param": n}


def step(n: str) -> dict:
    return {"step": n}


def op(name: str, *args, **attrs) -> dict:
    d = {"op": name, "args": list(args)}
    d.update(attrs)
    return d


# --- 共通の文片（lexicon の最小核。詳細は realize/lexicon_ja.py） -----------------


def sentence_rounding(rounding: str, digit_style: str, variant: int = 0) -> str:
    """端数処理の文。変種は同じ意味に限る（§9.3。G3 の検査語に両方とも一致する）。"""
    word = {"floor": "切り捨てる", "ceil": "切り上げる", "half_up": "四捨五入する"}[rounding]
    if variant % 2 == 1:
        return fw("1円未満の端数が生じたときは、これを", digit_style) + word + "。"
    return fw("この計算により生じた1円未満の端数は", digit_style) + word + "。"


def pct_surface(permille: int, digit_style: str) -> str:
    """千分率 → 「14.6%」「3%」形の表記。"""
    if permille % 10 == 0:
        text = f"{permille // 10}%"
    else:
        text = f"{permille // 10}.{permille % 10}%"
    return fw(text, digit_style)


CALENDAR_DEF_SENTENCE = "本条において「営業日」とは、土曜日、日曜日、国民の祝日および{d1229}から翌年{d0103}までの日を除いた日をいう。"


def calendar_def_paragraph(digit_style: str) -> str:
    return CALENDAR_DEF_SENTENCE.format(d1229=fw("12月29日", digit_style), d0103=fw("1月3日", digit_style))
