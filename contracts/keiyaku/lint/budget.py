"""ページ数の見積り（docs/rendering.md §6.10）。

style の `chars_per_page_estimate`（`scripts/calibrate_styles.py` で実測較正した値）を基準に、
表は 0.6 倍、図は固定高として換算する。**描画後の実ページ数が正**で、ここでの見積りは
執筆中に削る判断をするための目安。
"""

from __future__ import annotations

from dataclasses import dataclass

from keiyaku.blueprints import Blueprint
from keiyaku.lint.walk import iter_blocks, iter_texts
from keiyaku.models import Figure, Formula, SourceDraft, Table

# --- 係数は 2026-09-21 に P4-c の7文書（実ページ 11〜17）で最小二乗的に較正した。
#     較正前は最大 +28%／−11% の系統誤差があり、L09 の warn が恒常的に出て無視される状態だった。
#     字数は**トークンを解いた平文**で数える（生の RichText を数えていた不具合を同時に修正）。
#     較正後の最大相対誤差は 5.6%。
#: 表は罫線と余白ぶん縦に伸びるが、見出しを別項で数えるようにしたら 1.0 で足りた
TABLE_FACTOR = 1.25
#: 図 1 点が占めるおおよその高さ（ページに対する割合）
FIGURE_PAGE_SHARE = 0.24
#: 算式 1 点
FORMULA_PAGE_SHARE = 0.04
#: 見出し 1 つ（部・章・節・条・項…）が食う高さ。
#: 定款のように条が多く本文が短い文書は、字数だけで見ると必ず過小評価になる。
HEADING_PAGE_SHARE = 0.005
#: 表紙・目次でおおよそ使うページ数
#: 前付けの取り分。**文書が実際に持つ前付けから算出する**（固定値にしない）。
#: yakkan は「表紙＋目次＋前付け表」を前提に 3.0 の固定値だったが、
#: **契約書は表紙も目次も持たない**ので、3 ページの下駄が常に乗って推定が実測を下回れなくなり、
#: `chars_per_page_estimate` の較正が上限に張り付いた（2026-09-26 に実測で発覚）。
#: 保険の値は「表紙 1.0 ＋ 目次 1.0 ＋ 目次行（見出し 200 個 × 0.004）0.8 ＝ 2.8」で再現できる。
COVER_PAGES = 1.0
TOC_BASE_PAGES = 1.0
#: 目次 1 行ぶんのページ取り分（1 ページ 250 行相当）
TOC_LINE_PAGE_SHARE = 0.004


@dataclass(frozen=True)
class PageEstimate:
    pages: float
    body_chars: int
    table_chars: int
    figures: int
    detail: str


def estimate_pages(
    draft: SourceDraft, blueprint: Blueprint, chars_per_page: int | None = None
) -> PageEstimate:
    if chars_per_page is None:
        from keiyaku.styles import load_style

        try:
            chars_per_page = load_style(blueprint.default_style).chars_per_page_estimate
        except FileNotFoundError:
            chars_per_page = 1500

    table_ids = {b.id for b, _o, _a in iter_blocks(draft) if isinstance(b, Table)}
    body_chars = table_chars = 0
    for owned in iter_texts(draft):
        if _is_metadata(owned.path):
            continue  # 描画されない文字列は数えない
        # **トークンを解いた平文の長さで数える**。生の RichText を数えていたため、
        # `{term:liability_period}`（生23字／表示4字）のような長い id を丁寧に使った文書ほど
        # 不利になっていた（travel 担当の指摘。生21,138字 vs 平文16,097字）。
        length = len(_plain_length_text(owned.text)) if owned.rich else len(owned.text)
        if _owner_table(owned.owner_id, owned.path, table_ids):
            table_chars += length
        else:
            body_chars += length

    figures = sum(1 for b, _o, _a in iter_blocks(draft) if isinstance(b, Figure))
    formulas = sum(1 for b, _o, _a in iter_blocks(draft) if isinstance(b, Formula))
    headings = _count_headings(draft)

    front_pages = 0.0
    if draft.front_matter.cover is not None:
        front_pages += COVER_PAGES
    if draft.front_matter.toc is not None:
        front_pages += TOC_BASE_PAGES + headings * TOC_LINE_PAGE_SHARE

    pages = (
        front_pages
        + body_chars / chars_per_page
        + table_chars * TABLE_FACTOR / chars_per_page
        + figures * FIGURE_PAGE_SHARE
        + formulas * FORMULA_PAGE_SHARE
        + headings * HEADING_PAGE_SHARE
    )
    detail = (
        f"前付け{front_pages:.2f}頁 + 本文{body_chars}字 + 表{table_chars}字×{TABLE_FACTOR:.2f}"
        f" + 図{figures}点 + 算式{formulas}点 + 見出し{headings}個 / {chars_per_page}字per頁"
    )
    return PageEstimate(
        pages=pages, body_chars=body_chars, table_chars=table_chars, figures=figures, detail=detail
    )


def _plain_length_text(text: str) -> str:
    """字数を数えるための平文。トークンは「描画される幅」に近い形に置き換える。

    正確な解決（`{ref:}` のラベル導出）は build の仕事なので、ここでは
    - `{term:id}` / `{const:key}` → id / key をそのまま（実際の語は同程度の長さ）
    - `{ref:id}` → 「第１条（見出し）」相当の目安として固定長
    - 装飾（`{b:}` `{u:}` `{ruby:}`）→ 中身だけ
    に落とす近似で足りる。
    """
    import re

    out = text
    out = re.sub(r"\{ruby:([^|{}]*)\|[^{}]*\}", r"\1", out)
    out = re.sub(r"\{(?:b|u):", "", out)
    out = re.sub(r"\{ref:[^{}]*\}", "第００条（○○○○）", out)  # 参照の解決結果の目安
    out = re.sub(r"\{(?:term|const):([^{}]*)\}", lambda m: "○" * max(2, len(m.group(1)) // 3), out)
    out = re.sub(r"\{fn:\d+\}", "（＊０）", out)
    out = out.replace("{br}", "").replace("{auto_label}", "")
    out = re.sub(r"\{[^{}]*\}", "", out)  # 取りこぼしたトークン
    return out.replace("}", "").replace("{{", "{")


def _count_headings(draft: SourceDraft) -> int:
    """見出しの総数（部・章・節・条・項・号…）。ノード 1 つ＝見出し 1 つ。"""
    count = 0

    def walk(nodes: list) -> None:
        nonlocal count
        for node in nodes:
            count += 1
            walk(node.children or [])

    walk(draft.body)
    walk(draft.appendices)
    return count


#: 描画されない（＝ページを消費しない）文字列の場所。
#: 図の `alt` / `facts` は正解データ用のメタで PDF には出ない。
#: `defined_terms` も、本文の定義表として別に書かれるので二重に数えない。
METADATA_SUFFIXES = (".alt",)
METADATA_MARKERS = (".facts[", ".diagram")


def _is_metadata(path: str | None) -> bool:
    if not path:
        return False
    if path.endswith(METADATA_SUFFIXES) or any(m in path for m in METADATA_MARKERS):
        return True
    # defined_terms（id.definition / id.term / id.notes[n]）は本文の定義表と重複する
    return path.endswith((".definition", ".term")) or ".notes[" in path and path.count(".") == 1


def _owner_table(owner_id: str, path: str | None, table_ids: set[str]) -> bool:
    if owner_id in table_ids:
        return True
    return any(owner_id.startswith(t + "__") for t in table_ids)
