"""既定の約款にある計算規定を一覧にする（`icc lint-base`）。

追加した分だけを評価の対象にするのが方針なので（`HITL.md` H1）、
既定の約款に元からある計算規定は**直さずに一覧にする**。解釈が割れそうな箇所も挙げる。
"""

from __future__ import annotations

from collections import Counter

from .. import base_adapter as ba
from ..core.docindex import Doc
from . import discoverability

#: 解釈が割れやすい言い回し。
#:
#: `trigger` が**すべて**当たり、`resolved` が当たらない文だけを挙げる。
#: `utypes` を書くと、その種類の単位だけを見る。
#:
#: **2026-10-03（S10-4b）に作り直した。** 前の版は「引き金の語があって、解決の語が無い」だけを
#: 見ていたため、曖昧でない文を大量に挙げていた（729 件のうち精査すると多くが誤検出）。
#: 典型的な誤検出:
#:   * 「他の契約から支払われた額を差し引いた残額」——**限度額が無い**ので適用順の問題は起きない
#:   * 短期率表・等級表——**表のセル**に端数処理を書く必要はない
#:   * 「保険の対象に含みません」「初日と末日のいずれもこの期間に含みます」——
#:     「含み」に当たっただけで、内枠・別枠の話ではない
#: 曖昧さは「**2 つの操作が同じ文にあって、順序や枠が書かれていない**」ときに生じる。
#: そのように書き直した。
AMBIGUOUS: dict[str, dict] = {
    # 差し引きと限度が同じ文にあり、どちらを先に適用するかが書かれていない。
    #   * 「…を差し引いた額とし、◯円を限度とします」は**語順で示している**（golf-0004）
    #   * 「免責金額を控除しない額とし」は**差し引かない**ので順序の問題が起きない（auto-0008）
    #   * 「限度は無制限です」は**限度が無い**ので順序の問題が起きない（oneday-0007）
    "適用順が不明": {
        "trigger": [r"差し引|控除", r"限度|を超える"],
        "resolved": (
            r"差し引いた額|控除した額|差し引いた後|控除した後|残額|この額が|その額が"
            # S10-4d で補った言い回し（「限度額は、差引きを行った後の額に適用します」）
            r"|差引きを行った後|控除を行った後"
            r"|控除しない|差し引きません|差し引かない|控除せず|無制限"
        ),
        "utypes": ("paragraph", "list_item"),
    },
    # 割合を乗じて**金額を出す**のに、端数処理の方向が書かれていない。
    #   * 「倍率」は整数倍なので端数が出ない（group-0005）
    #   * 「前三項と同じ扱い」は**ほかの項に預けている**（group-0003）
    #   * 「乗じて得た数値」「配点に乗じ」は**金額ではない**ので円未満の端数が出ない
    #     （quake-0001 の損害割合、quake-0003 の配点）
    #   * 「乗じて得た額の範囲内で定めます」は**保険金額の決め方**で、支払額の計算ではない
    #     （quake-0004・quake-0005）
    "端数処理の方向が不明": {
        "trigger": [r"乗じ", r"割合|(?<!倍)率", r"額"],
        "resolved": (
            r"端数|切り捨て|切り上げ|四捨五入|未満を|前項|前二項|前三項|同じ扱い|同様"
            r"|得た数値|配点に乗じ|範囲内で定め"
        ),
        "utypes": ("paragraph", "list_item"),
    },
    # 限度額の内か外かが書かれていない。
    #   * 「この限度額を適用せず」は**適用しないと言い切っている**
    #   * 「◯円を限度とします。この額は、保険金とは別に支払います」は**別枠と言い切っている**。
    #     「とは別に」が限度額より**後ろ**に来る語順を取りこぼしていた（quake-0004/0005・travel）
    "内枠か別枠か不明": {
        "trigger": [r"限度", r"とは別に|の内枠|に含めて"],
        "resolved": (
            r"内枠|別枠|限度額に含めて|限度額を適用せず|適用しません"
            r"|とは別に.{0,8}(支払|お支払|計算|定め|負担|適用)"
            # 「◯円を限度として、付属品に含めて取り扱います」「限度額に含めず」は言い切っている
            r"|に含めて取り扱|に含めず|含めないもの"
        ),
        "utypes": ("paragraph", "list_item"),
    },
    # 「◯日以内」の起算日（当日を含むか）が書かれていない
    "起算日が不明": {
        "trigger": [r"から.{0,8}日以内"],
        "resolved": r"翌日|その日を含めて|当日を含ま",
        "utypes": ("paragraph", "list_item", "cell", "table_note", "footnote"),
    },
}


def lint_base(base_path: str) -> dict:
    """計算・判定らしい単位を数え上げ、明示が足りない箇所を挙げる。"""
    import re

    base = ba.load_base(base_path)
    policy = ba.rebuild(base.data)
    doc = Doc.from_dict(policy)
    cands = [c for c in discoverability.detect(doc) if c.normative]
    kinds = Counter(k for c in cands for k in c.kinds)
    ambiguous = []
    for c in cands:
        for label, rule in AMBIGUOUS.items():
            text = c.unit.text
            if c.unit.utype not in rule["utypes"]:
                continue
            if not all(re.search(pat, text) for pat in rule["trigger"]):
                continue
            if re.search(rule["resolved"], text):
                continue
            ambiguous.append(
                {
                    "unit": c.unit.id,
                    "citation": doc.citation(c.unit.id),
                    "issue": label,
                    "text": text[:120],
                }
            )
    return {
        "content_id": base.content_id,
        "genre": base.genre,
        "units": len(doc.units),
        "candidates": len(cands),
        "by_kind": dict(kinds),
        "formula_blocks": sum(1 for b in doc.blocks.values() if b["type"] == "formula"),
        "lookup_tables": sum(
            1
            for b in doc.blocks.values()
            if b["type"] == "table"
            and b.get("semantic_type") in ("rate", "grade_schedule", "surgery_schedule")
        ),
        "ambiguous": ambiguous[:40],
        "ambiguous_total": len(ambiguous),
        "note": "既定の計算規定は評価の対象にしない（HITL.md H1）。この一覧は人の判断の材料である。",
    }
