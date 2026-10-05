"""L16：執筆 QA（`content/<cid>/qa_authored.json`）の品質検査。

`docs/authoring_checklist.md` が定めた基準を**文章ではなく検査で**強制する
（docs/remaining_issues.md S1）。基準を書いただけでは守られず、30 content のうち
13 content が違反していた。

L14（`keiyaku qa`）は「答えが evidence と整合するか」を見る。こちらは
**問いの構成**（件数・観点の配り方）を見るので、別の規則として lint 側に置く。
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from keiyaku.lint.base import Finding, LintContext, rule

#: 既定値。**doctype ごとの要求は blueprint の `authored_qa` が持つ**ので、
#: それが読めるときはそちらを使う（契約書は図が 1〜2 点しかないので図 2・apply 2。
#: docs/decisions.md 12）。宣言と実装が食い違い、`lease` の 2 本目で図 3 問を求められた。
#: 1 文書あたりの執筆 QA の件数（CLAUDE.md §15）
REQUIRED_COUNT = 15
#: 表に関する問いの最小件数
MIN_TABLE = 3
#: 図に関する問いの最小件数
MIN_FIGURE = 2
#: 場面適用型の最小件数。**自動生成できない唯一の種別**なので、執筆で入れるほかない
MIN_APPLY = 2


def _wanted(ctx: LintContext) -> tuple[int, int, int, int]:
    """(件数, 表, 図, apply) の要求。blueprint の宣言を優先する。"""
    from keiyaku.blueprints import load_blueprint

    draft = getattr(ctx, "draft", None)
    if draft is None:
        return REQUIRED_COUNT, MIN_TABLE, MIN_FIGURE, MIN_APPLY
    try:
        spec = load_blueprint(draft.doctype).authored_qa
    except (FileNotFoundError, ValueError, KeyError):
        return REQUIRED_COUNT, MIN_TABLE, MIN_FIGURE, MIN_APPLY
    return spec.count, spec.table_min, spec.figure_min, spec.apply_min


TABLE_TYPES = frozenset({"table_lookup", "table_reason"})
FIGURE_TYPES = frozenset({"figure_path", "figure_fact"})


@rule("L16", "執筆 QA の件数と観点の配り方（docs/authoring_checklist.md）")
def l16_authored_qa(ctx: LintContext) -> Iterator[Finding]:
    if ctx.content_dir is None:
        return
    path = ctx.content_dir / "qa_authored.json"
    if not path.is_file():
        yield Finding("L16", "warn", f"執筆 QA が無い（{REQUIRED_COUNT} 問を書く）", path=str(path))
        return
    try:
        items = json.loads(path.read_text(encoding="utf-8")).get("items") or []
    except (json.JSONDecodeError, OSError) as error:
        yield Finding("L16", "error", f"執筆 QA が読めない: {error}", path=str(path))
        return

    required_count, min_table, min_figure, min_apply = _wanted(ctx)
    types = [str(item.get("type", "")) for item in items]
    if len(items) != required_count:
        yield Finding(
            "L16",
            "error",
            f"執筆 QA が {len(items)} 問（{required_count} 問にそろえる）",
            path=str(path),
        )
    for label, wanted, minimum in (
        ("表", TABLE_TYPES, min_table),
        ("図", FIGURE_TYPES, min_figure),
    ):
        got = sum(1 for t in types if t in wanted)
        if got < minimum:
            yield Finding(
                "L16",
                "error",
                f"{label}に関する問いが {got} 問（{minimum} 問以上）",
                path=str(path),
            )
    applies = sum(1 for t in types if t == "apply")
    if applies < min_apply:
        yield Finding(
            "L16",
            "error",
            f"場面適用型（apply）の問いが {applies} 問（{min_apply} 問以上）"
            "——自動生成できない唯一の種別なので、執筆で入れるほかない",
            path=str(path),
        )
    for i, item in enumerate(items):
        if not item.get("evidence"):
            yield Finding("L16", "error", f"items[{i}] に evidence が無い", path=str(path))
        if not str(item.get("question", "")).strip():
            yield Finding("L16", "error", f"items[{i}] の question が空", path=str(path))
