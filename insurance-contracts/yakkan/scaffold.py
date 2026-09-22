"""blueprint ＋ seed → 執筆用スケルトン（CLAUDE.md §7.2-1）。

    uv run yakkan scaffold --genre auto --content-id auto-0001 --seed 1

`content/<cid>/doc.json` と `parts/*.json` を作る。各ノードには
**見出し候補・TODO・必須要素・推定字数・安定 id** を埋め込み、執筆者（Claude）が穴を埋める。
定型条（`library/clauses/`）を指定したノードは、本文まで入った状態で展開する。

**番号ラベルは書かない**（CLAUDE.md §2-2）。見出しは `title` だけ、参照は `{ref:}`。
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from yakkan.blueprints import Blueprint, SkeletonNode, load_blueprint
from yakkan.ids import node_id
from yakkan.library import Clause, ClauseVariant, load_clause
from yakkan.models import SCHEMA_VERSION

#: 執筆者への指示を書くキー。lint は無視し、build は落とす
TODO_KEY = "_todo"

#: 数字表記をそろえる対象のキー（構造値や id には触らない）
TEXT_KEYS = frozenset({"text", "caption", "title", "alt", "label", "meaning", "question", "note", "value"})


def _normalize_text_values(value, convert):
    """dict / list をたどり、本文にあたるキーの文字列だけ変換する。"""
    if isinstance(value, dict):
        return {
            k: (convert(v) if k in TEXT_KEYS and isinstance(v, str) else _normalize_text_values(v, convert))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_normalize_text_values(v, convert) for v in value]
    return value


#: 本文中のトークン（この中の数字は変換しない）
_TOKEN = re.compile(r"\{[a-z_]+:[^}]*\}|\{auto_label\}|\{br\}")
_FULLWIDTH = str.maketrans("0123456789", "０１２３４５６７８９")
_HALFWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")

#: 奥付に必ず入れる定型文（CLAUDE.md §7.5）
DISCLAIMER = (
    "本冊子は、文書読取技術の検証を目的として作成された架空の約款です。"
    "記載の会社・商品・連絡先は実在しません。"
)

#: 定型条が使う定義語の既定（scaffold が defined_terms の枠を作る）
TERM_SEEDS: dict[str, tuple[str, str]] = {
    "policyholder": ("保険契約者", "ハ"),
    "insured": ("被保険者", "ハ"),
    "insured_object": ("保険の対象", "ハ"),
    "company": ("当会社", "タ"),
}


@dataclass
class ScaffoldResult:
    content_dir: Path
    doc: dict[str, Any]
    parts: dict[str, dict[str, Any]]
    #: 執筆が必要な箇所の数
    todo_count: int = 0
    notes: list[str] = field(default_factory=list)


def pick(rng: random.Random, weights: dict[str, float]) -> str:
    """重み付きで 1 つ選ぶ。"""
    keys = sorted(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def _title(rng: random.Random, options: list[str], fallback: str) -> str:
    return rng.choice(options) if options else fallback


def _shuffle_children(
    rng: random.Random, blueprint: Blueprint, nodes: list[SkeletonNode]
) -> list[SkeletonNode]:
    """variants.order_shuffle で許された集合だけ並べ替える。"""
    order = list(nodes)
    for group in blueprint.variants.order_shuffle:
        positions = [i for i, n in enumerate(order) if n.id in group]
        if len(positions) < 2:
            continue
        picked = [order[i] for i in positions]
        rng.shuffle(picked)
        for i, node in zip(positions, picked, strict=True):
            order[i] = node
    return order


class Scaffolder:
    """1 文書ぶんのスケルトンを組み立てる。"""

    def __init__(self, blueprint: Blueprint, content_id: str, seed: int) -> None:
        self.blueprint = blueprint
        self.content_id = content_id
        self.seed = seed
        self.rng = random.Random(seed)
        # variants の抽選はここで一度だけ行い、本文の数字表記にも反映する
        self.digit_style = pick(self.rng, blueprint.variants.digit_style)
        self.constants: dict[str, str] = {}
        self.terms: dict[str, tuple[str, str]] = {}
        self.todo_count = 0
        self.notes: list[str] = []

    # --- ノード ------------------------------------------------------------

    def node(self, spec: SkeletonNode, parent_id: str | None, index: int) -> dict[str, Any]:
        nid = (
            spec.id
            if parent_id is None or spec.id.startswith(parent_id)
            else node_id(parent_id, spec.kind, index)
        )
        title = _title(self.rng, spec.title_options, "")
        out: dict[str, Any] = {"id": nid, "kind": spec.kind}
        if title:
            out["title"] = title
        if spec.kind in ("chapter", "part") and self.blueprint.front_matter.toc_with_summaries:
            out["summary"] = ""
            self.todo_count += 1

        if spec.clause:
            children, blocks = self.expand_clause(spec.clause, nid)
            if children:
                out["children"] = children
            if blocks:
                out["blocks"] = blocks
        else:
            children = [
                self.node(child, nid, i + 1)
                for i, child in enumerate(_shuffle_children(self.rng, self.blueprint, spec.children))
            ]
            if children:
                out["children"] = children
            elif spec.kind == "article":
                # 空の条には執筆用の項を 2 つ置く
                out["children"] = [
                    {"id": node_id(nid, "paragraph", i + 1), "kind": "paragraph", "text": ""}
                    for i in range(2)
                ]
                self.todo_count += 2
            elif spec.kind in ("chapter", "section", "part") and not spec.children:
                out["children"] = [{"id": node_id(nid, "paragraph", 1), "kind": "paragraph", "text": ""}]
                self.todo_count += 1

        todo = self.todo_text(spec)
        if todo:
            out[TODO_KEY] = todo
        return out

    def todo_text(self, spec: SkeletonNode) -> str:
        parts: list[str] = []
        if spec.todo:
            parts.append(spec.todo)
        if spec.chars:
            parts.append(f"目安 {spec.chars} 字")
        for req in spec.required:
            label = f"{req.kind}"
            if req.subtype:
                label += f"/{req.subtype}"
            detail = []
            if req.min_count > 1:
                detail.append(f"{req.min_count}件以上")
            if req.min_rows:
                detail.append(f"{req.min_rows}行以上")
            if req.min_cols:
                detail.append(f"{req.min_cols}列以上")
            parts.append(f"必須: {label}" + (f"（{'・'.join(detail)}）" if detail else ""))
        return " / ".join(parts)

    # --- 定型条 ------------------------------------------------------------

    def expand_clause(self, clause_id: str, article_id: str) -> tuple[list[dict], list[dict]]:
        clause = self.load_clause(clause_id)
        variant = clause.variant(self.rng)
        self.constants |= clause.constants
        for term_id in clause.terms_used:
            if term_id in TERM_SEEDS:
                self.terms[term_id] = TERM_SEEDS[term_id]

        children = [
            {
                "id": node_id(article_id, "paragraph", i + 1),
                "kind": "paragraph",
                "text": self.normalize_digits(self.resolve_refs(paragraph.text, article_id)),
                **(
                    {"blocks": [self.localize_block(b, article_id) for b in paragraph.blocks]}
                    if paragraph.blocks
                    else {}
                ),
            }
            for i, paragraph in enumerate(variant.paragraphs)
        ]
        blocks = self.footnote_blocks(variant, article_id)
        return children, blocks

    def load_clause(self, clause_id: str) -> Clause:
        return load_clause(self.blueprint.numbering_scheme, clause_id)

    def normalize_digits(self, text: str) -> str:
        """ライブラリ本文の数字を、この文書の `digit_style` にそろえる。

        ライブラリは 1 つの表記で書いてあるので、そのまま使うと lint L10 が
        「digit_style と逆の数字が混ざっている」と警告する。トークンの中は触らない。
        """
        table = _FULLWIDTH if self.digit_style == "fullwidth" else _HALFWIDTH
        out, last = [], 0
        for m in _TOKEN.finditer(text):
            out.append(text[last : m.start()].translate(table))
            out.append(m.group())
            last = m.end()
        out.append(text[last:].translate(table))
        return "".join(out)

    def resolve_refs(self, text: str, article_id: str) -> str:
        """`{ref:$pN}` を実際のノード id に置き換える。"""
        out = text
        for n in range(1, 10):
            out = out.replace(f"{{ref:$p{n}}}", f"{{ref:{node_id(article_id, 'paragraph', n)}}}")
        return out

    def localize_block(self, block: Any, article_id: str) -> dict:
        """ライブラリのブロック id を、この条の下で一意になるよう付け替える。

        セルの本文にも `{ref:$pN}` が入りうるので、**ブロック全体を文字列として**
        参照解決してから読み直す（段落だけ解決すると表の中に `$p1` が残る）。
        """
        raw = self.resolve_refs(block.model_dump_json(by_alias=True), article_id)
        data = _normalize_text_values(json.loads(raw), self.normalize_digits)
        old_id = data.get("id", "")
        if old_id:
            new_id = f"{old_id}_{article_id}"
            data["id"] = new_id
            for row in data.get("grid", []):
                for cell in row:
                    if "id" in cell and cell["id"].startswith(old_id):
                        cell["id"] = cell["id"].replace(old_id, new_id, 1)
                    if "merged_into" in cell and cell["merged_into"].startswith(old_id):
                        cell["merged_into"] = cell["merged_into"].replace(old_id, new_id, 1)
        return data

    def footnote_blocks(self, variant: ClauseVariant, article_id: str) -> list[dict]:
        if not variant.footnotes:
            return []
        return [
            {
                "type": "footnotes",
                "id": f"fn_{article_id}",
                "notes": [{"n": f.n, "text": self.normalize_digits(f.text)} for f in variant.footnotes],
            }
        ]

    # --- 文書全体 ----------------------------------------------------------

    def build(self) -> ScaffoldResult:
        bp = self.blueprint
        rng = self.rng
        issuer_kind = pick(rng, bp.variants.issuer_kind)
        digit_style = self.digit_style
        has_pet_name = pick(rng, bp.variants.pet_name) == "present"

        body = [
            self.node(spec, None, i + 1) for i, spec in enumerate(_shuffle_children(rng, bp, bp.skeleton))
        ]
        appendices = [self.appendix(spec, i + 1) for i, spec in enumerate(bp.appendices)]

        if bp.riders.count[1] > 0:
            count = rng.randint(*bp.riders.count)
            picked = rng.sample(bp.riders.pool, min(count, len(bp.riders.pool)))
            for i, rider in enumerate(picked):
                body.append(self.rider_node(rider, len(bp.skeleton) + i + 1))
            if picked:
                self.notes.append(f"特約 {len(picked)} 本: {', '.join(picked)}")

        doc = {
            "schema_version": SCHEMA_VERSION,
            "content_id": self.content_id,
            "genre": bp.genre,
            "seed": self.seed,
            "meta": {
                "title": "",
                "subtitle": "",
                "issuer": {"name": "", "kind": issuer_kind, "short_name": ""},
                "product_name": "",
                **({"pet_name": ""} if has_pet_name else {}),
                "edition_date": "2026-10-01",
                "form_code": "",
                "numbering_scheme": bp.numbering_scheme,
                "digit_style": digit_style,
                "disclaimer": DISCLAIMER,
                "constants": dict(sorted(self.constants.items())),
            },
            "front_matter": {
                "cover": {
                    "title": "",
                    "subtitle": "",
                    "issuer_name": "",
                    "form_code": "",
                    "notes": [],
                },
                "toc": {
                    "enabled": True,
                    "with_summaries": bp.front_matter.toc_with_summaries,
                    "depth": bp.front_matter.toc_depth,
                },
            },
            "back_matter": {"colophon": []},
            TODO_KEY: (
                f"meta と front_matter.cover を埋める。会社名・商品名・様式番号はすべて架空にする"
                f"（CLAUDE.md §7.5）。目標 {bp.target_pages[0]}〜{bp.target_pages[1]} ページ、"
                f"本文 {bp.budget.chars_min}〜{bp.budget.chars_max} 字"
            ),
        }
        self.todo_count += 5

        # part は **章ごとに 1 ファイル**に割る（CLAUDE.md §7.2）。
        # 1 ファイルにまとめると、author サブエージェントに並列で書かせるときに衝突する。
        parts: dict[str, Any] = {
            "00_defined_terms.json": {
                "target": "defined_terms",
                TODO_KEY: "定義語を書く。定型条が使う語は枠を作ってあるので definition を埋める",
                "items": self.term_items(),
            }
        }
        for i, node in enumerate(body):
            name = f"{20 + i}_{node['id']}.json"
            parts[name] = {
                "target": "body",
                TODO_KEY: f"{node.get('title') or node['id']} の章。各ノードの {TODO_KEY} を読んで埋め、"
                f"埋めたら {TODO_KEY} を消す",
                "items": [node],
            }
        parts["80_appendix.json"] = {
            "target": "appendices",
            TODO_KEY: "別表・付表。表の行数は blueprint の最小件数を満たすこと",
            "items": appendices,
        }
        parts["90_back.json"] = {
            "target": "colophon",
            TODO_KEY: "奥付。meta.disclaimer と同じ文を必ず入れる（lint L13）",
            "items": [
                {"type": "paragraph", "id": "par_colophon_1", "text": ""},
                {"type": "paragraph", "id": "par_colophon_2", "text": DISCLAIMER},
            ],
        }
        doc["parts"] = list(parts)
        self.todo_count += 2
        return ScaffoldResult(
            content_dir=Path("content") / self.content_id,
            doc=doc,
            parts=parts,
            todo_count=self.todo_count,
            notes=self.notes,
        )

    def term_items(self) -> list[dict]:
        items = []
        for term_id, (word, kana) in sorted(self.terms.items()):
            items.append({"id": term_id, "term": word, "definition": "", "index_kana": kana})
            self.todo_count += 1
        return items

    def appendix(self, spec, index: int) -> dict:
        out = {
            "id": spec.id,
            "kind": "appendix",
            # blueprint の呼び名（「付表」など）を content に写す。build は blueprint を見ないので、
            # ここで持たせないと「付表」と宣言しても「別表」と描かれる。
            **({"kind_label": spec.kind_label} if spec.kind_label != "別表" else {}),
            "title": _title(self.rng, spec.title_options, ""),
            "children": [
                {
                    "id": node_id(spec.id, "appendix_section", 1),
                    "kind": "appendix_section",
                    "title": "",
                    "children": [
                        {
                            "id": node_id(node_id(spec.id, "appendix_section", 1), "paragraph", 1),
                            "kind": "paragraph",
                            "text": "",
                        }
                    ],
                }
            ],
        }
        todo = spec.todo or ""
        if spec.table:
            todo = f"{todo} / 必須: table/{spec.table}（{spec.min_rows}行以上）".strip(" /")
        out[TODO_KEY] = todo
        self.todo_count += 2
        return out

    def rider_node(self, rider_id: str, index: int) -> dict:
        nid = f"rider_{rider_id.removeprefix('rider_')}"
        return {
            "id": nid,
            "kind": "rider",
            "title": "",
            TODO_KEY: "特約。適用条件／用語の定義／補償／普通約款の準用 の4条構成にする",
            "children": [
                {
                    "id": node_id(nid, "article", i + 1),
                    "kind": "article",
                    "title": "",
                    "children": [
                        {
                            "id": node_id(node_id(nid, "article", i + 1), "paragraph", 1),
                            "kind": "paragraph",
                            "text": "",
                        }
                    ],
                }
                for i in range(4)
            ],
        }


def scaffold(genre: str, content_id: str, seed: int, root: Path | None = None) -> ScaffoldResult:
    """スケルトンを作ってディスクに書き出す。"""
    blueprint = load_blueprint(genre)
    result = Scaffolder(blueprint, content_id, seed).build()
    base = (root or Path.cwd()) / "content" / content_id
    result.content_dir = base
    (base / "parts").mkdir(parents=True, exist_ok=True)
    (base / "doc.json").write_text(
        json.dumps(result.doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name, part in result.parts.items():
        (base / "parts" / name).write_text(
            json.dumps(part, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return result
