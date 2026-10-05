"""パターンの選択と衝突回避（DESIGN.md §8.4）。

- 適用できるパターン（genre 一致・同じ事項が既定の契約書に無い）から、文書ごとの乱数で選ぶ。
- MUTEX（同じ事項の二重定義になる組）は同時に選ばない。
- REQUIRES（他のパターンの選択が前提）のものは、前提が選ばれているときだけ選ぶ。
- 選択は ID 順に安定化してから乱数で並べ替える（パターンを足しても既存の選択が変わらない）。
"""

from __future__ import annotations

from random import Random

from ..patterns.base import PatternDef
from ..patterns.registry import MUTEX, REQUIRES, all_patterns


def applicable_patterns(ctx) -> list[PatternDef]:
    return sorted((p for p in all_patterns() if p.applicable(ctx)), key=lambda p: p.id)


def select_patterns(
    ctx, rng: Random, min_rules: int, max_rules: int, exclude_ids: set[str] | None = None
) -> tuple[list[PatternDef], list[str]]:
    """選んだパターンと、注記（下限に満たない等）を返す。"""
    notes: list[str] = []
    pool = [p for p in applicable_patterns(ctx) if p.id not in (exclude_ids or set())]
    target = rng.randint(min_rules, max_rules)
    order = list(pool)
    rng.shuffle(order)

    chosen: list[PatternDef] = []
    chosen_ids: set[str] = set()

    def conflicts(pid: str) -> bool:
        return any(pid in group and (group - {pid}) & chosen_ids for group in MUTEX)

    # 2 周する：1 周目で前提の無いもの、2 周目で REQUIRES を満たせるもの。
    # 依存パターン（REQUIRES）は前提が選ばれたときにしか出番が無いので、
    # 2 周目に限り rules_max までの枠で追加を許す。
    for round_no in (1, 2):
        for p in order:
            needs = REQUIRES.get(p.id)
            limit = max_rules if (round_no == 2 and needs) else target
            if len(chosen) >= limit or p.id in chosen_ids or conflicts(p.id):
                continue
            if needs and not (set(needs) & chosen_ids):
                continue
            chosen.append(p)
            chosen_ids.add(p.id)

    if len(chosen) < min_rules:
        notes.append(
            f"適用できるパターンが下限に満たない（{len(chosen)} 件 < {min_rules} 件）。"
            f"適用可能: {[p.id for p in pool]}"
        )
    if not chosen:
        raise ValueError(f"{ctx.doctype}: 適用できるパターンが無い")
    chosen.sort(key=lambda p: p.id)
    return chosen, notes
