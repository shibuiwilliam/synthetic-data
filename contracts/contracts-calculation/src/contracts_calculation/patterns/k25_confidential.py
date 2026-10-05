"""K25 秘密情報の該当性（判定）：定義に当たり、除外事由のいずれにも当たらない。"""

from __future__ import annotations

from .base import PatternDef, RuleDraft, op, step, var


def _sample(ctx, rng) -> RuleDraft:
    return RuleDraft(
        pattern_id="K25",
        rule_id="is_confidential",
        function="is_confidential",
        title="秘密情報の取扱い",
        kind="determination",
        inputs={
            "designated": {"type": "bool", "origin": "fact", "desc": "秘密である旨を明示して開示されたか"},
            "publicly_known": {"type": "bool", "origin": "judgment", "desc": "開示の時点で公知であったか"},
            "independently_developed": {
                "type": "bool",
                "origin": "judgment",
                "desc": "受領者が独自に開発した情報か",
            },
            "lawfully_obtained": {
                "type": "bool",
                "origin": "judgment",
                "desc": "正当な権限を持つ第三者から適法に取得したか",
            },
        },
        steps=[
            {
                "name": "excluded",
                "label": "除外事由のいずれかに当たるか",
                "expr": op(
                    "or", var("publicly_known"), var("independently_developed"), var("lawfully_obtained")
                ),
            },
            {
                "name": "is_confidential",
                "label": "秘密情報に当たるか",
                "expr": op("and", var("designated"), op("not", step("excluded"))),
            },
        ],
        output={"step": "is_confidential", "type": "bool"},
        obligations=["definition:designation_required", "exclusions:enumerated"],
        paragraphs=[
            "本条において「秘密情報」とは、秘密である旨を明示して相手方に開示された情報をいう。",
            {
                "text": "次の各号のいずれかに該当する情報は、秘密情報に含まれない。",
                "items": [
                    "開示の時点で既に公知であった情報",
                    "受領した当事者が独自に開発した情報",
                    "正当な権限を有する第三者から適法に取得した情報",
                ],
            },
        ],
        difficulty={"condition": "definition_and_exclusions", "unknown": True},
    )


PATTERN = PatternDef(
    id="K25",
    title="秘密情報の該当性",
    genres=frozenset({"employment", "lease", "purchase", "contracting"}),
    topics=("秘密情報", "秘密保持"),
    sampler=_sample,
)
