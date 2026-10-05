"""計算パック（`packs/*.yaml`）の読み込み。

パックは**語彙と値域だけ**を持つ。式の形はパターン（`patterns/`）、文型は `realize/lexicon_ja.py`
にあり、三者を混ぜない。値をコードに直書きしないための置き場である（DESIGN.md §7.4）。

| ファイル | 内容 |
|---|---|
| `concepts.yaml` | 入力概念の語彙（引数名・日本語の呼び方・型・単位・値域） |
| `<genre>.yaml` | 種目ごとの題材（保険金の名称・支払事由・必要な用語）とパラメータの値域 |
| `limits.yaml` | 図と表の実用上限（実測値） |

読み込みは一度だけ行い、辞書は変更しない（`PackError` で早く止める）。
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PACKS_DIR = Path(__file__).resolve().parents[3] / "packs"


class PackError(ValueError):
    """パックの内容が規約に合わない。"""


def _load_yaml(path: Path) -> dict:
    import yaml  # 本体の venv が持つ（pyproject の注記を参照）

    if not path.is_file():
        raise PackError(f"パックが無い: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PackError(f"パックの最上位が辞書でない: {path}")
    return data


@dataclass(frozen=True)
class Concept:
    """入力概念。同じ概念には文書をまたいで同じ引数名を使う。"""

    key: str
    arg: str
    desc: str
    type: str
    unit: str | None = None
    origin: str = "claim_fact"
    min: Any = None
    max: Any = None
    optional: bool = False
    values: tuple[str, ...] = field(default_factory=tuple)

    def as_input(self, desc: str | None = None) -> dict:
        out: dict[str, Any] = {"type": self.type, "origin": self.origin, "desc": desc or self.desc}
        if self.unit:
            out["unit"] = self.unit
        if self.min is not None:
            out["min"] = self.min
        if self.max is not None:
            out["max"] = self.max
        if self.optional:
            out["optional"] = True
        if self.values:
            out["values"] = list(self.values)
        return out


@dataclass(frozen=True)
class Range:
    """パラメータの値域。きりのよい値の候補から選ぶ。"""

    key: str
    choices: tuple[int, ...]
    unit: str

    def pick(
        self,
        rng,
        *,
        below: int | None = None,
        above: int | None = None,
        reject=None,
    ) -> int:
        """制約を満たす候補から 1 つ選ぶ。`reject(value, unit)` が真の候補は使わない。"""
        cands = [c for c in self.choices if (below is None or c < below) and (above is None or c > above)]
        allowed = [c for c in cands if not (reject and reject(c, self.unit))]
        if not allowed:
            raise PackError(
                f"{self.key}: 制約（<{below} / >{above} / 表記の衝突）を満たす候補が無い {self.choices}"
            )
        return allowed[rng.randrange(len(allowed))]


@dataclass(frozen=True)
class Subject:
    """計算規定を足す題材（1 つの保険金・判定）。"""

    key: str
    benefit: str
    anchor: str
    trigger: str
    patterns: tuple[str, ...]
    requires_terms: tuple[str, ...] = field(default_factory=tuple)
    inputs: dict[str, dict] = field(default_factory=dict)
    vocab: dict[str, str] = field(default_factory=dict)
    params: dict[str, Range] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class Pack:
    genre: str
    subjects: tuple[Subject, ...]
    ranges: dict[str, Range]
    chapters: dict[str, tuple[str, ...]]
    vocab: dict[str, str]
    #: 用語の概念 → 既定の約款で使われうる用語ID（優先順）
    term_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: 用語が無いときに使う平語
    fallbacks: dict[str, str] = field(default_factory=dict)

    def subject(self, key: str) -> Subject:
        for s in self.subjects:
            if s.key == key:
                return s
        raise PackError(f"{self.genre}: 題材 {key} が無い")

    def range_of(self, subject: Subject, key: str) -> Range:
        return subject.params.get(key) or self.ranges.get(key) or _missing(self.genre, key)

    def word(self, key: str, subject: Subject | None = None) -> str:
        """語彙の引き当て（題材の語彙 → 種目の語彙）。"""
        if subject and key in subject.vocab:
            return subject.vocab[key]
        if key in self.vocab:
            return self.vocab[key]
        raise PackError(f"{self.genre}: 語彙 {key} が無い")


def _missing(genre: str, key: str) -> Range:
    raise PackError(f"{genre}: パラメータの値域 {key} が無い（packs/{genre}.yaml に足す）")


def _range(key: str, raw: dict) -> Range:
    if "choices" not in raw or "unit" not in raw:
        raise PackError(f"値域 {key} に choices と unit が要る")
    return Range(key, tuple(int(c) for c in raw["choices"]), raw["unit"])


@functools.cache
def concepts() -> dict[str, Concept]:
    raw = _load_yaml(PACKS_DIR / "concepts.yaml")
    out: dict[str, Concept] = {}
    for key, c in raw.items():
        out[key] = Concept(
            key=key,
            arg=c.get("arg", key),
            desc=c["desc"],
            type=c["type"],
            unit=c.get("unit"),
            origin=c.get("origin", "claim_fact"),
            min=c.get("min"),
            max=c.get("max"),
            optional=bool(c.get("optional", False)),
            values=tuple(c.get("values", ())),
        )
    return out


@functools.cache
def load(genre: str) -> Pack:
    raw = _load_yaml(PACKS_DIR / f"{genre}.yaml")
    if raw.get("genre") != genre:
        raise PackError(f"packs/{genre}.yaml の genre が {raw.get('genre')!r} になっている")
    ranges = {k: _range(k, v) for k, v in (raw.get("param_ranges") or {}).items()}
    known = concepts()
    subjects = []
    for s in raw.get("subjects") or []:
        inputs = {}
        for role, spec in (s.get("inputs") or {}).items():
            spec = {"concept": spec} if isinstance(spec, str) else dict(spec)
            if spec["concept"] not in known:
                raise PackError(f"{genre}/{s['key']}: 知らない概念 {spec['concept']}（concepts.yaml に足す）")
            inputs[role] = spec
        subjects.append(
            Subject(
                key=s["key"],
                benefit=s["benefit"],
                anchor=s.get("anchor", "body"),
                trigger=s["trigger"],
                patterns=tuple(s.get("patterns") or ()),
                requires_terms=tuple(s.get("requires") or s.get("requires_terms") or ()),
                inputs=inputs,
                vocab=dict(s.get("vocab") or {}),
                params={k: _range(k, v) for k, v in (s.get("params") or {}).items()},
                note=s.get("note", ""),
            )
        )
    return Pack(
        genre=genre,
        subjects=tuple(subjects),
        ranges=ranges,
        chapters={k: tuple(v) for k, v in (raw.get("chapters") or {}).items()},
        vocab=dict(raw.get("vocab") or {}),
        term_aliases={k: tuple(v) for k, v in (raw.get("term_aliases") or {}).items()},
        fallbacks=dict(raw.get("fallbacks") or {}),
    )


def available() -> list[str]:
    return sorted(p.stem for p in PACKS_DIR.glob("*.yaml") if p.stem not in ("concepts", "limits"))
