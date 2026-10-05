"""単体テスト用の最小の文書と仕様を組み立てる（本体に依存しない）。"""

from __future__ import annotations

import datetime as dt
from typing import Any

from insurance_contracts_calculation.core.docindex import Doc
from insurance_contracts_calculation.spec.validate import RuleSet

_UNIT_OF = {int: "1", bool: "BOOL", str: "STR"}


def minimal_policy(text: str = "検査用の文。30%と10か月を含む。") -> dict:
    """`Doc` が読める最小の約款JSON。"""
    tid = "tbl_t1"
    grid = [
        [
            {"id": f"{tid}__r0c0", "text": "経過月数", "role": "header"},
            {"id": f"{tid}__r0c1", "text": "10か月まで", "role": "header"},
            {"id": f"{tid}__r0c2", "text": "20か月まで", "role": "header"},
        ],
        [
            {"id": f"{tid}__r1c0", "text": "支払割合", "role": "stub"},
            {"id": f"{tid}__r1c1", "text": "30%", "role": "body"},
            {"id": f"{tid}__r1c2", "text": "20%", "role": "body"},
        ],
    ]
    return {
        "schema_version": "1.0",
        "content_id": "t-0001",
        "genre": "auto",
        "seed": 1,
        "meta": {"title": "検査用約款", "constants": {"t_limit": "10万円"}},
        "front_matter": {},
        "defined_terms": [],
        "body": [
            {
                "id": "ch1",
                "kind": "chapter",
                "title": "検査",
                "children": [
                    {
                        "id": "ch1_a1",
                        "kind": "article",
                        "title": "検査用の条",
                        "children": [{"id": "ch1_a1_p1", "kind": "paragraph", "text": text, "blocks": []}],
                        "blocks": [
                            {
                                "type": "table",
                                "id": tid,
                                "caption": "経過月数に応じる支払割合",
                                "semantic_type": "rate",
                                "layout": {"header_rows": 1, "header_cols": 1},
                                "grid": grid,
                            }
                        ],
                    }
                ],
            }
        ],
        "appendices": [],
        "back_matter": {},
        "derived": {"labels": {}, "plain_text": {}, "refs": [], "tables": {}, "figures": {}},
    }


def _input_spec(value: Any) -> dict:
    if isinstance(value, bool):
        return {"type": "bool", "origin": "assessment", "desc": "検査用の真偽"}
    if isinstance(value, dt.date):
        return {"type": "date", "origin": "claim_fact", "desc": "検査用の日付"}
    if isinstance(value, list):
        return {"type": "list"}
    return {"type": "int", "unit": "1", "min": 0, "max": 10**6, "origin": "claim_fact", "desc": "検査用の数"}


def build_ruleset(
    expr: dict, inputs: dict, *, obligations: list[str] | None = None, text: str | None = None
) -> RuleSet:
    """式 1 本からなる仕様を組み立てる。"""
    doc = Doc.from_dict(minimal_policy(text) if text else minimal_policy())
    rule_inputs = {k: _input_spec(v) for k, v in inputs.items() if not isinstance(v, list)}
    collections = {
        k: {
            "fields": {
                f: {"type": "int", "unit": "1", "min": 0, "max": 100, "origin": "claim_fact", "desc": "明細"}
                for f in v[0]
            },
            "max_items": 3,
        }
        for k, v in inputs.items()
        if isinstance(v, list) and v
    }
    out_unit = _guess_output_unit(expr)
    spec = {
        "spec_version": "0.2",
        "document": {"content_id": "t-0001"},
        "params": {},
        "tables": {
            "rate": {
                "from_block": "tbl_t1",
                "shape": "header_keys",
                "key_row": 0,
                "value_row": 1,
                "key_parse": "upto_month",
                "value_parse": "percent",
                "mode": "step_le",
                "key_unit": "1",
                "value_unit": "1",
            }
        },
        "rules": [
            {
                "id": "t.rule",
                "title": "検査用の規定",
                "kind": "calculation",
                "interface": {"function": "t_rule"},
                "inputs": rule_inputs,
                "collections": collections,
                "steps": [{"name": "t_rule", "label": "検査用の値", "expr": expr}],
                "output": {"step": "t_rule", "type": out_unit[0], "unit": out_unit[1]},
                "obligations": list(obligations or []),
                "sources": [{"unit": "ch1_a1_p1"}],
            }
        ],
    }
    return RuleSet(spec, doc)


def _guess_output_unit(expr: dict) -> tuple[str, str | None]:
    from insurance_contracts_calculation.spec.ops import CMP, LOGIC

    op = expr.get("op")
    if op in CMP or op in LOGIC:
        return "bool", None
    if op in ("add_days", "add_months", "end_of_month"):
        return "date", None
    return "int", "1"
