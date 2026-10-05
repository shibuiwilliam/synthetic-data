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

from keiyaku.models import Answer, QASet

#: answer_type ごとに許す Python 型
_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "list": (list,),
    "boolean": (bool, str),
}

#: answer が evidence の平文に含まれていなければならない種別。
#: `apply`（場面適用）は**算出値を答える**ので、ここに入れてはいけない。
CONTAINMENT_TYPES = frozenset({"extract", "table_lookup", "definition"})

#: 答えが文書の文字列にならない種別（包含検査をしない）。記録のために明示しておく。
DERIVED_ANSWER_TYPES = frozenset({"apply", "table_reason", "negative", "count", "figure_fact"})

#: 数値で答える種別
NUMBER_TYPES = frozenset({"count"})

#: 図の中の要素を答えにする種別。答えが図のノードのラベルに実在するかを検査する。
FIGURE_LABEL_TYPES = frozenset({"figure_path"})


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

        # --- 3b. 図の答えが実在するラベルか ---
        # `figure_path` は包含検査の対象外なので、**間違った答えが素通りする**。
        # 実際に「最初の手順は何か」に存在しないノード名を書いた執筆 QA が通ってしまった。
        if item.type in FIGURE_LABEL_TYPES:
            labels = _figure_labels(answer, item.evidence)
            if labels:
                wanted = item.answer if isinstance(item.answer, list) else [item.answer]
                for value in wanted:
                    if not isinstance(value, str):
                        continue
                    if normalize(value) not in labels:
                        out.append(
                            Finding(
                                "L14",
                                "error",
                                f"図に存在しないラベルを答えにしている: {value[:30]!r}",
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


def _figure_labels(answer: Answer, evidence: list[str]) -> set[str]:
    """evidence に含まれる図の、ノード・手順・区間のラベルを正規化して集める。

    図の中身は `source` の diagram にしかない（`plain_text` には出ない）ので、
    ここだけは diagram を直接歩く。
    """
    wanted = set(evidence)
    labels: set[str] = set()

    #: 図の「読み取れる文字」が入るキー。timeline の区間は軸の目盛（from/to）で答えるので、
    #: ノードのラベルだけを集めると取りこぼす。
    text_keys = ("label", "title", "text", "name", "from", "from_", "to", "start", "end", "note")

    def add(value: str, mapping: dict[str, str]) -> None:
        if not value.strip():
            return
        # 図の中のトークンは build が解決して描くので、紙面に出るのは解決後の文字列。
        # 執筆時の生文字列も許しておく（どちらで書いても同じ図を指す）。
        labels.add(normalize(value))
        labels.add(normalize(mapping.get(value, value)))

    def collect(obj: object, mapping: dict[str, str]) -> None:
        if isinstance(obj, dict):
            for key in text_keys:
                value = obj.get(key)
                if isinstance(value, str):
                    add(value, mapping)
            ticks = obj.get("ticks")
            if isinstance(ticks, list):
                for tick in ticks:
                    if isinstance(tick, str):
                        add(tick, mapping)
            for value in obj.values():
                collect(value, mapping)
        elif isinstance(obj, list):
            for value in obj:
                collect(value, mapping)

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "figure" and obj.get("id") in wanted:
                derived = answer.source.derived.figures.get(str(obj["id"]))
                collect(obj.get("diagram"), derived.resolved_labels if derived else {})
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    dumped = answer.source.model_dump(mode="json")
    for key in ("front_matter", "body", "appendices"):
        walk(dumped.get(key))
    # 正規化グラフのノードラベルも正解に含める（docs/eval_dataset_plan.md P1）。
    # 経路（`paths`）はグラフから作るので、グラフのラベルを認めないと自動 QA が自分で落ちる。
    for figure_id in wanted:
        derived = answer.source.derived.figures.get(figure_id)
        if derived is None:
            continue
        for node in derived.graph.nodes:
            if node.label.strip():
                labels.add(normalize(node.label))
    return labels


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
