"""定型条のライブラリ（CLAUDE.md §7.6 / `library/clauses/<scheme>/<clause_id>.json`）。

告知義務・通知義務・事故発生時の義務のような、どの商品にも出てくる条を一度オリジナルで書き、
パラメータ差替えと言い換えで再利用する。**ライブラリ文もすべてオリジナル**（§0.4-1）。

ディレクトリは `<doctype>` ではなく **`<scheme>`**（numbering の方式名）で切る。
全 doctype で共有する一般条項は `common/` に置く（docs/repo_layout.md）。
同じ番号方式のジャンルは条の書き方も共通で、7 ジャンルぶん重複して持つ意味が無いため
（docs/decisions.md 2026-09-21）。ジャンル固有の条は `applies_to` で絞る。

**本文中のプレースホルダ**

- `{ref:$p2}` … 同じ条の第 2 項への参照。`$pN` は compose がノード id に置き換える。
- `{const:<key>}` … `constants` に宣言した値。scaffold が `meta.constants` へ写す。
- `{term:<id>}` … `terms_used` に宣言した定義語。scaffold が `defined_terms` に枠を作る。
- `{fn:<n>}` … `footnotes` に対応する脚注。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from keiyaku.models import Block, Model, NumberingScheme, RichText

LIBRARY_DIR = Path(__file__).resolve().parent.parent / "library" / "clauses"


class ClauseParagraph(Model):
    """条の 1 項。`blocks` には表・算式などを置ける。"""

    text: RichText
    blocks: list[Block] = Field(default_factory=list)


class ClauseFootnote(Model):
    n: int
    text: RichText


class ClauseVariant(Model):
    """同じ条の言い換え。seed で 1 つ選ぶ。"""

    id: str
    #: 言い回しの傾向（執筆者と reviewer への手がかり）
    tone: Literal["standard", "concise", "detailed"] = "standard"
    paragraphs: list[ClauseParagraph]
    footnotes: list[ClauseFootnote] = Field(default_factory=list)


class Clause(Model):
    clause_id: str
    scheme: NumberingScheme
    title_options: list[str]
    #: 使ってよいジャンル（空ならその scheme の全ジャンル）
    #: 適用する doctype（空なら全 doctype）。enum にしない（blueprints/ が正本）。
    applies_to: list[str] = Field(default_factory=list)
    #: 文書の `meta.constants` に入れる値。本文からは `{const:key}` で参照する
    constants: dict[str, str] = Field(default_factory=dict)
    #: 使う定義語の id。scaffold が `defined_terms` に枠を作る
    terms_used: list[str] = Field(default_factory=list)
    variants: list[ClauseVariant]

    def variant(self, rng) -> ClauseVariant:
        return rng.choice(self.variants)


def load_clause(scheme: str, clause_id: str, library_dir: Path | None = None) -> Clause:
    path = (library_dir or LIBRARY_DIR) / scheme / f"{clause_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"定型条が無い: {path}")
    return Clause.model_validate(json.loads(path.read_text(encoding="utf-8")))


def available_clauses(scheme: str, library_dir: Path | None = None) -> list[str]:
    directory = (library_dir or LIBRARY_DIR) / scheme
    return sorted(p.stem for p in directory.glob("*.json")) if directory.is_dir() else []


def load_all(scheme: str, library_dir: Path | None = None) -> dict[str, Clause]:
    return {cid: load_clause(scheme, cid, library_dir) for cid in available_clauses(scheme, library_dir)}
