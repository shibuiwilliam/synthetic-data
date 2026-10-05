"""計算仕様（CalcSpec）のデータ型。

トップレベルの構造は dataclass で持つ。式（expr）は閉じた演算集合の木で、JSON のまま持ち、
`validate.py` が構造と型を検査し、`interp.py` が意味論の正本として評価する。
式の形は DESIGN.md §12.1・§12.2 のとおり：

- 葉: {"lit": int|bool|"YYYY-MM-DD"} / {"var": 入力名} / {"param": 定数名} /
      {"step": 手順名} / {"item": true}（agg の中でだけ使える現在要素）
- 節: {"op": "...", "args": [...]} ＋ 演算ごとの属性
      （muldiv/round_to は rounding、lookup/tiered は table、period_end は unit と include_start）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SPEC_VERSION = "0.1"

#: 演算の閉じた集合（DESIGN.md §12.2）。これ以外は validate が落とす。
OPS_ARITH = frozenset({"add", "sub", "mul", "muldiv", "round_to", "min", "max"})
OPS_CMP = frozenset({"lt", "le", "gt", "ge", "eq", "ne"})
OPS_LOGIC = frozenset({"and", "or", "not"})
OPS_COND = frozenset({"if", "case", "coalesce"})
OPS_TABLE = frozenset({"lookup", "tiered"})
OPS_LIST = frozenset({"agg"})
OPS_DATE = frozenset(
    {
        "add_days",
        "add_months",
        "end_of_month",
        "set_day",
        "period_end",
        "days_between",
        "days_in_month",
        "is_business_day",
        "next_business_day",
        "prev_business_day",
        "add_business_days",
    }
)
ALL_OPS = OPS_ARITH | OPS_CMP | OPS_LOGIC | OPS_COND | OPS_TABLE | OPS_LIST | OPS_DATE

#: 営業日を使う演算（spec.calendar の宣言が必須になる）
BUSINESS_DAY_OPS = frozenset(
    {"is_business_day", "next_business_day", "prev_business_day", "add_business_days"}
)

ROUNDINGS = frozenset({"floor", "ceil", "half_up"})
INPUT_ORIGINS = frozenset({"order", "fact", "notice", "judgment", "external"})
VALUE_TYPES = frozenset({"int", "ratio", "bool", "enum", "date", "list"})

#: 演算 → 仕様に書かれていなければならない明示事項のキー（G3 の仕様側）
OBLIGATION_BY_OP = {
    "muldiv": "rounding",
    "round_to": "rounding",
    "tiered": "tier_method",
    "add_business_days": "business_days",
    "next_business_day": "business_days",
    "prev_business_day": "business_days",
    "is_business_day": "business_days",
    "days_between": "day_count",
    "period_end": "period_count",
}


@dataclass(frozen=True)
class SourceRef:
    """根拠。unit は契約書JSONの単位 ID、quote は紙面の逐語の文字列。"""

    unit: str
    quote: str

    @classmethod
    def from_dict(cls, d: dict) -> SourceRef:
        return cls(unit=d["unit"], quote=d["quote"])

    def to_dict(self) -> dict:
        return {"unit": self.unit, "quote": self.quote}


@dataclass(frozen=True)
class Param:
    """契約書に書かれた定数。surface は紙面の表記、source は根拠。"""

    name: str
    type: str  # int / ratio / date / enum
    value: Any = None  # int は整数、date は "YYYY-MM-DD"、enum は文字列
    num: int | None = None  # ratio の分子
    den: int | None = None  # ratio の分母
    unit: str | None = None  # JPY / DAY / MONTH / HOUR / MIN / COUNT / JPY/HOUR など
    surface: str | None = None
    source: SourceRef | None = None

    @classmethod
    def from_dict(cls, name: str, d: dict) -> Param:
        return cls(
            name=name,
            type=d["type"],
            value=d.get("value"),
            num=d.get("num"),
            den=d.get("den"),
            unit=d.get("unit"),
            surface=d.get("surface"),
            source=SourceRef.from_dict(d["source"]) if d.get("source") else None,
        )


@dataclass(frozen=True)
class TableRow:
    """段階表の 1 行。upto=None は「それ以上すべて」。"""

    upto: int | None
    value: int


@dataclass(frozen=True)
class SpecTable:
    """参照表。kind: "tiers"（段階）または "map"（一致）。"""

    name: str
    kind: str
    rows: tuple[TableRow, ...]
    unit: str | None = None
    source: SourceRef | None = None

    @classmethod
    def from_dict(cls, name: str, d: dict) -> SpecTable:
        rows = tuple(TableRow(upto=r.get("upto"), value=r["value"]) for r in d["rows"])
        return cls(
            name=name,
            kind=d.get("kind", "tiers"),
            rows=rows,
            unit=d.get("unit"),
            source=SourceRef.from_dict(d["source"]) if d.get("source") else None,
        )


@dataclass(frozen=True)
class InputDecl:
    """関数の入力。契約書に値が無いもの（事実・個別契約・通知・評価・外部）だけが入力になる。"""

    name: str
    type: str
    unit: str | None = None
    origin: str = "fact"
    desc: str = ""
    optional: bool = False  # True なら None 既定で、coalesce で既定値に落とす
    min: Any = None  # int または "YYYY-MM-DD"
    max: Any = None
    values: tuple[str, ...] = ()  # enum の候補
    item_unit: str | None = None  # list の要素の単位

    @classmethod
    def from_dict(cls, name: str, d: dict) -> InputDecl:
        return cls(
            name=name,
            type=d["type"],
            unit=d.get("unit"),
            origin=d.get("origin", "fact"),
            desc=d.get("desc", ""),
            optional=d.get("optional", False),
            min=d.get("min"),
            max=d.get("max"),
            values=tuple(d.get("values", ())),
            item_unit=d.get("item_unit"),
        )


@dataclass(frozen=True)
class Step:
    """名前つきの手順。1 手順が文・表の行・図のノードの 1 つに対応する。"""

    name: str
    label: str
    expr: dict


@dataclass(frozen=True)
class Example:
    """設例。oracle: "manual"（手で検算した値）。"""

    inputs: dict
    expect: Any
    oracle: str = "manual"
    holidays: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rule:
    """1 つの計算・判定ルール。"""

    id: str
    title: str
    kind: str  # calculation / determination
    origin: str  # added / bound
    interface: dict
    inputs: dict[str, InputDecl]
    steps: tuple[Step, ...]
    output: dict  # {"step": name, "type": ..., "unit": ...}
    parties: dict | None = None  # {"payer": "乙", "payee": "甲"}
    obligations: tuple[str, ...] = ()
    presentation: dict = field(default_factory=dict)
    sources: tuple[SourceRef, ...] = ()
    properties: tuple[dict, ...] = ()
    examples: tuple[Example, ...] = ()
    difficulty: dict = field(default_factory=dict)
    challenge: dict | None = None  # challenge モードのラベル（例 {"type": "omission", "aspect": "rounding"}）

    @property
    def function(self) -> str:
        return self.interface["function"]

    @classmethod
    def from_dict(cls, d: dict) -> Rule:
        return cls(
            id=d["id"],
            title=d["title"],
            kind=d["kind"],
            origin=d.get("origin", "added"),
            interface=d["interface"],
            inputs={k: InputDecl.from_dict(k, v) for k, v in d.get("inputs", {}).items()},
            steps=tuple(Step(s["name"], s.get("label", s["name"]), s["expr"]) for s in d["steps"]),
            output=d["output"],
            parties=d.get("parties"),
            obligations=tuple(d.get("obligations", ())),
            presentation=d.get("presentation", {}),
            sources=tuple(SourceRef.from_dict(s) for s in d.get("sources", ())),
            properties=tuple(d.get("properties", ())),
            examples=tuple(
                Example(
                    inputs=e["inputs"],
                    expect=e.get("expect"),
                    oracle=e.get("oracle", "manual"),
                    holidays=tuple(e.get("holidays", ())),
                )
                for e in d.get("examples", ())
            ),
            difficulty=d.get("difficulty", {}),
            challenge=d.get("challenge"),
        )


@dataclass(frozen=True)
class CalendarDef:
    """契約書に書かれた営業日の定義。祝日は常に入力（holidays）。"""

    weekend: tuple[str, ...] = ("SAT", "SUN")
    closed: tuple[tuple[tuple[int, int], tuple[int, int]], ...] = ()
    source: SourceRef | None = None

    @classmethod
    def from_dict(cls, d: dict) -> CalendarDef:
        closed = tuple(
            (
                (int(a.split("-")[0]), int(a.split("-")[1])),
                (int(b.split("-")[0]), int(b.split("-")[1])),
            )
            for a, b in d.get("closed", ())
        )
        return cls(
            weekend=tuple(d.get("weekend", ("SAT", "SUN"))),
            closed=closed,
            source=SourceRef.from_dict(d["source"]) if d.get("source") else None,
        )


@dataclass(frozen=True)
class CalcSpec:
    """1 文書の計算仕様（唯一の正）。"""

    spec_version: str
    document: dict
    params: dict[str, Param]
    tables: dict[str, SpecTable]
    rules: tuple[Rule, ...]
    calendar: CalendarDef | None = None

    @classmethod
    def from_dict(cls, d: dict) -> CalcSpec:
        return cls(
            spec_version=d.get("spec_version", SPEC_VERSION),
            document=d.get("document", {}),
            params={k: Param.from_dict(k, v) for k, v in d.get("params", {}).items()},
            tables={k: SpecTable.from_dict(k, v) for k, v in d.get("tables", {}).items()},
            rules=tuple(Rule.from_dict(r) for r in d.get("rules", ())),
            calendar=CalendarDef.from_dict(d["calendar"]) if d.get("calendar") else None,
        )

    def rule(self, rule_id: str) -> Rule:
        for r in self.rules:
            if r.id == rule_id:
                return r
        raise KeyError(rule_id)
