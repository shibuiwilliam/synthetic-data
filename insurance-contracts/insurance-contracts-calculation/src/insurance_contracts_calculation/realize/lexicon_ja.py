"""演算ごとの文型（日本語）。

ここだけが日本語の文を持つ。パターンのコードには文を書かない（DESIGN.md §7.2・§8.2）。
各文型には同じ意味の変種が 2〜4 個あり、`rng` で選ぶ。変種はすべて、
`satisfies` に挙げた明示性の要件（`spec/obligations.py`）を満たす言い回しを含む。

文体は既定の約款に合わせる。です・ます調、主語は「当会社は、」、
定義語は `{term:ID}`、数値は `{const:キー}` で書く（`CLAUDE.md`「約款の文言」）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

_ROUND_WORD = {"floor": "切り捨て", "ceil": "切り上げ", "half_up": "四捨五入"}
_ROUND_VERB = {"floor": "切り捨てます", "ceil": "切り上げます", "half_up": "四捨五入します"}
_CMP_WORD = {"ge": "以上", "gt": "を超える", "le": "以下", "lt": "未満"}
_CMP_PRED = {
    "ge": "{a}が{b}以上であるとき",
    "gt": "{a}が{b}を超えるとき",
    "le": "{a}が{b}以下であるとき",
    "lt": "{a}が{b}未満であるとき",
    "eq": "{a}が{b}と同じであるとき",
    "ne": "{a}が{b}と異なるとき",
}
_SCOPE_SENTENCE = {
    "per_accident": "この条の規定による{benefit}は、1回の事故につき{amount}を限度とします。",
    "per_person": "この条の規定による{benefit}は、1名につき{amount}を限度とします。",
    "per_day": "この条の規定による{benefit}は、1日につき{amount}を限度とします。",
    "per_period": "この条の規定による{benefit}は、保険期間を通じて{amount}を限度とします。",
}


@dataclass
class Rendered:
    """文または体言 1 つ。`satisfies` は満たすことを意図した明示性の要件。"""

    text: str
    satisfies: tuple[str, ...] = field(default_factory=tuple)


def pick(rng: random.Random, options: list[str]) -> str:
    return options[rng.randrange(len(options))]


# --------------------------------------------------------------- 体言（句）
def phrase_sub(a: str, b: str, rng: random.Random) -> str:
    return pick(rng, [f"{a}から{b}を差し引いた額", f"{a}から{b}を控除した額"])


def phrase_sum(parts: list[str], rng: random.Random) -> str:
    joined = "、".join(parts[:-1]) + "および" + parts[-1]
    return pick(rng, [f"{joined}の合計額", f"{joined}を合計した額"])


def phrase_mul(amount: str, times: str, rng: random.Random) -> str:
    return pick(rng, [f"{times}に{amount}を乗じて得た額", f"{amount}に{times}を乗じて得た額"])


def phrase_table_rate(amount: str, key: str, rate_name: str, rng: random.Random, where: str = "下表") -> str:
    """表引きの割合を乗じる体言。`where` は表の在りか（「下表」または `{ref:別表}`）。"""
    return pick(
        rng,
        [
            f"{amount}に、{key}に応じて{where}に定める{rate_name}を乗じて得た額",
            f"{amount}に、{key}の区分に応じ{where}に定める{rate_name}を乗じて得た額",
        ],
    )


def phrase_proration(amount: str, num: str, den: str, rng: random.Random) -> str:
    return pick(
        rng,
        [
            f"{amount}に、{num}の{den}に対する割合を乗じて得た額",
            f"{amount}に、{den}のうち{num}が占める割合を乗じて得た額",
        ],
    )


def phrase_min(parts: list[str], rng: random.Random) -> str:
    joined = "または".join(parts)
    return pick(rng, [f"{joined}のいずれか低い額", f"{joined}のうち低い額"])


def phrase_max(parts: list[str], rng: random.Random) -> str:
    joined = "または".join(parts)
    return pick(rng, [f"{joined}のいずれか高い額", f"{joined}のうち高い額"])


def phrase_limited(base: str, limit: str, rng: random.Random) -> str:
    """限度を体言の中で明示する。

    文の末尾も「…とします。」になるので、「とします」が重ならない言い方も混ぜる。
    """
    return pick(
        rng,
        [
            f"{base}（ただし、{limit}を限度とします。）",
            f"{base}（{limit}を限度とします。）",
            f"{limit}を限度とする{base}",
        ],
    )


def phrase_lookup(key: str, value_name: str, rng: random.Random, where: str = "下表") -> str:
    return pick(rng, [f"{key}に応じて{where}に定める{value_name}", f"{where}の{key}の欄に定める{value_name}"])


def phrase_deadline(base: str, span: str, rng: random.Random) -> str:
    return pick(rng, [f"{base}から{span}を経過する日", f"{base}に{span}を加えた日"])


def phrase_elapsed(start: str, end: str, rng: random.Random) -> str:
    return pick(rng, [f"{start}から{end}までの日数", f"{start}から{end}までに経過した日数"])


def phrase_aggregate(inner: str, rng: random.Random) -> str:
    return pick(rng, [f"それぞれについて算出した{inner}の合計額", f"{inner}をそれぞれ算出して合計した額"])


# --------------------------------------------------------------- 文（規範）
def sentence_amount(benefit: str, phrase: str, rng: random.Random) -> Rendered:
    """「…の額は、…とします。」"""
    return Rendered(
        pick(
            rng,
            [
                f"{benefit}の額は、{phrase}とします。",
                f"当会社が支払う{benefit}の額は、{phrase}とします。",
            ],
        )
    )


def sentence_cap(limit: str, benefit: str, rng: random.Random, subject: str = "この額") -> Rendered:
    """限度額。適用順が読めるように、必ず差引の文のあとに置く。"""
    return Rendered(
        pick(
            rng,
            [
                f"{subject}が{limit}を超えるときは、{limit}とします。",
                f"ただし、{limit}を限度とします。",
                f"{subject}が{limit}を上回る場合は、{limit}をもって{benefit}の額とします。",
            ],
        ),
        ("order:deductible_then_limit",),
    )


def sentence_floor_zero(
    benefit: str, rng: random.Random, subject: str = "前項の規定により算出した額"
) -> Rendered:
    return Rendered(
        pick(
            rng,
            [
                f"{subject}が0円を下回るときは、{benefit}は支払いません。",
                f"{subject}が0円を下回る場合には、{benefit}を支払いません。",
            ],
        ),
        ("floor:zero",),
    )


def sentence_round(
    unit: str, rounding: str, rng: random.Random, subject: str = "前項の規定により算出した額"
) -> Rendered:
    verb = _ROUND_VERB[rounding]
    return Rendered(
        pick(
            rng,
            [
                f"{subject}に{unit}未満の端数があるときは、これを{verb}。",
                f"{subject}について{unit}未満の端数が生じたときは、その端数を{verb}。",
            ],
        ),
        (f"rounding:{rounding}",),
    )


def sentence_round_unspecified(
    unit: str, rng: random.Random, subject: str = "前項の規定により算出した額"
) -> Rendered:
    """端数処理の**方向を書かない**文（challenge モード専用。通常モードでは使わない）。"""
    return Rendered(
        pick(
            rng,
            [
                f"{subject}は、{unit}を単位として計算します。",
                f"{subject}については、{unit}を単位として取り扱います。",
            ],
        )
    )


def sentence_case_vague(
    threshold: str, subject: str, then_phrase: str, else_phrase: str, benefit: str, rng: random.Random
) -> Rendered:
    """境界の**向き**を書かない場合分けの文（challenge モード専用）。

    しきい値そのものは示すが、その点がどちらに属するかを書かない。
    「以上」か「を超える」かで結果が変わる入力があり、読みが 2 通りになる。
    """
    return Rendered(
        pick(
            rng,
            [
                f"{benefit}の額は、{subject}が{threshold}を境として、"
                f"これより大きい場合は{then_phrase}、小さい場合は{else_phrase}とします。",
                f"{benefit}の額は、{threshold}を基準として、{subject}がこれより大きいときは{then_phrase}、"
                f"小さいときは{else_phrase}とします。",
            ],
        )
    )


def sentence_ceil_period(unit_word: str, rng: random.Random) -> Rendered:
    """「1か月未満の端日数があるときは、これを1か月として計算します。」"""
    return Rendered(
        pick(
            rng,
            [
                f"{unit_word}未満の端日数があるときは、これを{unit_word}として計算します。",
                f"{unit_word}に満たない端日数は、{unit_word}として計算します。",
            ],
        ),
        ("ceil_period",),
    )


def sentence_threshold(a: str, b: str, op: str, effect: str, rng: random.Random) -> Rendered:
    cond = _CMP_PRED[op].format(a=a, b=b)
    return Rendered(
        pick(rng, [f"{cond}に限り、{effect}", f"{cond}は、{effect}"]),
        (f"threshold:{op}",) if op in _CMP_WORD else (),
    )


def sentence_case(
    cond: str, then_phrase: str, else_phrase: str, benefit: str, rng: random.Random
) -> Rendered:
    return Rendered(
        pick(
            rng,
            [
                f"{benefit}の額は、{cond}は{then_phrase}、それ以外の場合は{else_phrase}とします。",
                f"{benefit}の額は、{cond}に該当する場合は{then_phrase}とし、"
                f"該当しない場合は{else_phrase}とします。",
            ],
        )
    )


def sentence_table_out_of_range(key: str, limit: str, benefit: str, rng: random.Random) -> Rendered:
    """表に定めのないキーの扱い。限度を数値で示すので、表の範囲が一義に読める。"""
    return Rendered(
        pick(
            rng,
            [
                f"{key}が{limit}を超えるときは、{benefit}は支払いません。",
                f"{key}が{limit}を超える場合には、{benefit}を支払いません。",
            ],
        ),
        ("table:out_of_range",),
    )


def sentence_scope(scope: str, benefit: str, amount: str, rng: random.Random) -> Rendered:
    return Rendered(
        _SCOPE_SENTENCE[scope].format(benefit=benefit, amount=amount),
        (f"scope:{scope}",),
    )


def sentence_policy_limit(limit_phrase: str, default: str, rng: random.Random) -> Rendered:
    """保険証券の記載を限度とし、記載がないときの既定値も同じ文で示す。

    「記載がないときの値」を書かないと解釈が割れるので、必ず続けて書く（DESIGN.md §8.3）。
    """
    head = pick(
        rng,
        [f"ただし、{limit_phrase}を限度とします。", f"この額は、{limit_phrase}を限度とします。"],
    )
    tail = pick(
        rng,
        [
            f"保険証券にその記載がないときは、{default}を限度とします。",
            f"保険証券に記載がないときは、{default}とします。",
        ],
    )
    return Rendered(head + tail, ("limit", "default:policy_absent"))


def sentence_default(param: str, rng: random.Random, what: str = "保険証券") -> Rendered:
    return Rendered(
        pick(
            rng,
            [
                f"{what}にその記載がないときは、{param}とします。",
                f"{what}に記載がないときは、{param}として取り扱います。",
            ],
        ),
        ("default:policy_absent",),
    )


def sentence_period_start(base: str, span: str, included: bool, effect: str, rng: random.Random) -> Rendered:
    if included:
        head = pick(
            rng,
            [f"{base}からその日を含めて{span}以内に", f"{base}からその日を含めて{span}を経過する日までに"],
        )
        oid = "period:first_day_included"
    else:
        head = pick(
            rng,
            [f"{base}の翌日から起算して{span}以内に", f"{base}の翌日から起算して{span}を経過する日までに"],
        )
        oid = "period:next_day_start"
    return Rendered(f"{head}{effect}", (oid,))


def sentence_multi_hit(rule: str, benefit: str, rng: random.Random) -> Rendered:
    words = {
        "highest": f"いずれか高い額のみを{benefit}として支払います。",
        "sum": f"それぞれの額を合算して{benefit}を支払います。",
        "first": f"最初に該当した区分により{benefit}を支払います。",
    }
    return Rendered(
        pick(
            rng,
            [
                f"2以上の区分に該当する場合は、{words[rule]}",
                f"同時に2以上の区分に該当するときは、{words[rule]}",
            ],
        ),
        (f"multi_hit:{rule}",),
    )


def sentence_frame(inner: bool, small: str, big: str, rng: random.Random) -> Rendered:
    if inner:
        return Rendered(
            pick(rng, [f"{small}は、{big}に含みます。", f"{small}は{big}の内枠とします。"]), ("frame:inner",)
        )
    return Rendered(
        pick(rng, [f"{small}は、{big}とは別に支払います。", f"{small}は{big}の別枠とします。"]),
        ("frame:outer",),
    )


def sentence_waiting_rule(span: str, start_phrase: str, benefit: str, rng: random.Random) -> Rendered:
    """待機期間の規定。支払う条件と、期間中に生じた事由を支払わないことを 1 つの文で書く。"""
    head = pick(
        rng,
        [
            f"当会社は、{start_phrase}から{span}以上を経過した後に生じた事由に限り、{benefit}を支払います。",
            f"{start_phrase}から{span}以上を経過した後に生じた事由に限り、{benefit}を支払います。",
        ],
    )
    tail = pick(
        rng,
        [
            f"この期間中に生じた事由については、{benefit}は支払いません。",
            f"この期間中に生じた事由については、{benefit}を支払いません。",
        ],
    )
    return Rendered(head + tail, ("threshold:ge", "waiting:excluded"))


def sentence_waiting(span: str, benefit: str, rng: random.Random) -> Rendered:
    return Rendered(
        pick(
            rng,
            [
                f"この期間中に生じた事由については、{benefit}は支払いません。",
                f"{span}の期間中に生じた事由については、{benefit}を支払いません。",
            ],
        ),
        ("waiting:excluded",),
    )


def sentence_cap_subject(subject: str, limit: str, rng: random.Random) -> Rendered:
    """「支払の対象となる日数は、…を限度とします。」"""
    return Rendered(
        pick(rng, [f"{subject}は、{limit}を限度とします。", f"{subject}については、{limit}を限度とします。"]),
        ("limit",),
    )


def sentence_enumeration(mode: str, benefit: str, rng: random.Random) -> Rendered:
    """号の表を導く文。"""
    if mode == "exclude":
        return Rendered(
            pick(
                rng,
                [
                    f"当会社は、次のいずれかに該当する場合には、{benefit}を支払いません。",
                    f"次のいずれかに該当するときは、{benefit}を支払いません。",
                ],
            )
        )
    if mode == "all":
        return Rendered(
            pick(
                rng,
                [
                    f"当会社は、次のすべてに該当する場合に限り、{benefit}を支払います。",
                    f"次のすべてに該当する場合に限り、{benefit}を支払います。",
                ],
            )
        )
    return Rendered(
        pick(
            rng,
            [
                f"当会社は、次のいずれかに該当する場合に、{benefit}を支払います。",
                f"次のいずれかに該当する場合に、{benefit}を支払います。",
            ],
        )
    )


def sentence_figure_pointer(what: str, rng: random.Random) -> Rendered:
    return Rendered(
        pick(
            rng,
            [
                f"当会社は、下図の手順により、{what}を判定します。",
                f"{what}は、下図に示す順序により判定します。",
            ],
        )
    )


def sentence_formula_pointer(rng: random.Random) -> Rendered:
    return Rendered(pick(rng, ["その算出は、次の算式によります。", "算出は次の算式によります。"]))


def sentence_table_pointer(what: str, rng: random.Random, where: str = "下表") -> Rendered:
    return Rendered(
        pick(rng, [f"{what}は、{where}に定めるとおりとします。", f"{what}は{where}のとおりです。"])
    )


def sentence_proviso_pointer(ref: str, what: str, rng: random.Random) -> Rendered:
    """但し書きを別の条に置いたとき、本文からその条を指す文（分散。DESIGN.md §8.5）。"""
    return Rendered(
        pick(
            rng,
            [
                f"{what}の取扱いは、{ref}に定めるところによります。",
                f"{what}については、{ref}の規定を適用します。",
            ],
        )
    )


def proviso_article_title(what: str) -> str:
    """但し書きを置く条の見出し。"""
    return f"{what}の取扱い"


def sentence_appendix_lead(what: str, rng: random.Random) -> str:
    """別表の冒頭に置く導入文（別表そのものが何の表かを述べる）。"""
    return pick(rng, [f"{what}は、次のとおりとします。", f"{what}は、次表に定めるとおりとします。"])


def rider_title(benefit: str) -> str:
    """特約の名称。既定の約款の付け方（「…特約」）に合わせる。"""
    return f"{benefit.removesuffix('保険金').removesuffix('給付金')}特約"


def sentence_rider_scope(benefit: str, rng: random.Random) -> Rendered:
    """特約の適用条件の条（既定の約款の特約が必ず持つ）。"""
    return Rendered(
        pick(
            rng,
            [
                f"この特約は、保険証券にこの特約を適用する旨の記載がある場合に適用し、{benefit}を支払います。",
                f"この特約は、保険証券にこの特約の記載がある保険契約に適用し、{benefit}を支払います。",
            ],
        )
    )


def sentence_rider_fallback(rng: random.Random) -> Rendered:
    """特約の末尾に置く準用の条（既定の約款の特約が必ず持つ）。"""
    return Rendered(
        pick(
            rng,
            [
                "この特約に定めのない事項については、普通保険約款の規定を準用します。",
                "この特約に定めがない事項は、普通保険約款の規定によります。",
            ],
        )
    )


def conjunction(parts: list[str], all_of: bool) -> str:
    """号の列挙を 1 文にまとめるときの導入句。"""
    return "次のすべてに該当する場合" if all_of else "次のいずれかに該当する場合"
