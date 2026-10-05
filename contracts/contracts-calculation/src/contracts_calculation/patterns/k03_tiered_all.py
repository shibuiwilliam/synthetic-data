"""K03 段階料金（全量方式）：数量が属する区分の単価を全量に掛ける。"""

from __future__ import annotations

from ._tiered_common import sample_tiered
from .base import PatternDef


def _sample(ctx, rng):
    return sample_tiered(ctx, rng, "all_units")


PATTERN = PatternDef(
    id="K03",
    title="段階料金（全量方式）",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "purchase"}),
    topics=("処理手数料",),
    sampler=_sample,
)
