"""K04 段階料金（超過分方式）：区分ごとの超過分にそれぞれの単価を掛けて合計する。"""

from __future__ import annotations

from ._tiered_common import sample_tiered
from .base import PatternDef


def _sample(ctx, rng):
    return sample_tiered(ctx, rng, "marginal")


PATTERN = PatternDef(
    id="K04",
    title="段階料金（超過分方式）",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "purchase"}),
    topics=("処理手数料",),
    sampler=_sample,
)
