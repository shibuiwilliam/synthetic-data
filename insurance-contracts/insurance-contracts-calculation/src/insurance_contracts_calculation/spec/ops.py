"""演算の一覧（意味論・型検査・コード生成・テスト生成・逆翻訳の共通の台帳）。

演算を足すときは、まずここに 1 行足す。`tests/unit/test_ops_coverage.py` が
「台帳にあるすべての演算が 5 モジュールで扱われている」ことを確かめるので、
どれか 1 つを直し忘れると落ちる（`CLAUDE.md`「演算や型を足すとき」）。

| 欄 | 意味 |
|---|---|
| `arity` | 引数の個数 `(最小, 最大)`。`-1` は可変 |
| `strict` | 引数に不明（`None`）があれば結果も不明。`False` のものは演算ごとに意味論を書く |
| `group` | 検査と文型の振り分けに使う種別 |
| `attrs` | 式の辞書に必要な追加キー（`rounding` など） |
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: 端数処理の方向。必ず明示する（省略を許すと解釈が割れる）
ROUNDINGS = ("floor", "ceil", "half_up")

#: 原子的な単位（加減乗除できない型）
ATOMIC_KINDS = frozenset({"BOOL", "STR", "DATE", "YM", "GRADE", "CLASS"})

#: 加減算で「絶対量 ± 差分」となる単位の対応
AFFINE = {"DATE": "DAY", "YM": "MONTH"}


@dataclass(frozen=True)
class OpDef:
    name: str
    arity: tuple[int, int]
    strict: bool
    group: str
    doc: str
    attrs: tuple[str, ...] = field(default_factory=tuple)


def _op(name: str, arity: tuple[int, int], strict: bool, group: str, doc: str, attrs: tuple = ()) -> OpDef:
    return OpDef(name, arity, strict, group, doc, attrs)


OPS: dict[str, OpDef] = {
    o.name: o
    for o in (
        # ---- 算術 -------------------------------------------------------
        _op("add", (2, -1), True, "arith", "合計"),
        _op("sub", (2, 2), True, "arith", "差引"),
        _op("mul", (2, -1), True, "arith", "乗算"),
        _op("muldiv", (3, 3), True, "arith", "a×b÷c（端数処理を明示）", ("rounding",)),
        _op("min", (2, -1), True, "arith", "いずれか低い額"),
        _op("max", (2, -1), True, "arith", "いずれか高い額"),
        _op("round_to", (2, 2), True, "round", "単位で丸める（端数処理を明示）", ("rounding",)),
        # ---- 比較 -------------------------------------------------------
        _op("lt", (2, 2), True, "cmp", "未満"),
        _op("le", (2, 2), True, "cmp", "以下"),
        _op("gt", (2, 2), True, "cmp", "を超える"),
        _op("ge", (2, 2), True, "cmp", "以上"),
        _op("eq", (2, 2), True, "cmp", "等しい"),
        _op("ne", (2, 2), True, "cmp", "等しくない"),
        # ---- 論理（Kleene の三値） ---------------------------------------
        _op("and", (2, -1), False, "logic", "次のすべてに該当"),
        _op("or", (2, -1), False, "logic", "次のいずれかに該当"),
        _op("not", (1, 1), True, "logic", "該当しない"),
        # ---- 制御 -------------------------------------------------------
        _op("if", (3, 3), False, "ctrl", "場合分け（条件が不明なら不明）"),
        _op("coalesce", (2, 2), False, "ctrl", "記載がなければ既定値"),
        # ---- 表・明細 ---------------------------------------------------
        _op("lookup", (1, 1), True, "table", "表引き（表にないキーは不明）", ("table",)),
        _op("agg", (1, 1), True, "agg", "明細ごとの集計", ("func", "over")),
        # ---- 日付 -------------------------------------------------------
        _op("add_days", (2, 2), True, "date", "日付に日数を加える"),
        _op("add_months", (2, 2), True, "date", "日付に月数を加える（月末は丸める）"),
        _op("days_between", (2, 2), True, "date", "2 つの日付の間の日数（後−前）"),
        _op("end_of_month", (1, 1), True, "date", "その日の属する月の末日"),
    )
}

ARITH = frozenset(o.name for o in OPS.values() if o.group in ("arith", "round"))
CMP = frozenset(o.name for o in OPS.values() if o.group == "cmp")
LOGIC = frozenset(o.name for o in OPS.values() if o.group == "logic")
DATE_OPS = frozenset(o.name for o in OPS.values() if o.group == "date")
STRICT = frozenset(o.name for o in OPS.values() if o.strict)

#: 式の原子（演算ではない節）
ATOMS = ("lit", "param", "var", "item", "step", "rule")


def check_shape(e: dict) -> str | None:
    """式 1 節の形（演算名・引数の数・必須キー）を検査する。問題があれば日本語で返す。"""
    if any(k in e for k in ATOMS):
        return None
    op = e.get("op")
    if op not in OPS:
        return f"未知の演算 {op!r}"
    d = OPS[op]
    n = len(e.get("args", []))
    lo, hi = d.arity
    if n < lo or (hi != -1 and n > hi):
        want = f"{lo}" if lo == hi else (f"{lo}以上" if hi == -1 else f"{lo}〜{hi}")
        return f"{op} の引数は{want}個でなければならない（{n}個）"
    for a in d.attrs:
        if a not in e:
            return f"{op} には {a} の指定が必要"
    if "rounding" in d.attrs and e["rounding"] not in ROUNDINGS:
        return f"{op} の端数処理 {e['rounding']!r} は {'/'.join(ROUNDINGS)} のいずれかでなければならない"
    return None


def walk(e: dict):
    """式の節を前順に辿る。"""
    if not isinstance(e, dict):
        return
    yield e
    for a in e.get("args", []):
        yield from walk(a)
