"""blueprint（ジャンルの設計図）の読み込み（docs/blueprints.md 付録B）。

`blueprints/<genre>.yaml` に「骨組み・必須要素・分量・番号方式・バリエーション候補」を宣言し、
`yakkan scaffold` がここから執筆用スケルトンを作り、lint L04 が必須要素の充足を検査する。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from yakkan.models import DigitStyle, Genre, Model, NodeKind, NumberingScheme, SemanticType

BLUEPRINTS_DIR = Path(__file__).resolve().parent.parent / "blueprints"

#: 必須要素の種類
RequirementKind = Literal["table", "figure", "formula", "box", "footnotes", "list", "term", "badge"]


class Requirement(Model):
    """1 つの必須要素。`min_count` 件以上あること、表なら `min_rows` 行以上あることを求める。"""

    kind: RequirementKind
    #: table なら semantic_type、figure なら diagram の kind、box なら style
    subtype: str | None = None
    min_count: int = 1
    min_rows: int | None = None
    min_cols: int | None = None
    #: どのノードの配下に要るか（未指定なら文書のどこでもよい）
    under: str | None = None
    note: str = ""


class SkeletonNode(Model):
    """骨組みの 1 ノード。`scaffold` がこれを元に空のノードを作る。"""

    id: str
    kind: NodeKind
    title_options: list[str] = Field(default_factory=list)
    #: 執筆者への指示（scaffold が TODO として埋め込む）
    todo: str = ""
    #: このノードの推定字数（scaffold が埋め込み、L09 の見積りに使う）
    chars: int = 0
    #: ライブラリの定型条を使う場合の id（`library/clauses/<scheme>/<id>.json`）
    clause: str | None = None
    required: list[Requirement] = Field(default_factory=list)
    children: list[SkeletonNode] = Field(default_factory=list)
    #: 章の並び替えを許すか（variants の order_shuffle 対象）
    movable: bool = False
    #: 単項のときにラベルを出さない（numbering が siblings で判定するので通常は触らない）
    paragraphs: int = 0


class FrontMatterSpec(Model):
    cover: bool = True
    preface: bool = False
    purpose_index: bool = False
    toc_with_summaries: bool = False
    toc_depth: Literal[1, 2, 3] = 3
    rider_index: bool = False
    petname_table_p: float = 0.0


class RiderSpec(Model):
    count: tuple[int, int] = (0, 0)
    pool: list[str] = Field(default_factory=list)


class AppendixSpec(Model):
    """別表 1 つぶんの下書き。

    `table` は **scaffold が置く表の下書き**であって、lint の検査対象ではない。
    同一ジャンル 3 文書は別表の題材を変えて書くのが前提なので（L15 の重複率を下げるため）、
    `semantic_type` を要件にすると正当な差別化が落ちる。
    lint が見るのは「この別表の中に `min_rows` 行以上の表が 1 つある」ことだけ。
    """

    id: str
    title_options: list[str]
    table: SemanticType | None = None
    min_rows: int = 0
    min_cols: int | None = None
    kind_label: str = "別表"
    #: 執筆の判断で落としてよい別表（落としても warn を出さない）
    optional: bool = False
    todo: str = ""


class Variants(Model):
    """seed で選ぶ揺らぎ（docs/blueprints.md §4.2）。値は重み。"""

    digit_style: dict[DigitStyle, float] = Field(default_factory=lambda: {"fullwidth": 1.0})
    paren_style: dict[str, float] = Field(default_factory=lambda: {"fullwidth": 1.0})
    era: dict[str, float] = Field(default_factory=lambda: {"seireki": 1.0})
    issuer_kind: dict[str, float] = Field(default_factory=lambda: {"stock": 1.0})
    pet_name: dict[str, float] = Field(default_factory=lambda: {"present": 0.5, "absent": 0.5})
    #: 入れ替えてよい章 id の集合（この中だけ順序を変える）
    order_shuffle: list[list[str]] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)


class Budget(Model):
    chars_min: int
    chars_max: int
    #: 条末脚注・欄外注の最小件数（実物は 1 頁あたり脚注 7〜12 件：docs/reference_structures.md）
    footnotes_min: int = 0
    margin_notes_min: int = 0


class Blueprint(Model):
    genre: Genre
    description: str = ""
    target_pages: tuple[int, int]
    numbering_scheme: NumberingScheme
    #: 条見出しの体裁（`above` は見出し文言を条の上に置く。docs/reference_structures.md #12）
    article_heading: Literal["inline", "above", "plain"] = "inline"
    #: 条末脚注の体裁（`remarks_box` は黒丸数字と「第N条　備考」の枠。#13）
    footnote_style: Literal["inline", "remarks_box"] = "inline"
    default_style: str
    front_matter: FrontMatterSpec = Field(default_factory=FrontMatterSpec)
    skeleton: list[SkeletonNode] = Field(default_factory=list)
    riders: RiderSpec = Field(default_factory=RiderSpec)
    required: list[Requirement] = Field(default_factory=list)
    appendices: list[AppendixSpec] = Field(default_factory=list)
    variants: Variants = Field(default_factory=Variants)
    budget: Budget

    def iter_skeleton(self, nodes: list[SkeletonNode] | None = None):
        for node in self.skeleton if nodes is None else nodes:
            yield node
            yield from self.iter_skeleton(node.children)

    def all_requirements(self) -> list[Requirement]:
        out = list(self.required)
        for node in self.iter_skeleton():
            out.extend(node.required)
        # 別表の中身も検査する。ここに入れていなかったため、
        # 「rate 5行以上の表が文書のどこかに 1 つ」しか見ておらず、
        # **別表が空でも通ってしまっていた**（travel で発覚）。
        #
        # ただし **`subtype`（題材）は指定しない**。同一ジャンル 3 文書は別表の題材を
        # 変えて書くのが前提で（L15 の重複率を下げるため）、`semantic_type` を
        # error にすると正当な差別化が落ちる。題材の食い違いは L04 が warn で見る。
        for spec in self.appendices:
            if spec.table is None:
                continue
            out.append(
                Requirement(
                    kind="table",
                    subtype=None,
                    min_count=1,
                    min_rows=spec.min_rows or None,
                    min_cols=spec.min_cols,
                    under=spec.id,
                    note=f"{spec.kind_label}（{spec.id}）の中に要る",
                )
            )
        return out


SkeletonNode.model_rebuild()
Blueprint.model_rebuild()


def load_blueprint(genre: str, blueprints_dir: Path | None = None) -> Blueprint:
    path = (blueprints_dir or BLUEPRINTS_DIR) / f"{genre}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"blueprint が無い: {path}")
    return Blueprint.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def available_genres(blueprints_dir: Path | None = None) -> list[str]:
    return sorted(p.stem for p in (blueprints_dir or BLUEPRINTS_DIR).glob("*.yaml"))
