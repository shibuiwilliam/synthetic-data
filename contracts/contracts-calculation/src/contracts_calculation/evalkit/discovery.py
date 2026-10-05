"""「発見」の採点：ルールの一覧と根拠単位を、正解表の units＋definition_units に対して採点する。"""

from __future__ import annotations


def score_discovery(predicted_rules: list[dict], answer_key: list[dict]) -> dict:
    """predicted_rules: [{"units": [...]}, ...]。集合の再現率・適合率（文書単位のマイクロ平均用）。"""
    gold: set[str] = set()
    for a in answer_key:
        gold.update(a.get("units", []))
        gold.update(a.get("definition_units", []))
    pred: set[str] = set()
    for r in predicted_rules:
        pred.update(r.get("units", []))
    tp = len(gold & pred)
    precision = tp / len(pred) if pred else 0.0
    recall = tp / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "gold": len(gold),
        "predicted": len(pred),
        "tp": tp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }
