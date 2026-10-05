"""読取結果（PDF を読んだ結果のJSON）と、正解の根拠との突き合わせ。

一気通貫（`--track e2e`）の採点に使う。実装の点数だけでは
「読み取りで落としたのか、読んだうえで取り違えたのか」が分からないので、
**根拠が読取結果に残っているか**を別に測る（DESIGN.md §11.4）。

読取結果の形は本体の `schema/prediction.schema.json` に合わせる。
突合は**中身（文字列）で行う**。予測に内部IDは無い前提である（TASK.md §3-2）。
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

#: 突合の前に落とす文字（約款の表記ゆれを吸収する）
_NOISE = re.compile(r"[\s　、。，．・：；（）()「」『』\[\]【】]")
#: 根拠として短すぎる単位は、たまたま一致してしまうので突合に使わない
MIN_CHARS = 8


class ReadingError(ValueError):
    """読取結果を読めない。"""


def normalize(text: str) -> str:
    """表記ゆれを落とした突合用の文字列（全角半角・記号・空白を無視する）。"""
    return _NOISE.sub("", unicodedata.normalize("NFKC", text))


@dataclass
class Reading:
    """読取結果。突合に使うのは「読めた文字列の集まり」だけ。"""

    doc_id: str
    texts: list[str] = field(default_factory=list)
    pages: int = 0

    @property
    def blob(self) -> str:
        return "".join(normalize(t) for t in self.texts)

    @classmethod
    def load(cls, path: str | Path) -> Reading:
        p = Path(path)
        if not p.is_file():
            raise ReadingError(f"読取結果が無い: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ReadingError(f"{p} を JSON として読めない: {e}") from e
        if not isinstance(data, dict):
            raise ReadingError(f"{p}: 最上位が辞書でない")
        texts = list(_iter_texts(data))
        if not texts:
            raise ReadingError(f"{p}: 本文らしい文字列が 1 つも無い（elements / tables / figures を見る）")
        return cls(doc_id=str(data.get("doc_id", "")), texts=texts, pages=int(data.get("pages") or 0))


def _iter_texts(data: dict):
    """読取結果から文字列を集める。本体の prediction 形式に合わせつつ、欄が欠けても落ちない。"""
    for el in data.get("elements") or []:
        if isinstance(el, dict) and el.get("text"):
            yield str(el["text"])
    for t in data.get("tables") or []:
        if not isinstance(t, dict):
            continue
        if t.get("caption"):
            yield str(t["caption"])
        for cell in t.get("cells") or []:
            if isinstance(cell, dict) and cell.get("value"):
                yield str(cell["value"])
            elif isinstance(cell, str):
                yield cell
        for row in t.get("grid") or []:
            for cell in row or []:
                if isinstance(cell, str):
                    yield cell
                elif isinstance(cell, dict) and cell.get("text"):
                    yield str(cell["text"])
    for f in data.get("figures") or []:
        if not isinstance(f, dict):
            continue
        for key in ("caption", "alt"):
            if f.get(key):
                yield str(f[key])
        for n in f.get("nodes") or []:
            if isinstance(n, dict) and n.get("label"):
                yield str(n["label"])
            elif isinstance(n, str):
                yield n
        for fact in f.get("facts") or []:
            yield str(fact)
    for e in data.get("enumerations") or []:
        for item in (e or {}).get("items") or []:
            if isinstance(item, dict) and item.get("text"):
                yield str(item["text"])
    for o in data.get("outline") or []:
        if isinstance(o, dict) and o.get("heading_text"):
            yield str(o["heading_text"])


@dataclass
class Coverage:
    """根拠がどれだけ読取結果に残っているか。"""

    units: int
    found: int
    rate: float
    missing: list[dict] = field(default_factory=list)
    per_rule: dict[str, dict] = field(default_factory=dict)


def evidence_coverage(reading: Reading, answer: list[dict], units: dict[str, str]) -> Coverage:
    """正解表の根拠単位が、読取結果の文字列に含まれているかを測る。

    `units` は「単位ID → 正解の文字列」。短すぎる単位は突合に使わない
    （たまたま一致して読み取れたように見えるため）。
    """
    blob = reading.blob
    total = found = 0
    missing: list[dict] = []
    per_rule: dict[str, dict] = {}
    for a in answer:
        hit = lost = 0
        for uid in a["units"]:
            text = units.get(uid, "")
            if len(normalize(text)) < MIN_CHARS:
                continue
            total += 1
            if normalize(text) in blob:
                found += 1
                hit += 1
            else:
                lost += 1
                missing.append({"rule": a["rule"], "unit": uid, "text": text[:60]})
        per_rule[a["rule"]] = {
            "units": hit + lost,
            "found": hit,
            "rate": round(hit / (hit + lost), 4) if hit + lost else 1.0,
        }
    return Coverage(total, found, round(found / total, 4) if total else 1.0, missing[:40], per_rule)
