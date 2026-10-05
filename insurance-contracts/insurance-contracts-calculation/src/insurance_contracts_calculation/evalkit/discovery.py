"""「発見」の採点（DESIGN.md §10.4・§11.4）。

正解表の `units`（規範の根拠）に対する再現率と適合率で測る。
`explanatory_units`（設例など説明側）は採点に含めない。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiscoveryScore:
    recall: float
    precision: float
    f1: float
    matched: int
    expected: int
    predicted: int
    per_rule: dict[str, dict]


def score(answer: list[dict], submission: list[dict]) -> DiscoveryScore:
    """`submission` は `[{"function": ..., "units": [...]}, ...]` の形。

    対応づけは**関数名**で行う（内部IDは評価に使わない。TASK.md §3-2）。
    """
    gold = {a["function"]: set(a["units"]) for a in answer}
    pred = {s.get("function"): set(s.get("units") or []) for s in submission}
    per_rule: dict[str, dict] = {}
    tp = fp = fn = 0
    for fname, units in gold.items():
        got = pred.get(fname, set())
        hit = units & got
        tp += len(hit)
        fn += len(units - got)
        fp += len(got - units)
        per_rule[fname] = {
            "recall": _ratio(len(hit), len(units)),
            "precision": _ratio(len(hit), len(got)),
            "missing": sorted(units - got),
            "extra": sorted(got - units),
        }
    for fname, got in pred.items():
        if fname not in gold:
            fp += len(got)
            per_rule[str(fname)] = {"recall": 0.0, "precision": 0.0, "missing": [], "extra": sorted(got)}
    recall = _ratio(tp, tp + fn)
    precision = _ratio(tp, tp + fp)
    f1 = 0.0 if recall + precision == 0 else 2 * recall * precision / (recall + precision)
    return DiscoveryScore(recall, precision, f1, tp, tp + fn, tp + fp, per_rule)


def _ratio(a: int, b: int) -> float:
    return 0.0 if b == 0 else round(a / b, 4)
