"""keiyaku.eval — 予測 JSON と検索結果の採点（CLAUDE.md §9・docs/evaluation.md）。"""

from keiyaku.eval.harness import evaluate
from keiyaku.eval.oracle import build_prediction, degrade, misread
from keiyaku.eval.search import evaluate_run, load_qrels, oracle_run

__all__ = [
    "build_prediction",
    "degrade",
    "misread",
    "evaluate",
    "evaluate_run",
    "load_qrels",
    "oracle_run",
]
