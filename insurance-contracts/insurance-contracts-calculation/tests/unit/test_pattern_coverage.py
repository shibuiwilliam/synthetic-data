"""パターンの網羅（S9-1）。

パターンは 18 種あるが、出現数は「宿主（そのパターンを挙げている題材）の数」にほぼ比例する。
重みづけをしないと、宿主 1 件のパターンは一括生成に 1 度も出てこない
（v1.2 の実測: `P11` 宿主 2 → 0 件）。ここで守るのは 2 つ。

1. どのパターンにも宿主が 2 件以上あり、2 つ以上の種目にまたがること
2. 希少なパターンに重みが付いていること（題材が複数挙げるときのくじ）
"""

from __future__ import annotations

import collections

from insurance_contracts_calculation.core import packs
from insurance_contracts_calculation.patterns import registry
from insurance_contracts_calculation.planning import selector

#: 1 つのパターンに最低限必要な宿主の数。これを下回ると一括生成から消えうる
MIN_HOSTS = 2


def _hosts() -> dict[str, list[str]]:
    out: dict[str, list[str]] = collections.defaultdict(list)
    for genre in packs.available():
        for subject in packs.load(genre).subjects:
            for pid in subject.patterns:
                out[pid].append(f"{genre}:{subject.key}")
    return out


def test_every_pattern_has_hosts_in_more_than_one_genre() -> None:
    hosts = _hosts()
    thin = {
        p.id: hosts.get(p.id, [])
        for p in registry.ALL
        if len(hosts.get(p.id, [])) < MIN_HOSTS or len({h.split(":")[0] for h in hosts.get(p.id, [])}) < 2
    }
    assert not thin, f"宿主が足りないパターン（一括生成から消えうる）: {thin}"


def test_hosts_only_name_implemented_patterns() -> None:
    unknown = {pid: hs for pid, hs in _hosts().items() if pid not in registry.BY_ID}
    assert not unknown, f"パックが未実装のパターンを挙げている: {unknown}"


def test_the_lottery_favours_the_rare_patterns() -> None:
    """宿主が少ないパターンほど重みが大きい。"""
    hosts = _hosts()
    weights = selector.pattern_weights()
    assert set(weights) == set(hosts), "重みの対象がパックと合っていない"
    ranked = sorted(weights, key=lambda p: weights[p])
    counts = [len(hosts[p]) for p in ranked]
    assert counts == sorted(counts, reverse=True), f"重みの順が宿主の数の逆順になっていない: {ranked}"
