"""明示性の要件（DESIGN.md §8.3）。

通常モードでは、解釈が割れる論点を必ず文言にする。パターンは「明示すべき事項」を
`obligations` として宣言し、検証ゲート G3 が**実際に出力された文**に対応する言い回しが
あるかを逐語で確かめる。宣言しただけでは通らない（言い回しを落とすと G3 が落ちる）。

要件のIDは `家族[:引数[:引数]]` の形。家族ごとに、満たすために必要な言い回しを持つ。
`ordered=True` の家族は、言い回しが**文書順に**その順序で現れることまで要求する。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Requirement:
    id: str
    desc: str
    patterns: tuple[str, ...]
    ordered: bool = False

    def check(self, text: str) -> str | None:
        """満たしていれば None、満たしていなければ理由を返す。"""
        pos = -1
        for pat in self.patterns:
            m = re.search(pat, text[pos + 1 :] if self.ordered and pos >= 0 else text)
            if not m:
                return f"「{self.desc}」に当たる言い回し（/{pat}/）が見つからない"
            if self.ordered:
                pos = (pos + 1 if pos >= 0 else 0) + m.start()
        return None


_ROUND_WORD = {"floor": "切り捨て", "ceil": "切り上げ", "half_up": "四捨五入"}
_CMP_WORD = {"ge": "以上", "gt": "を超える", "le": "以下", "lt": "未満"}
_SCOPE_WORD = {
    "per_accident": r"1回の事故につき|1事故につき|1回の事故ごとに",
    "per_person": r"1名につき|1名ごとに",
    "per_day": r"1日につき",
    "per_period": r"保険期間を通じて|保険期間中を通じて",
}
_MULTI_WORD = {
    "highest": r"いずれか高い|最も高い|いずれか重い",
    "sum": r"合算し|合計し",
    "first": r"最初に該当",
}


def build(oid: str) -> Requirement:
    """要件IDから検査器を作る。知らないIDは生成を止める（黙って通さない）。"""
    family, *args = oid.split(":")
    if family == "order" and args and args[0] == "deductible_then_limit":
        return Requirement(
            oid,
            "免責金額と限度額のどちらを先に適用するか",
            (r"差し引いた額|控除した額", r"を超えるときは|を限度|を上回る場合"),
            ordered=True,
        )
    if family == "order" and args and args[0] == "rate_then_rounding":
        return Requirement(
            oid, "割合を乗じた後に端数処理をすること", (r"乗じて得た額", r"端数"), ordered=True
        )
    if family == "floor" and args and args[0] == "zero":
        return Requirement(oid, "差引の結果が0円を下回るときの扱い", (r"0円を下回る",))
    if family == "rounding":
        word = _ROUND_WORD[args[0]]
        return Requirement(oid, f"端数処理の単位と方向（{word}）", (r"未満の端数", word), ordered=True)
    if family == "ceil_period":
        return Requirement(
            oid, "期間の端数を1単位として数えること", (r"(?:未満|に満たない)の?端(?:日数|数).*として計算",)
        )
    if family == "threshold":
        word = _CMP_WORD[args[0]]
        return Requirement(oid, f"しきい値の境界（{word}）", (re.escape(word),))
    if family == "period" and args and args[0] == "first_day_included":
        return Requirement(oid, "初日を算入すること", (r"その日を含めて",))
    if family == "period" and args and args[0] == "next_day_start":
        return Requirement(oid, "翌日から起算すること", (r"翌日から起算",))
    if family == "table" and args and args[0] == "out_of_range":
        return Requirement(
            oid,
            "表に定めのないキーの扱い",
            (
                r"定めがない|定めのない|を超えるときは、[^。]*支払いません|を超える場合には、[^。]*支払いません",
            ),
        )
    if family == "multi_hit":
        return Requirement(oid, "複数に該当するときの扱い", (_MULTI_WORD[args[0]],))
    if family == "scope":
        return Requirement(oid, "適用の範囲（1事故・1名・1日・通算）", (_SCOPE_WORD[args[0]],))
    if family == "default" and args and args[0] == "policy_absent":
        return Requirement(oid, "保険証券に記載がないときの値", (r"記載がないときは",))
    if family == "frame" and args and args[0] == "inner":
        return Requirement(oid, "小さい限度額が大きい限度額に含まれること", (r"に含みます|の内枠",))
    if family == "frame" and args and args[0] == "outer":
        return Requirement(oid, "小さい限度額が大きい限度額とは別枠であること", (r"とは別に|の別枠",))
    if family == "waiting":
        return Requirement(oid, "待機期間中は支払わないこと", (r"支払いません",))
    if family == "limit":
        return Requirement(
            oid, "限度額を明示すること", (r"を限度|を超えるときは|を上回る場合|いずれか低い額|うち低い額",)
        )
    if family == "proration":
        return Requirement(oid, "按分の分母と分子", (r"に対する割合|が占める割合",))
    raise ValueError(f"知らない明示性の要件: {oid}")


#: 文書に必ず現れるべき言い回しを持つ要件の一覧（文書化と網羅テストに使う）
FAMILIES = (
    "order:deductible_then_limit",
    "order:rate_then_rounding",
    "floor:zero",
    "rounding:floor",
    "rounding:ceil",
    "rounding:half_up",
    "ceil_period",
    "threshold:ge",
    "threshold:gt",
    "threshold:le",
    "threshold:lt",
    "period:first_day_included",
    "period:next_day_start",
    "table:out_of_range",
    "multi_hit:highest",
    "multi_hit:sum",
    "multi_hit:first",
    "limit",
    "scope:per_accident",
    "scope:per_person",
    "scope:per_day",
    "scope:per_period",
    "default:policy_absent",
    "frame:inner",
    "frame:outer",
    "waiting:excluded",
    "proration",
)
