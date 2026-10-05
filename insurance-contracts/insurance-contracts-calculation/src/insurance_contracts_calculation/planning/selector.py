"""パターンの選択と衝突回避。

乱数は**ルールごとに独立**にする（`Random(f"{cid}:{seed}:{subject}:{pattern}")`）。
パターンを足しても、ほかのルールの出力が変わらないようにするためである（DESIGN.md §13）。
選ぶ順序も、通し番号ではなく (題材, パターン) ごとのくじ（ハッシュ）で決める。
"""

from __future__ import annotations

import functools
import hashlib
import random
from dataclasses import dataclass, field

from ..config import Settings
from ..core.packs import PackError, Subject
from ..patterns import registry
from ..patterns.base import Pattern, RuleDraft
from .context import Context


@dataclass
class Plan:
    """1 文書分の計画（題材とパターンの組の並び）。

    `items` は**候補の全部**を優先順に並べたもの、`want` は目標のルール数である。
    下書きの段階で落ちた題材があっても、次の候補で埋められるようにしてある。
    """

    items: list[tuple[Subject, Pattern]]
    skipped: list[tuple[str, str]]
    want: int = 0
    #: 実際に採用した組（`sample` が埋める）
    used: list[tuple[Subject, Pattern]] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.used or self.items)


def _ticket(*parts: str) -> str:
    return hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()


def _unit(*parts: str) -> float:
    """くじの番号を [0,1) の実数にする（決定的。`random` を使わない）。"""
    return int(_ticket(*parts)[:16], 16) / float(1 << 64)


#: 宿主（そのパターンを挙げている題材）の数が少ないパターンに重みを付ける指数。
#: 重みづけをしないと、出現数が宿主の数にほぼ比例してしまう
#: （v1.2 の実測: `P07` 宿主 9 → 16 件、`P18` 宿主 1 → 1 件、`P11` 宿主 2 → 0 件）。
#: 重みはパックだけから決まるので、文書や seed には依存しない（ほかの題材に響かない）。
#:
#: 値は実測で決めた。43 文書の計画段階で数えた「18 種すべてが出て、最小が 3 件以上」になる
#: 最小の指数が 1.0 である（0.0 では `P13` 1 件・`P18` 4 件、1.4 まで上げると `P01` が 22→10 件まで
#: 削られる）。大きくするほど希少なパターンが増え、`P01` のような基本のパターンが減る。
RARITY_EXPONENT = 1.0


def _hosts() -> dict[str, int]:
    """全パックを通して、各パターンを挙げている題材の数。"""
    from ..core.packs import available, load

    counts: dict[str, int] = {}
    for genre in available():
        for subject in load(genre).subjects:
            for pid in subject.patterns:
                counts[pid] = counts.get(pid, 0) + 1
    return counts


@functools.cache
def pattern_weights() -> dict[str, float]:
    """パターンごとのくじの重み。宿主が少ないほど大きい。"""
    hosts = _hosts()
    if not hosts:
        return {}
    most = max(hosts.values())
    return {pid: (most / n) ** RARITY_EXPONENT for pid, n in hosts.items()}


def _pick_pattern(ctx: Context, seed: int, subject: Subject, usable: list[Pattern]) -> Pattern:
    """題材が挙げている複数のパターンから 1 つ選ぶ（重みつきのくじ）。

    `u ** (1/w)` が最大のものを選ぶと、採用される確率が `w` に比例する
    （指数競走。`random` を使わないので、同じ入力なら必ず同じ結果になる）。
    """
    weights = pattern_weights()

    def score(p: Pattern) -> tuple[float, str]:
        u = _unit(ctx.content_id, str(seed), subject.key, p.id)
        w = weights.get(p.id, 1.0)
        # u=0 のときは最弱にせず、くじの番号そのもので決める（同点は id の順）
        return (u ** (1.0 / w) if u > 0.0 else 0.0, p.id)

    return max(usable, key=score)


def rule_rng(ctx: Context, seed: int, subject: Subject, pattern: Pattern) -> random.Random:
    """ルールごとに独立した乱数列。"""
    return random.Random(f"{ctx.content_id}:{seed}:{subject.key}:{pattern.id}")


def presentation_rng(ctx: Context, seed: int, subject: Subject, pattern: Pattern) -> random.Random:
    """表現手段の割当に使う乱数列（パラメータの抽選とは別にする）。"""
    return random.Random(f"{ctx.content_id}:{seed}:presentation:{subject.key}:{pattern.id}")


def plan(ctx: Context, seed: int, settings: Settings) -> Plan:
    """題材とパターンを選ぶ。選べなかった理由も返す（黙って外さない）。"""
    skipped: list[tuple[str, str]] = []
    candidates: list[tuple[str, Subject, Pattern]] = []
    for subject in ctx.pack.subjects:
        ok, why = ctx.subject_applicable(subject)
        if not ok:
            skipped.append((subject.key, why))
            continue
        usable = []
        for pid in subject.patterns:
            if pid not in registry.BY_ID:
                skipped.append((f"{subject.key}/{pid}", "パターンが未実装"))
                continue
            pattern = registry.BY_ID[pid]
            if not pattern.applicable(ctx, subject):
                skipped.append((f"{subject.key}/{pid}", "このパターンは題材・種目に合わない"))
                continue
            clash = [
                f"{subject.key}_{role}"
                for role in pattern.needs_params
                if f"{subject.key}_{role}" in ctx.constants
            ]
            if clash:
                skipped.append((f"{subject.key}/{pid}", f"定数名が既定の約款と衝突: {', '.join(clash)}"))
                continue
            usable.append(pattern)
        if not usable:
            skipped.append((subject.key, "使えるパターンが無い"))
            continue
        # 題材ごとに 1 パターン。くじで選ぶのでパターンを足しても他の題材に響かない。
        # 宿主の少ないパターンに重みを付ける（`pattern_weights`）
        pattern = _pick_pattern(ctx, seed, subject, usable)
        # 並び順は題材だけで決める（パターンの希少さで前に寄せると、`rule_limit` で切る組み直しの
        # たびに文書の中身が総入れ替えになり、基準の文書と対になる `examples/wrong_impl.py` が
        # 当たらなくなる。希少さの補正はパターンのくじ（`_pick_pattern`）だけで行う）
        candidates.append((_ticket(ctx.content_id, str(seed), "pick", subject.key), subject, pattern))

    candidates.sort(key=lambda x: x[0])
    want = _target_count(ctx, seed, settings, len(candidates))
    # 控えも持っておく。下書きの段階で落ちた題材のぶんは、次の候補で埋める
    return Plan([(s, p) for _t, s, p in candidates], skipped, want)


def _target_count(ctx: Context, seed: int, settings: Settings, available: int) -> int:
    lo, hi = settings.profile.rules_min, settings.profile.rules_max
    rng = random.Random(f"{ctx.content_id}:{seed}:count")
    want = rng.randint(lo, hi)
    if settings.rule_limit is not None:
        want = min(want, settings.rule_limit)
    return min(want, available)


def sample(ctx: Context, seed: int, plan_: Plan) -> list[list[RuleDraft]]:
    """計画どおりに下書きを作る。1 要素 = 1 つの条にまとめるルール群。"""
    groups: list[list[RuleDraft]] = []
    plan_.used = []
    for subject, pattern in plan_.items:
        if len(groups) >= plan_.want:
            plan_.skipped.append((subject.key, "ルール数の上限に達した"))
            continue
        rng = rule_rng(ctx, seed, subject, pattern)
        try:
            drafts = pattern.sample(ctx, subject, rng)
        except PackError as e:
            # 値域の制約や名前の衝突で作れない題材は、文書ごと落とさずに外して記録する
            plan_.skipped.append((f"{subject.key}/{pattern.id}", str(e)))
            continue
        ctx.reserve_benefit(subject.benefit)
        plan_.used.append((subject, pattern))
        groups.append(drafts)
    return groups
