"""仕様からのテスト入力の生成。

  * 境界値: 入力と同じ単位を持つ定数・表キー・端数処理の単位の ±1、入力同士の大小関係の ±1。
  * 日付: 月末・うるう年・起算日（初日算入か翌日起算か）・「N 日以内」の前後。
  * 不明値: 入力を 1 つずつ `None` にして、三値の伝播を確かめる。
  * 性質: 範囲（0 以上・限度額以下）と単調性。条文から導ける不変条件。

期待値は参照インタプリタで計算する（`spec/interp.py` が意味論の正本）。
"""

from __future__ import annotations

import datetime as dt
import itertools
import random

from ..spec import interp
from ..spec.validate import RuleSet, input_unit

#: テストケースの種別と、その**ねらい**（DESIGN.md §11.3）。**唯一の正**。
#: 件数だけを持つ側（データカードなど）がねらいを引けるようにしてある。
KIND_NOTES: dict[str, str] = {
    "example": "約款の囲みに書いた設例。文書と仕様が一致していることを示す（**これだけ公開してよい**）",
    "boundary": "定数・表キー・端数処理の単位の ±1、入力同士の大小の ±1。以上と超える、限度額、表の段の境目",
    "unknown": "入力を 1 つずつ不明（`None`）にする。三値の伝播。採点から外せるよう種別を分けてある",
    "random": "宣言した値域からの乱数。全体の挙動",
}

#: 日付入力の既定の値域（約款の保険期間として自然な範囲。うるう年とその前後を含む）
DEFAULT_DATE_MIN = dt.date(2024, 1, 1)
DEFAULT_DATE_MAX = dt.date(2027, 12, 31)


def as_date(v) -> dt.date:
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(v)


def date_bounds(spec: dict) -> tuple[dt.date, dt.date]:
    lo = as_date(spec["min"]) if spec.get("min") else DEFAULT_DATE_MIN
    hi = as_date(spec["max"]) if spec.get("max") else DEFAULT_DATE_MAX
    return lo, hi


# ------------------------------------------------------------------ 入力生成
def _thresholds(rs: RuleSet, expr: dict) -> dict[str, set]:
    """式に現れる定数・表キー・注記つきリテラルを単位ごとに集める。"""
    out: dict[str, set] = {}

    def walk(e):
        if not isinstance(e, dict):
            return
        if "param" in e:
            p = rs.params[e["param"]]
            out.setdefault(p["unit"], set()).add(p["value"])
            # 端数処理の単位は「その倍数の前後」も境界になる（丸めの向きの誤りを見分ける）
            for k in (2, 3, 10):
                out.setdefault(p["unit"], set()).add(p["value"] * k)
        if e.get("op") == "lookup":
            t = rs.tables[e["table"]]
            out.setdefault(t["key_unit"], set()).update(k for k, *_ in t["rows"])
        for a in e.get("args", []):
            walk(a)

    walk(expr)
    return out


def _values(spec: dict, thresholds: dict[str, set], rng: random.Random) -> list:
    t = spec["type"]
    if t == "bool":
        return [True, False]
    if t == "str":
        return list(spec["values"])
    if t == "date":
        return _date_values(spec)
    lo, hi = spec.get("min", 0), spec.get("max", 10**6)
    vals = {lo, min(lo + 1, hi), hi, (lo + hi) // 2}
    for c in thresholds.get(input_unit(spec), ()):
        if isinstance(c, int):
            vals.update(v for v in (c - 1, c, c + 1) if lo <= v <= hi)
    out = sorted(vals)
    return out + [None] if spec.get("optional") else out  # 「記載なし」も値の 1 つ


def _date_values(spec: dict) -> list[dt.date]:
    lo, hi = date_bounds(spec)
    mid = lo + (hi - lo) // 2
    cands = [
        lo,
        lo + dt.timedelta(days=1),
        mid,
        interp.end_of_month(mid),
        interp.end_of_month(mid) + dt.timedelta(days=1),
        dt.date(2024, 2, 28),  # うるう年の前日
        dt.date(2024, 2, 29),  # うるう年の末日
        dt.date(2024, 3, 31),  # 月末（翌月に 31 日が無い）
        dt.date(2025, 1, 31),
        hi,
    ]
    return sorted({d for d in cands if lo <= d <= hi})


def _targeted_item_sets(coll: dict, thresholds: dict[str, set], field: str) -> list[list[dict]]:
    """合計が「しきい値ちょうど」になる明細の組を作る。

    `Σ min(明細, 1件ごとの限度) − 免責金額` が限度額の境目に乗る入力は、
    無作為に引いても当たらない。限度額を取り違えた実装を見分けるために、狙って作る。
    """
    spec = coll["fields"][field]
    lo, hi = int(spec.get("min", 0)), int(spec.get("max", 10**6))
    max_items = int(coll.get("max_items", 3))
    values = sorted(v for v in thresholds.get(input_unit(spec), ()) if isinstance(v, int) and v > 0)
    out: list[list[dict]] = []
    for target in values:
        for cap in values:
            if cap <= 0:
                continue
            for delta in (-1, 0, 1):
                want = target + delta
                k = -(-want // cap)
                if want <= 0 or k > max_items:
                    continue
                items = [cap] * (k - 1) + [want - cap * (k - 1)]
                if all(lo <= v <= hi for v in items):
                    out.append([{field: v} for v in items])
    return out[:120]


def _item_sets(coll: dict, thresholds, rng) -> list[list[dict]]:
    fields = {k: _values(v, thresholds, rng) for k, v in coll["fields"].items()}
    sets: list[list[dict]] = []
    lo, hi = coll.get("min_items", 0), coll.get("max_items", 3)
    if lo == 0:
        sets.append([])
    for _ in range(60):
        n = rng.randint(max(lo, 1), hi)
        sets.append([{k: rng.choice(v) for k, v in fields.items()} for _ in range(n)])
    for k, vs in fields.items():  # 各項目の各境界値を必ず 1 回は通す
        for v in vs:
            base = {f: rng.choice(x) for f, x in fields.items()}
            base[k] = v
            sets.append([base])
    top = {f: [v for v in x if not isinstance(v, bool | str)][-1:] or x for f, x in fields.items()}
    for combo in itertools.islice(itertools.product(*top.values()), 40):
        sets.append([dict(zip(top, combo, strict=False)) for _ in range(hi)])  # 合計が上限に届く集合
    for k in fields:  # 明細の 1 項目が不明
        base = {f: rng.choice(x) for f, x in fields.items()}
        sets.append([{**base, k: None}])
        sets.append([base, {**base, k: None}])
    if len(fields) == 1:
        sets += _targeted_item_sets(coll, thresholds, next(iter(fields)))
    return sets


def boundary_cases(rs: RuleSet, rule_id: str, expr: dict, seed: int = 7, n_pairwise: int = 400) -> list[dict]:
    r = rs.rules[rule_id]
    rng = random.Random(f"{seed}:{rule_id}")
    th = _thresholds(rs, expr)
    domains = {k: _values(v, th, rng) for k, v in r.get("inputs", {}).items()}
    colls = {k: _item_sets(v, th, rng) for k, v in r.get("collections", {}).items()}
    names = list(domains) + list(colls)
    space = {**domains, **colls}
    cases: list[dict] = []

    size = 1
    for v in space.values():
        size *= len(v)
    if size <= 3000:
        for combo in itertools.product(*(space[n] for n in names)):
            cases.append(dict(zip(names, combo, strict=False)))
    else:
        bases = [
            {n: space[n][len(space[n]) // 2] for n in names},
            {n: space[n][0] for n in names},
            {n: [v for v in space[n] if v is not None][-1] for n in names},
        ]
        for base in bases:  # 1 因子ずつ動かす
            for n in names:
                for v in space[n]:
                    cases.append({**base, n: v})
        for _ in range(n_pairwise):  # 境界値どうしの組合せを無作為に
            cases.append({n: rng.choice(space[n]) for n in names})

    cases += _relative_cases(rs, r, space, names, th, rng)
    known = list(cases[: max(40, len(cases) // 10)])
    for n in r.get("inputs", {}):  # 不明値を 1 つずつ注入
        for base in known[:25]:
            cases.append({**base, n: None})
    return _dedupe(_filter(rs, r, cases))


def _relative_cases(rs: RuleSet, r: dict, space, names, th, rng) -> list[dict]:
    """入力どうしの関係の境界（同単位の大小、日付の間隔が定数と一致する点）。"""
    out: list[dict] = []
    ints = [n for n, s in r.get("inputs", {}).items() if s["type"] == "int"]
    for a, b in itertools.permutations(ints, 2):
        sa, sb = r["inputs"][a], r["inputs"][b]
        if input_unit(sa) != input_unit(sb):
            continue
        for _ in range(6):
            base = {n: rng.choice(space[n]) for n in names}
            if base[b] is None or base.get(a) is None:
                continue
            for delta in (-1, 0, 1):
                v = base[b] + delta
                if sa.get("min", 0) <= v <= sa.get("max", 10**12):
                    out.append({**base, a: v})
    dates = [n for n, s in r.get("inputs", {}).items() if s["type"] == "date"]
    gaps = sorted(th.get("DAY", set()) | {0, 1})
    for a, b in itertools.permutations(dates, 2):
        lo, hi = date_bounds(r["inputs"][b])
        for _ in range(4):
            base = {n: rng.choice(space[n]) for n in names}
            if base[a] is None:
                continue
            for g in gaps:
                for delta in (-1, 0, 1):
                    v = as_date(base[a]) + dt.timedelta(days=g + delta)
                    if lo <= v <= hi:
                        out.append({**base, b: v})
    for a, b in itertools.permutations(dates, 2):  # 月末をまたぐ（add_months の丸め）
        lo, hi = date_bounds(r["inputs"][b])
        base = {n: rng.choice(space[n]) for n in names}
        for d in (dt.date(2024, 1, 31), dt.date(2024, 2, 29), dt.date(2025, 3, 31)):
            if lo <= d <= hi:
                out.append({**base, a: d})
    return out


def random_cases(rs: RuleSet, rule_id: str, n: int, seed: int = 11) -> list[dict]:
    r = rs.rules[rule_id]
    rng = random.Random(f"{seed}:{rule_id}")
    cases = []
    for _ in range(n):
        c = {}
        for k, s in r.get("inputs", {}).items():
            c[k] = _rand(s, rng)
            if rng.random() < 0.03:
                c[k] = None
        for k, coll in r.get("collections", {}).items():
            m = rng.randint(coll.get("min_items", 0), coll.get("max_items", 3))
            c[k] = [{f: _rand(s, rng) for f, s in coll["fields"].items()} for _ in range(m)]
        cases.append(c)
    return _filter(rs, r, cases)


def _rand(s: dict, rng: random.Random):
    if s["type"] == "bool":
        return rng.random() < 0.5
    if s["type"] == "str":
        return rng.choice(s["values"])
    if s["type"] == "date":
        lo, hi = date_bounds(s)
        return lo + dt.timedelta(days=rng.randint(0, (hi - lo).days))
    return rng.randint(s.get("min", 0), s.get("max", 10**6))


def _filter(rs: RuleSet, r: dict, cases: list[dict]) -> list[dict]:
    pre = r.get("preconditions", [])
    if not pre:
        return cases
    return [c for c in cases if all(interp._ev(rs, p, c, None) is not False for p in pre)]


def _key(c: dict) -> str:
    items = ((k, v.isoformat() if isinstance(v, dt.date) else v) for k, v in c.items())
    return repr(sorted(items, key=lambda kv: kv[0]))


def _dedupe(cases: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in cases:
        k = _key(c)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


# ------------------------------------------------------------------ 性質検査
def check_properties(rs: RuleSet, rule_id: str, expr: dict, cases: list[dict]) -> list[str]:
    r = rs.rules[rule_id]
    failures: list[str] = []
    for prop in r.get("properties", []):
        if prop["type"] == "range":
            for c in cases:
                y = interp._ev(rs, expr, c, None)
                if y is None:
                    continue
                lo = prop.get("min", rs.params[prop["min_param"]]["value"] if "min_param" in prop else None)
                hi = (
                    rs.params[prop["max_param"]]["value"]
                    if "max_param" in prop
                    else c.get(prop["max_var"])
                    if "max_var" in prop
                    else None
                )
                if (lo is not None and y < lo) or (hi is not None and y > hi):
                    failures.append(f"range 違反: {c} -> {y}")
                    break
        elif prop["type"] == "monotone":
            x, sign = prop["input"], 1 if prop["dir"] == "+" else -1
            hi = r["inputs"][x].get("max", 10**12)
            for c in cases:
                if c.get(x) is None or c[x] + 1 > hi:
                    continue
                y0 = interp._ev(rs, expr, c, None)
                y1 = interp._ev(rs, expr, {**c, x: c[x] + 1}, None)
                if y0 is None or y1 is None:
                    continue
                if sign * (y1 - y0) < 0:
                    failures.append(f"monotone 違反（{x}）: {c} -> {y0}, +1 -> {y1}")
                    break
    return failures


# ---------------------------------------------------------------- 変異を落とす探索
def kill_search(
    rs: RuleSet,
    rule_id: str,
    expr: dict,
    mutant: dict,
    bases: list[dict],
    sweep: int = 20_000,
    draws: int = 40_000,
    seed: int = 97,
) -> dict | None:
    """ある変異だけを見分ける入力を探す。

    すべての入力をいっぺんに振るより、**1 つの入力を連続した値で掃く**方が確実に当たる。
    端数処理の向きの違いは「丸めの境目に 1 円差で乗ったとき」にしか現れないので、
    まず無作為に広く引き（当たる確率は丸めの単位の逆数で、単位が大きくても引数を増やせば届く）、
    次に連続して掃く（定数の ±1 のように、特定の値のまわりでしか現れない差を拾う）。
    """
    r = rs.rules[rule_id]
    rng = random.Random(f"{seed}:{rule_id}:kill")
    # 値域の広い入力から掃く（丸めの境目は金額のような広い入力に現れる）
    ints = sorted(
        (n for n, s in r.get("inputs", {}).items() if s["type"] == "int"),
        key=lambda n: -(int(r["inputs"][n].get("max", 10**6)) - int(r["inputs"][n].get("min", 0))),
    )
    if not ints or not bases:
        return None

    def differs(c: dict) -> bool:
        if any(v is None for v in c.values()):
            return False
        return interp._ev(rs, expr, c, None) != interp._ev(rs, mutant, c, None)

    # まず全部の数値入力をいっぺんに振る。表引きの段と丸めの境目が同時に要る差は、
    # 1 入力ずつ振っても当たらない（段が固定されたままになるため）。
    for base in bases[:2]:
        for _ in range(draws):
            c = dict(base)
            for name in ints:
                spec = r["inputs"][name]
                c[name] = rng.randint(int(spec.get("min", 0)), int(spec.get("max", 10**6)))
            if differs(c):
                return c
    for base in bases[:4]:
        for name in ints:
            spec = r["inputs"][name]
            lo, hi = int(spec.get("min", 0)), int(spec.get("max", 10**6))
            if hi <= lo:
                continue
            for _ in range(draws):
                c = {**base, name: rng.randint(lo, hi)}
                if differs(c):
                    return c
            width = min(sweep, hi - lo + 1)
            start_v = rng.randint(lo, max(lo, hi - width + 1))
            for v in range(start_v, start_v + width):
                c = {**base, name: v}
                if differs(c):
                    return c
    return None
