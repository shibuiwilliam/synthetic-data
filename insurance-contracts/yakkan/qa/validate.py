"""QA の検証（CLAUDE.md §8 L14）。

`qa.json` が評価に使える状態かを確かめる。

1. **型と answer の整合**：`answer_type` と `answer` の Python 型が一致する。
   `count`/`locate` は number、`figure_path` の経路は list、それ以外は string。
2. **evidence の存在**：`evidence` の要素 id が `source` にあり、かつ **`layout` に描画されている**。
   描画されていない id は bbox が取れないので、evidence として使えない。
3. **extract 系の包含**：`extract` / `table_lookup` / `definition` の answer 文字列が
   evidence の `plain_text` に含まれる。**比較は正規化後**に行う（`{const:}` の解決や
   全角空白の有無で落とさないため）。
4. **page_hint の整合**：`page_hint` が evidence の実ページと矛盾しない。
5. **問いの重複**：同じ question が 2 つ以上ない。

`Finding` は lint と同じ体裁で返す（id・重大度・メッセージ）。
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal

from yakkan.models import Answer, QASet

#: answer_type ごとに許す Python 型
_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "list": (list,),
    "boolean": (bool, str),
}

#: answer が evidence の平文に含まれていなければならない種別
CONTAINMENT_TYPES = frozenset({"extract", "table_lookup", "definition"})

#: 数値で答える種別
NUMBER_TYPES = frozenset({"count"})


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Literal["error", "warn"]
    message: str
    qa_id: str = ""

    def __str__(self) -> str:
        mark = "ERROR" if self.severity == "error" else "WARN "
        return f"[{mark}] {self.rule} {self.qa_id}: {self.message}"


def normalize(text: str) -> str:
    """包含比較用の正規化。全角半角・空白・約物のゆれを吸収する。"""
    text = unicodedata.normalize("NFKC", text)
    return "".join(text.split())


def validate(qa_set: QASet, answer: Answer) -> list[Finding]:
    out: list[Finding] = []
    elements = answer.layout.elements
    plain = answer.source.derived.plain_text
    seen_questions: dict[str, str] = {}
    seen_ids: set[str] = set()

    for item in qa_set.items:
        # --- id ---
        if not item.id:
            out.append(Finding("L14", "error", "id が空"))
            continue
        if item.id in seen_ids:
            out.append(Finding("L14", "error", "id が重複している", item.id))
        seen_ids.add(item.id)

        # --- 1. 型と answer の整合 ---
        allowed = _TYPES.get(item.answer_type, ())
        if not isinstance(item.answer, allowed):
            out.append(
                Finding(
                    "L14",
                    "error",
                    f"answer_type={item.answer_type} に対して answer が {type(item.answer).__name__}",
                    item.id,
                )
            )
        if item.type in NUMBER_TYPES and item.answer_type != "number":
            out.append(Finding("L14", "error", f"{item.type} は answer_type=number であるべき", item.id))
        if item.answer_type == "list" and isinstance(item.answer, list) and not item.answer:
            out.append(Finding("L14", "error", "list の answer が空", item.id))
        if item.answer_type == "string" and isinstance(item.answer, str) and not item.answer.strip():
            out.append(Finding("L14", "error", "string の answer が空", item.id))

        # --- 2. evidence の存在 ---
        if not item.evidence:
            out.append(Finding("L14", "error", "evidence が空", item.id))
        for element_id in item.evidence:
            if element_id not in plain and element_id not in elements:
                out.append(Finding("L14", "error", f"evidence の id が source に無い: {element_id}", item.id))
            elif element_id not in elements:
                out.append(
                    Finding(
                        "L14",
                        "error",
                        f"evidence が描画されていない（bbox が取れない）: {element_id}",
                        item.id,
                    )
                )

        # --- 3. extract 系の包含 ---
        if item.type in CONTAINMENT_TYPES and isinstance(item.answer, str):
            needle = normalize(item.answer)
            haystack = ""
            for element_id in item.evidence:
                entry = plain.get(element_id)
                if entry is not None:
                    haystack += normalize(entry.with_label) + normalize(entry.without_label)
                haystack += _descendant_text(answer, element_id)
            if needle and needle not in haystack:
                out.append(
                    Finding(
                        "L14",
                        "error",
                        f"answer が evidence の平文に含まれない: {item.answer[:40]!r}",
                        item.id,
                    )
                )

        # --- 4. page_hint の整合 ---
        if item.page_hint:
            real: set[int] = set()
            for element_id in item.evidence:
                element = elements.get(element_id)
                if element:
                    real.update(f.page for f in element.fragments)
            if real and not (set(item.page_hint) & real):
                out.append(
                    Finding(
                        "L14",
                        "warn",
                        f"page_hint {item.page_hint} が evidence の実ページ {sorted(real)} と重ならない",
                        item.id,
                    )
                )
            over = [p for p in item.page_hint if p < 1 or p > answer.layout.page_count]
            if over:
                out.append(Finding("L14", "error", f"page_hint がページ範囲外: {over}", item.id))

        # --- 5. 問いの重複 ---
        if item.question in seen_questions:
            out.append(
                Finding(
                    "L14",
                    "warn",
                    f"question が {seen_questions[item.question]} と重複している",
                    item.id,
                )
            )
        else:
            seen_questions[item.question] = item.id

    return out


def _descendant_text(answer: Answer, element_id: str) -> str:
    """要素そのものの平文が無いとき、その配下（セル・項）の平文を連結して代用する。

    表全体を evidence にした QA（答えはそのセルの値）などで必要になる。
    """
    prefix = f"{element_id}__"
    parts = [
        normalize(entry.without_label)
        for key, entry in answer.source.derived.plain_text.items()
        if key.startswith(prefix) or key.startswith(f"{element_id}_")
    ]
    return "".join(parts)
