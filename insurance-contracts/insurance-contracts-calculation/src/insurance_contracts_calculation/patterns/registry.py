"""パターンの登録簿。IDの小さい順に並べる（選択の決定性のため）。"""

from __future__ import annotations

from .base import Pattern
from .p01_limit import P01Limit
from .p02_deductible import P02Deductible
from .p03_per_diem import P03PerDiem
from .p04_grade_table import P04GradeTable
from .p05_step_table import P05StepTable
from .p06_proration import P06Proration
from .p07_cases import P07Cases
from .p08_frames import P08Frames
from .p09_itemized import P09Itemized
from .p10_deadline import P10Deadline
from .p11_count import P11Count
from .p12_decision import P12Decision
from .p13_override import P13Override
from .p14_flowchart import P14Flowchart
from .p15_composite import P15Composite
from .p16_cumulative import P16Cumulative
from .p17_declining import P17Declining
from .p18_waiting import P18Waiting

ALL: tuple[Pattern, ...] = (
    P01Limit(),
    P02Deductible(),
    P03PerDiem(),
    P04GradeTable(),
    P05StepTable(),
    P06Proration(),
    P07Cases(),
    P08Frames(),
    P09Itemized(),
    P10Deadline(),
    P11Count(),
    P12Decision(),
    P13Override(),
    P14Flowchart(),
    P15Composite(),
    P16Cumulative(),
    P17Declining(),
    P18Waiting(),
)

BY_ID = {p.id: p for p in ALL}


def get(pattern_id: str) -> Pattern:
    if pattern_id not in BY_ID:
        raise KeyError(f"知らないパターン: {pattern_id}")
    return BY_ID[pattern_id]
