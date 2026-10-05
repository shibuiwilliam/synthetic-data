"""パターンの土台。

パターンは**ルールの型**である。乱数からパラメータを抽選し、表現に依存しない `RuleDraft`
だけを返す。文言・表・図への展開は `realize/` が受け持つ（DESIGN.md §7.2）。

パターンのコードに日本語の文は書かない。必要な名詞は `packs/<genre>.yaml` の語彙から取る
（`tests/unit/test_patterns_no_prose.py` がこれを固定する）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..core import numbers_ja as nj
from ..core.packs import PackError, Subject
from ..planning.context import Context


# ------------------------------------------------------------------ 式の組立
def V(name: str) -> dict:
    return {"var": name}


def P(name: str) -> dict:
    return {"param": name}


def S(name: str) -> dict:
    return {"step": name}


def R(rule_id: str, **bind) -> dict:
    out: dict[str, Any] = {"rule": rule_id}
    if bind:
        out["with"] = bind
    return out


def LIT(value, unit: str | None = None, note: str | None = None) -> dict:
    """数値リテラル。0 以外には必ず `note`（根拠）を付ける（`CLAUDE.md` 守ること 5）。"""
    out: dict[str, Any] = {"lit": value}
    if unit is not None:
        out["unit"] = unit
    if note is not None:
        out["note"] = note
    return out


def op(name: str, *args, **attrs) -> dict:
    return {"op": name, "args": list(args), **attrs}


def ITEM(field_name: str) -> dict:
    return {"item": field_name}


# ------------------------------------------------------------------ 下書き
@dataclass
class ConstDraft:
    """`meta.constants` に足す定数。値・表記・単位を 1 組で持つ。

    `unit` は式の中での次元（日額なら `JPY/DAY`）、`const_unit` は表記の単位（`JPY`）である。
    両者を分けないと「日額×日数＝金額」の単位検査が通らない。
    """

    name: str
    value: int
    unit: str
    surface: str
    const_unit: str | None = None

    @classmethod
    def of(cls, name: str, value: int, unit: str, per: str | None = None) -> ConstDraft:
        surface = nj.surface(value, unit)
        return cls(name, value, f"{unit}/{per}" if per else unit, surface, unit if per else None)


@dataclass
class StepDraft:
    """名前つきの手順。`role` が文への展開のしかたを決める。"""

    name: str
    expr: dict
    #: core=体言に積む / qualify=直前の額に対する但し書き / sentence=独立した文 / decide=判定（図・号）
    role: str = "core"
    #: 文型に渡す補足（`rate_name` `key_phrase` `own_paragraph` など）
    hint: dict[str, Any] = field(default_factory=dict)
    #: 既に日本語の名前が決まっているとき（既定は文型が作る体言）
    label: str | None = None


@dataclass
class TableDraft:
    """仕様から見た表（見た目は `realize` が決める）。"""

    name: str
    semantic_type: str
    key_header: str
    value_header: str
    keys: list[Any]
    values: list[int]
    key_surfaces: list[str]
    value_surfaces: list[str]
    mode: str = "step_le"
    key_parse: str = "upto_month"
    value_parse: str = "percent"
    key_unit: str = "MONTH"
    value_unit: str = "1"
    orientation: str = "header_keys"
    caption: str | None = None
    monotone: str | None = None


@dataclass
class EnumerationDraft:
    """号の表（除外の列挙・該当の列挙）。見た目は `realize` が決める。"""

    #: all=次のすべてに該当 / any=次のいずれかに該当 / exclude=次のいずれかに該当する場合は支払わない
    mode: str
    items: list[str]
    semantic_type: str = "exclusions"
    header: str = ""
    #: 各号に対応する入力名（根拠を入力に結びつける）
    item_inputs: list[str] = field(default_factory=list)


@dataclass
class FigureDraft:
    kind: str
    spec: Any
    normative: bool = True


@dataclass
class RuleDraft:
    """1 ルール分の下書き。表現（文・表・図）には触れない。"""

    pattern: str
    subject_key: str
    rule_id: str
    function: str
    title: str
    kind: str  # calculation / decision
    benefit: str
    trigger: str
    steps: list[StepDraft]
    inputs: dict[str, dict]
    output: dict
    #: 明細（1 行が 1 件の集合）。`agg` で集計する
    collections: dict[str, dict] = field(default_factory=dict)
    consts: list[ConstDraft] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)
    properties: list[dict] = field(default_factory=list)
    #: テスト入力を意味のある範囲に絞る条件（約款が前提にしている関係）
    preconditions: list[dict] = field(default_factory=list)
    table: TableDraft | None = None
    figure: FigureDraft | None = None
    enumeration: EnumerationDraft | None = None
    #: 設例の入力の候補（表記の衝突を避けるため複数用意する。値は仕様から計算する）
    example_sets: list[list[dict]] = field(default_factory=list)
    difficulty: dict = field(default_factory=dict)
    depends: list[str] = field(default_factory=list)
    #: 題材の語彙（設例の見出しなど）
    vocab: dict[str, str] = field(default_factory=dict)
    #: 追加先の章の分類
    anchor: str = "body"
    #: 同じ条にまとめて書くルール群のキー（判定＋金額など）
    group: str | None = None


class Pattern(Protocol):
    id: str
    title: str
    #: 使える種目（空なら全種目）
    genres: tuple[str, ...]

    def applicable(self, ctx: Context, subject: Subject) -> bool: ...

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]: ...


# ------------------------------------------------------------------ 補助
class PatternBase:
    id = "P00"
    title = ""
    genres: tuple[str, ...] = ()
    #: 題材が持っていなければならない入力の役割
    needs_inputs: tuple[str, ...] = ()
    #: 使うパラメータの役割（パックに値域が無ければ使えない）
    needs_params: tuple[str, ...] = ()

    def applicable(self, ctx: Context, subject: Subject) -> bool:
        if self.genres and ctx.genre not in self.genres:
            return False
        if self.id not in subject.patterns:
            return False
        if any(r not in subject.inputs for r in self.needs_inputs):
            return False
        for role in self.needs_params:
            if role not in subject.params and role not in ctx.pack.ranges:
                return False
        return True

    # ---- 共通の下請け ----
    def input_of(self, ctx: Context, subject: Subject, role: str) -> tuple[str, dict]:
        """題材の入力の役割 → (引数名, 入力仕様)。"""
        from ..core.packs import concepts

        spec = subject.inputs[role]
        concept = concepts()[spec["concept"]]
        desc = ctx.resolve_tokens(spec.get("desc") or concept.desc)
        out = concept.as_input(desc)
        for key in ("min", "max", "optional"):
            if key in spec:
                out[key] = spec[key]
        return concept.arg, out

    def const(
        self,
        ctx: Context,
        subject: Subject,
        role: str,
        rng: random.Random,
        *,
        per: str | None = None,
        **limits,
    ) -> ConstDraft:
        """パラメータを抽選して定数にする。`per` を渡すと単位が `<unit>/<per>` になる（日額など）。"""
        rng_range = ctx.pack.range_of(subject, role)
        value = rng_range.pick(rng, reject=ctx.reject_value, **limits)
        return ConstDraft.of(ctx.const_name(subject.key, role), value, rng_range.unit, per=per)

    def inside(self, spec: dict) -> dict:
        """しきい値・限度額を入力の値域の中に収める制約。

        値域の外に置くと、境界値のテストがその点に届かず、「以上／超える」の取り違えを
        見分けられなくなる（G7 の変異が残る）。
        """
        out: dict[str, int] = {}
        if "min" in spec:
            out["above"] = int(spec["min"])
        if "max" in spec:
            out["below"] = int(spec["max"])
        return out

    def safe_rates(self, ctx: Context, series: list[list[int]]) -> list[int]:
        """割合の列のうち、表記が既定の約款とぶつからない最初のものを選ぶ。"""
        from ..core import numbers_ja as nj

        return self.safe_series(ctx, series, nj.pct, "割合")

    def safe_series(self, ctx: Context, series, render, what: str = "表記"):
        """表に素で書く値の列から、既定の定数とぶつからない最初のものを選ぶ（本体 lint L11）。"""
        for cand in series:
            if not any(ctx.surface_clashes(render(v)) for v in cand):
                return cand
        raise PackError(f"{what}が既定の約款の定数とぶつかり、避けられる候補が無い")

    def _fit(self, spec: dict, value: int) -> int:
        """入力の値域に収める（設例の金額を限度額から決めるときに使う）。"""
        return max(int(spec.get("min", 0)), min(int(spec.get("max", 10**9)), value))

    def nice_amount(self, spec: dict, k: int = 0) -> int:
        """入力の値域の中から、設例に使えるきりのよい金額を選ぶ。"""
        lo, hi = int(spec.get("min", 0)), int(spec.get("max", 1_000_000))
        unit = 100_000 if hi >= 1_000_000 else 10_000
        v = ((lo + hi) // 2 // unit) * unit + k * unit
        return max(lo + unit, min(hi - unit, v)) if hi - lo > 2 * unit else (lo + hi) // 2

    def func(self, subject: Subject, suffix: str) -> str:
        return f"{subject.key}_{suffix}"

    def rule_id(self, subject: Subject, suffix: str) -> str:
        return f"{subject.key}.{suffix}"
