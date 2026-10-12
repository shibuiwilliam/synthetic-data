"""評価向けの派生成果物を書き出す（docs/eval_dataset_plan.md P5・P8）。

`source.json` / `layout.json` / `answer.json` は正解の一次資料で、形を変えない。
評価スクリプトが最初に読むための**平らな索引**をここで作る。

- `elements.jsonl`：1 行 1 要素。テキスト・構造位置（citation）・ページ・bbox・
  表や図や列挙の中での位置を 1 か所にまとめる。
- `passages.jsonl` / `queries.jsonl` / `qrels.jsonl`：検索評価用（`yakkan.search_set`）。
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from yakkan.answer import load_answer
from yakkan.export_models import (
    ElementEnumeration,
    ElementFigure,
    ElementFigureNode,
    ElementRow,
    ElementTable,
    ExportRow,
)
from yakkan.models import Answer

#: 表のセル id（`<table_id>__r{row}c{col}`）
CELL_ID = re.compile(r"^(?P<table>.+)__r(?P<row>\d+)c(?P<col>\d+)$")

#: 本文として扱う region（ヘッダ・フッタは furniture）
BODY_REGIONS = frozenset({"body", "table", "margin_note"})


def _regions(answer: Answer) -> dict[str, str]:
    """要素 id → その要素が最初に現れた行の region。"""
    out: dict[str, str] = {}
    for page in answer.layout.pages:
        for line in page.text_lines:
            if line.element_id and line.element_id not in out:
                out[line.element_id] = line.region
    return out


def _normalize_bbox(bbox: list[float], size: tuple[float, float]) -> list[float]:
    width, height = size
    if not width or not height:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        round(bbox[0] / width, 6),
        round(bbox[1] / height, 6),
        round(bbox[2] / width, 6),
        round(bbox[3] / height, 6),
    ]


def _enum_index(answer: Answer) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for enum in answer.source.derived.enumerations:
        for item in enum.items:
            out[item.id] = {
                "enum_id": enum.id,
                "enum_source": enum.source,
                "enum_owner_id": enum.owner_id,
                "index": item.index,
                "label": item.label,
            }
    return out


def _figure_index(answer: Answer) -> dict[str, dict[str, Any]]:
    """図のノード id → 図の情報。ノード bbox は `layout.figures[].nodes` にある。"""
    out: dict[str, dict[str, Any]] = {}
    for figure_id, derived in answer.source.derived.figures.items():
        layout = answer.layout.figures.get(figure_id)
        for node in derived.graph.nodes:
            box = (layout.nodes.get(node.id) if layout else None) or None
            out[f"{figure_id}::{node.id}"] = {
                "figure_id": figure_id,
                "node_id": node.id,
                "role": node.role,
                "label": node.label,
                "page": layout.page if layout else 0,
                "bbox": list(box) if box else None,
            }
    return out


def element_rows(answer: Answer) -> list[ElementRow]:
    """`elements.jsonl` の行を作る。**テキストか bbox のどちらかを持つ要素**をすべて出す。"""
    source = answer.source
    layout = answer.layout
    derived = source.derived
    regions = _regions(answer)
    enums = _enum_index(answer)
    size = tuple(layout.page_size_pt)
    header_paths = {
        cell_id: path for table in derived.tables.values() for cell_id, path in table.header_path.items()
    }
    caption_of = {tid: t.caption_label for tid, t in derived.tables.items()}
    caption_of |= {fid: f.caption_label for fid, f in derived.figures.items()}

    rows: list[ElementRow] = []
    ids = sorted(set(derived.plain_text) | set(layout.elements))
    for element_id in ids:
        element = layout.elements.get(element_id)
        plain = derived.plain_text.get(element_id)
        label_info = derived.labels.get(element_id)
        fragments = element.fragments if element else []
        row = ElementRow(
            doc_id=answer.doc_id,
            content_id=source.content_id,
            style_id=layout.style_id,
            genre=source.genre,
            element_id=element_id,
            kind=element.kind if element else "unrendered",
            region=regions.get(element_id, "body"),
            text=plain.without_label if plain else "",
            text_with_label=plain.with_label if plain else "",
            label=(label_info.label if label_info else None) or (element.label if element else None),
            heading_text=label_info.heading_text if label_info else None,
            node_kind=label_info.kind if label_info else None,
            citation=label_info.citation if label_info else "",
            parent_id=label_info.parent_id if label_info else None,
            path_ids=list(label_info.path_ids) if label_info else [],
            pages=sorted({f.page for f in fragments}),
            bboxes=[list(f.bbox) for f in fragments],
            bboxes_norm=[_normalize_bbox(list(f.bbox), size) for f in fragments],
            repeated=any(f.repeated for f in fragments),
        )
        match = CELL_ID.match(element_id)
        if match and match.group("table") in derived.tables:
            table_id = match.group("table")
            path = header_paths.get(element_id)
            row.table = ElementTable(
                table_id=table_id,
                caption_label=caption_of.get(table_id),
                row=int(match.group("row")),
                col=int(match.group("col")),
                row_headers=list(path.row_headers) if path else [],
                col_headers=list(path.col_headers) if path else [],
            )
        if element_id in caption_of and element_id in derived.figures:
            figure = derived.figures[element_id]
            row.figure = ElementFigure(
                caption_label=figure.caption_label,
                node_count=len(figure.graph.nodes),
                edge_count=len(figure.graph.edges),
                paths=figure.paths,
            )
        if element_id in enums:
            row.enumeration = ElementEnumeration(**enums[element_id])
        rows.append(row)

    # 図のノードは layout.elements に出ないので、別の行として足す
    for key, info in _figure_index(answer).items():
        owner = derived.labels.get(info["figure_id"])
        rows.append(
            ElementRow(
                doc_id=answer.doc_id,
                content_id=source.content_id,
                style_id=layout.style_id,
                genre=source.genre,
                element_id=key,
                kind="figure_node",
                region="figure",
                text=info["label"],
                text_with_label=info["label"],
                citation=owner.citation if owner else "",
                parent_id=info["figure_id"],
                pages=[info["page"]] if info["page"] else [],
                bboxes=[info["bbox"]] if info["bbox"] else [],
                bboxes_norm=[_normalize_bbox(info["bbox"], size)] if info["bbox"] else [],
                figure_node=ElementFigureNode(
                    figure_id=info["figure_id"],
                    node_id=info["node_id"],
                    role=info["role"],
                ),
            )
        )
    return rows


def write_jsonl(rows: Sequence[ExportRow], path: Path) -> int:
    """1 行 1 モデルで書き出す。行の形はモデルの `jsonl_row()` が決める。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row.jsonl_row(), ensure_ascii=False, sort_keys=True) + "\n")
    return len(rows)


def export_dataset(dataset_dir: Path) -> dict[str, int]:
    """1 文書ぶんの評価向け派生成果物を書き出す。"""
    from yakkan.search_set import build_passages

    answer = load_answer(dataset_dir)
    counts = {"elements": write_jsonl(element_rows(answer), dataset_dir / "elements.jsonl")}
    counts["passages"] = write_jsonl(build_passages(answer), dataset_dir / "passages.jsonl")
    return counts


#: Hugging Face のデータセット ID。カードの引用例・`load_dataset()` の例に埋め込む。
#: **HF はリポジトリ直下の `README.md` だけをデータセットカードとして読む**ので、
#: 配布面の要約も本文も 1 枚にまとめてある（旧 `DATASET_CARD.md` は廃止。
#: docs/decisions.md 2026-10-05）。
HF_REPO_ID = "cvusk/japanese-insurance-document-understanding"

#: 検索評価セット（`dataset/search/`）の Hugging Face データセット ID。
#: **文書本体とは別のリポジトリとして配る**（2026-10-08 決定。docs/decisions.md）。
#: 本体は PDF とページ画像で 846 MiB あり、検索だけを試す人にそれを引かせる理由が無い。
#: カードも「読み取りの説明」と「検索の説明」が混ざる。評価セットは JSONL 4 本・19 MiB。
#: **ローカルの置き場所は `dataset/search/` のまま**で、そのディレクトリを別リポジトリの
#: 直下として上げる（`yakkan eval --search-run` の既定パスと docs の参照を壊さないため）。
SEARCH_HF_REPO_ID = "cvusk/japanese-insurance-document-understanding-retrieval"

#: 配布ライセンス。`TASK.md` T11 で 2026-10-05 に **CC BY 4.0** と決まった。
#: 変えるときは `LICENSE` の本文（`LICENSE_NOTICE`）と対で変える。
LICENSE_ID = "cc-by-4.0"
LICENSE_NAME = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_LEGALCODE_URL = "https://creativecommons.org/licenses/by/4.0/legalcode"

#: 学習・蒸留の禁止の出どころ（Anthropic Usage Policy）。本データセットの文章・QA・図の alt は
#: Claude Code セッション内で Claude が書いた Output であり、AUP は「入力と出力を AI モデルの
#: 学習（model scraping / model distillation を含む）に用いること」を事前許可なしに禁じている。
#: **これは告知であってライセンス条件ではない。** CC BY 4.0 第 2 条(a)(5)(B)が下流への追加制限を
#: 禁じているので、CC BY の付与条件としては書けない（書くと CC BY 違反になる）。
#: `LICENSE`（英語）とカード（日本語）で同じことを言う。**表現を変えるときは両方を直す。**
AUP_URL = "https://www.anthropic.com/legal/aup"
COPYRIGHT_HOLDER = "Yusuke Shibui (shibuiwilliam)"
COPYRIGHT_YEAR = "2026"

#: カード・LICENSE・帰属・引用に出る名前。2 つのデータセットで**別の名前**を持つ。
#: **Hub の `pretty_name` と英語面の見出しは英語**にする（姉妹プロジェクト contracts と同じ設計。
#: HF の閲覧者は日本語話者に限らないので、英語面を先に置き日本語面を続ける。
#: docs/decisions.md 2026-10-09）。
PRETTY_NAME_EN = "Japanese Insurance Policy Document Understanding (synthetic, with full ground truth)"
SEARCH_PRETTY_NAME_EN = "Japanese Insurance Policy Retrieval Evaluation Set (synthetic, derived ground truth)"
PRETTY_NAME = "日本語保険約款 合成ドキュメントデータセット（yakkan-synth）"
SEARCH_PRETTY_NAME = "日本語保険約款 合成検索評価セット（yakkan-synth search）"

#: 生成コードの置き場。カードから案内する（**公開リポジトリであることの確認は人間の判断**）。
CODE_REPO = "https://github.com/shibuiwilliam/synthetic-data/tree/main/insurance-contracts"

#: 2 枚のカード（文書本体・検索評価セット）で**同じ文面を使う告知**。
#: 片方だけ直すと食い違うので定数に出してある。`{aup_url}` は書き出し時に埋める。
FICTITIOUS_JA = """## ⚠ すべて架空である

**会社名・商品名・ペットネーム・連絡先・URL・様式番号・人物名・金額はすべて架空**で、
実在の保険会社・実在の商品・実在の約款とは一切関係がない。
電話番号はゼロ埋め（`0120-000-000`）、ドメインは `example.jp` / `example.co.jp` /
`example.com` のみ。各文書の奥付に免責を明記してある。

これらの固有名詞は、可能な限り実在しないものを選ぶよう努めている。
万が一、実在する社名・商品名・人物名等と偶然一致していることが判明した場合は、
該当箇所を修正する。

**実在の約款の文章は、部分的にも、語順を変えただけでも含まれていない。**
参考にしたのは構造・要素の種類・レイアウト慣行のみである。

**保険商品としての内容は検証されていない。** 条文は読み取り評価のために書いたダミーで、
保険実務・法務の校閲を受けていない。**実務の参考・商品の比較・法的な参照に使ってはならない。**
"""

#: 学習・蒸留の禁止（英語面）。**`What it is for` より前**に置く。
#: 文面は `LICENSE_NOTICE` の `NOT FOR TRAINING AI MODELS` と同じことを言う
#: （姉妹プロジェクト contracts の `NO_TRAINING_EN` と同じ設計）。
NO_TRAINING_EN = """## ⚠ Not for training AI models

THIS DATASET MUST NOT BE USED TO TRAIN, FINE-TUNE, DISTILL, OR OTHERWISE DEVELOP
ANY ARTIFICIAL INTELLIGENCE OR MACHINE LEARNING MODEL, INCLUDING LARGE LANGUAGE
MODELS (LLMs) AND VISION-LANGUAGE MODELS (VLMs).

The policy clauses, tables, figure descriptions and QA pairs in this dataset were
written by Claude (Anthropic) inside a Claude Code session; they are Outputs of
that service. Anthropic's Usage Policy prohibits "Utilization of inputs and
outputs to train an AI model (e.g., 'model scraping' or 'model distillation')
without prior authorization from Anthropic" ({aup_url}).

EVALUATION IS NOT TRAINING. Benchmarking or evaluating document-reading systems
(OCR, layout analysis, VLMs, structured extraction), retrieval and RAG pipelines,
or AI agents against this dataset is the purpose it was built for, and nothing
above restricts it. Neither does using it as test fixtures, as few-shot examples,
or as a retrieval corpus at inference time. What is excluded is updating model
weights from it.

This is a NOTICE, not an additional condition of the license above. CC BY 4.0
Section 2(a)(5)(B) forbids imposing further restrictions on downstream recipients,
so this statement is not offered as a term of that grant and does not narrow it.
It tells you about a restriction that arises from Anthropic's Usage Policy and
that binds everyone subject to that policy. If you need to train on data of this
kind, obtain prior authorization from Anthropic first.
"""

#: 学習・蒸留の禁止（告知）。**ライセンス節より前**に置く。LICENSE（英語）と同じことを言う。
NO_TRAINING_JA = """## ⚠ AI モデルの学習・蒸留には使えない

**本データセットを LLM・VLM・その他 AI モデルの学習・ファインチューニング・蒸留・
強化学習の素材に使ってはならない。**

本データセットの文章・QA・図の説明は、Claude Code セッション内で **Claude（Anthropic）が
書いた Output** である。Anthropic の Usage Policy は「入力と出力を AI モデルの学習
（model scraping・model distillation を含む）に用いること」を**事前許可なしに禁じている**
（{aup_url}）。学習に使う必要がある場合は、まず Anthropic の事前許可を得ること。

**評価は学習ではない。** ドキュメント読み取り（OCR・レイアウト解析・VLM・構造化抽出）・
検索／RAG・AI エージェントの**評価とベンチマークは、このデータセットが作られた目的そのもの**で、
上の制限は一切かからない。テストフィクスチャとしての利用、few-shot の実例、
推論時の検索コーパスとしての利用も同じく対象外である。**除かれるのはモデルの重みを更新する用途だけ。**

なお、**この節は告知であってライセンス条件ではない。** CC BY 4.0 は下流の受領者に追加の制限を
課すことを禁じている（第 2 条(a)(5)(B)）ため、上の禁止を CC BY の付与条件として書くことはできず、
書いてもいない。制限の出どころは Anthropic の Usage Policy であり、同ポリシーの適用を受ける者を縛る。
"""

CARD = """---
license: {license_id}
pretty_name: {pretty_name_en}
language:
- ja
multilinguality: monolingual
annotations_creators:
- machine-generated
source_datasets:
- original
task_categories:
- question-answering
- visual-question-answering
- image-to-text
- document-question-answering
- table-question-answering
task_ids:
- extractive-qa
- document-question-answering
tags:
- japanese
- insurance
- legal
- synthetic
- document-understanding
- document-ai
- ocr
- layout-analysis
- table-extraction
- information-extraction
- pdf
size_categories:
- {size_category}
configs:
- config_name: documents
  default: true
  data_files:
  - split: train
    path: documents.jsonl
- config_name: qa
  data_files:
  - split: train
    path: qa.jsonl
---

# {pretty_name_en}

**{n_docs} synthetic Japanese insurance policy documents rendered to PDF, each paired
with complete, machine-generated ground truth** — page text, the clause tree
(part / chapter / article / paragraph / item), tables, figures, cross-references,
defined terms, bounding boxes, reading order, and {n_qa} QA pairs. Every company,
product, pet name, contact detail, form number and amount is **fictional**; no
sentence is copied from a real policy.

- **{n_docs} documents** = {n_contents} written policies, each rendered in 1–2 of
  {n_styles} page layouts, covering **{n_genres} genres** of Japanese insurance
  document, {n_pages} pages in total (20 pages or fewer per document).
- The JSON is the **single source of truth**; the PDF is its deterministic
  rendering (JSON → HTML → PDF), so the paper and the labels cannot disagree.
- 150 dpi page images (`pages/*.png`) are included for OCR / VLM evaluation.
- The corpus-wide retrieval evaluation set (passages / queries / qrels) is a
  **companion dataset**: [`{search_hf_repo_id}`]({search_hf_repo_url}).
- Released under **{license_id}** © {copyright_year} {copyright_holder}. See `LICENSE`.

{no_training_en}
## What it is for

1. OCR / VLM text reading from page images or PDF.
2. Clause-structure extraction — the part→chapter→article→paragraph→item tree and
   where an element sits in it (`第2章 第1条 (1)`).
3. Table structure understanding (row header × column header → value), including
   merged cells, repeated table headers and premium / grade tables.
4. Figure structure (nodes / edges / paths over six diagram kinds).
5. Reference resolution (cross-references between articles, defined terms, 別表).
6. Document QA (extraction, reference following, counting and arithmetic).
7. **Layout robustness**: the same policy body rendered in two page layouts — the
   labels stay identical, only boxes and reading order change.

## What it is **not** for

- **Any real-world insurance use.** The clauses are dummies written for reading
  evaluation; they have not been reviewed by an insurance or legal professional.
  Do not use them as policy terms, for product comparison, or as a legal reference.
- Reproducing real policies (only structure and layout conventions were studied;
  every sentence is original). Every effort is made to avoid company, product and
  person names that exist in the real world; if a coincidental match with a real
  name is found, the affected part will be corrected.
- **Training, fine-tuning or distilling any AI / ML model** (see the section above;
  this is a restriction from Anthropic's Usage Policy, not from the dataset license).
- Language-model pre-training (too small, deliberately narrow subject matter).
- Scanned / photographed / handwritten document evaluation: these PDFs are
  born-digital, with no skew, shadow, noise or seal impressions.
- Vertical writing (縦書き) or ruby (ルビ): the renderer does not produce them, so
  there is no ground truth for them here.

## Configs

| config | rows | what one row is | file |
|---|---|---|---|
| `documents` | {n_doc_rows} | one document — genre, layout, pages, counts | `documents.jsonl` |
| `qa` | {n_qa} | one QA pair — answer in typed columns | `qa.jsonl` |

```python
from datasets import load_dataset
from huggingface_hub import snapshot_download

qa   = load_dataset("{hf_repo_id}", "qa", split="train")
root = snapshot_download("{hf_repo_id}", repo_type="dataset",
                         allow_patterns=["auto-0001--nl-a4-2col-mincho/*"])
```

The per-document directories hold the **authoritative** ground truth
(`source.json`, `layout.json`, `answer.json`, `qa.json`, `elements.jsonl`,
`doc.pdf`, `pages/*.png`); `documents.jsonl` and `qa.jsonl` are flat projections
for the viewer. `elements.jsonl` is **one row per element** — text, structural
citation, page, bounding boxes — and is the file an evaluation script should read
first.

{sample_qa}
## Files

```
manifest.json          every document (pages, QA count, artifacts, checksums, status)
data-card.md           full data card: measured scale, breakdown, verification, limits
documents.jsonl        flat projection of manifest.json (`documents` config)
qa.jsonl               flat projection of every qa.json (`qa` config)
<content_id>--<style_id>/
  doc.pdf  pages/page-001.png …  source.json  layout.json  answer.json  qa.json
  elements.jsonl  passages.jsonl
```

`doc_id` is `<content_id>--<style_id>`. **Two documents with the same
`content_id` have identical text and differ only in layout** — split by
`content_id`, not by `doc_id`.

Read **`data-card.md`** next: it is generated by measuring these files and holds
the scale, the per-genre breakdown, the label vocabulary, the verification
results, and the known limits and biases.

Generator code: {code_repo}

## Citation

```bibtex
@misc{{yakkan_synth,
  title  = {{{pretty_name_en}}},
  author = {{{copyright_holder}}},
  year   = {{{copyright_year}}},
  howpublished = {{Hugging Face Hub}},
  url    = {{{hf_repo_url}}},
  note   = {{Version {dataset_version}. Licensed under {license_id}.}}
}}
```

---

# 日本語版 — 生成した約款データセットの読み方

日本語の保険約款（やっかん）の**構造的特徴を忠実に再現した、完全に架空の文書**と、
その**完全な正解データ**を対にしたデータセット。ドキュメント読み取り
（OCR・レイアウト解析・VLM・構造化抽出）と**検索／RAG** の開発検証用。

**このファイルは `yakkan export` が生成する。手で編集しない**（CLAUDE.md §0.4-3）。

- 生成物は **{license_id}** で配布する（著作権表示：© {copyright_year} {copyright_holder}）。
  本文は `LICENSE`。
- **実務の約款としては使えない**（保険実務・法務の校閲を受けていないダミーである）。
- **AI モデルの学習・蒸留には使えない**（下記）。評価・ベンチマークは対象外。
- **検索評価セット（passages / queries / qrels）は別のデータセットで配布している**：
  [`{search_hf_repo_id}`]({search_hf_repo_url})。文書そのものはこのリポジトリにある。

| | |
|---|---|
| 文書（PDF） | **{n_docs} 点** / **{n_pages} ページ**（1 文書 20 ページ以下） |
| ジャンル | **{n_genres} 種**（下記） |
| 版面（スタイル） | **{n_styles} 種**（A4/B5/横長・1 段/2 段・明朝/ゴシック） |
| QA | **{n_qa} 問**（自動生成 30 問＋執筆 15 問／文書） |
| 検索評価セット | **別のデータセット** `{search_hf_repo_id}`（下記。クエリ {n_kinds} 種） |
| 版 | `{dataset_version}`（`manifest.json` の `dataset_version`） |
| 言語 | 日本語のみ（横書き） |

ジャンル：総合自動車保険・1 日型自動車保険・地震保険・傷害疾病保険・生命保険（ご契約のしおり＋約款）・
保険会社の定款・海外旅行保険・賠償責任保険（ゴルファー保険）・団体保険・重要事項説明書。
**重要事項説明書は「条」を 1 つも持たない**文書で、見出し階層が他と違う。

{fictitious_ja}
{no_training_ja}
## 使い方

```python
from datasets import load_dataset

docs = load_dataset("{hf_repo_id}", "documents")   # 文書の一覧とメタデータ
qa   = load_dataset("{hf_repo_id}", "qa")          # 問答 {n_qa} 問
```

**検索／RAG の評価セット（パッセージ・クエリ・qrels）はここには無い。**
別のデータセット `{search_hf_repo_id}` にある（下記「検索評価セットは別のデータセット」）。

PDF・ページ画像・正解 JSON は 1 文書 1 ディレクトリで入っている。`load_dataset` では
構造が深すぎて扱えないので、**ファイルとして取る**。

```python
from huggingface_hub import snapshot_download

# 1 文書だけ
snapshot_download("{hf_repo_id}", repo_type="dataset",
                  allow_patterns=["auto-0001--nl-a4-2col-mincho/*"])
# ページ画像と正解テキストだけを全文書ぶん
snapshot_download("{hf_repo_id}", repo_type="dataset",
                  allow_patterns=["*/pages/*.png", "*/answer.json"])
```

## 並び

```
manifest.json            全文書の一覧（ページ数・QA 数・成果物・checksums・status）
documents.jsonl          上の 1 行 1 文書版（`documents` コンフィグ）
qa.jsonl                 全文書の QA を 1 行 1 問に平らにしたもの（`qa` コンフィグ）
data-card.md             規模・内訳・検証結果・制限と偏りの実測（**使うか判断するならここ**）
<content_id>--<style_id>/
  doc.pdf                  PDF（フォント埋め込み・テキスト層あり・タグ無し）
  pages/page-001.png …     150dpi のページ画像（VLM の入力）
  source.json              内容＋構造＋意味（レイアウト非依存）＋ derived
  layout.json              描画結果（ページ・要素の bbox・読み順・ヘッダ/フッタ）
  answer.json              ページ別テキスト ＋ outline（**source と layout は内包しない**）
  qa.json                  45 問（自動 30 ＋ 執筆 15）。**QA の正本はこちら**
  elements.jsonl           **1 行 1 要素の平らな索引。評価スクリプトはまずこれを読む**
  passages.jsonl           この文書ぶんの検索パッセージ
```

`doc_id` は `<content_id>--<style_id>`。**同じ `content_id` の別 `style_id` は、本文が同一で
版面だけが違う。** レイアウト頑健性はこの対で測る。学習と評価に分けるときは
**`content_id` で分ける**こと（`doc_id` で分けると同じ文章が両側に入る）。

## 検索評価セットは別のデータセット

検索／RAG の評価セット（パッセージ **{n_passages}** 件・クエリ **{n_queries}** 件・
qrels **{n_qrels}** 行）は、**別のリポジトリ**で配っている。

> **{search_hf_repo_id}** — {search_hf_repo_url}

本体は PDF とページ画像で大半を占めるので、**検索だけを試す人に数百 MiB を引かせない**ため
分けてある（評価セットは JSONL 4 本）。両者は `doc_id` / `content_id` で突き合わせられる。
検索コーパスは重複を避けて **content ごとに 1 スタイルだけ**採っている（{n_corpus_docs} 文書）。

このデータセットの各文書にある `passages.jsonl` は**その 1 文書ぶんのパッセージ**で、
評価セット側の `passages.jsonl`（コーパス全体）と作り方は同じである。
クエリと qrels は評価セット側にしか無い。

## どのファイルを使うか

| やりたいこと | 読むファイル |
|---|---|
| ページ画像から本文を読み取る精度 | `pages/*.png` ＋ `answer.json` の `pages[].text` |
| 文章の**構造内の位置づけ**（第2章 第1条 (1)） | `elements.jsonl` の `citation` / `node_kind` / `path_ids` |
| 見出しツリー | `answer.json` の `outline`（`kind` / `parent_id` / `citation` つき） |
| 表の構造（結合セル・意味座標） | `source.json` の `grid` ＋ `derived.tables[].header_path` / `records` |
| 図の構造（6 種共通の有向グラフ） | `derived.figures[].graph` ＋ `paths` |
| 列挙の「N 番目」 | `derived.enumerations` |
| 読み順・bbox | `layout.json` の `pages[].reading_order`（**内容の単位**。ラベルと本文の内訳は含まない） |
| 質問応答 | `qa.json`（正本）または `qa.jsonl` |
| 検索・RAG | **別データセット** `{search_hf_repo_id}`（各文書の `passages.jsonl` は 1 文書ぶん） |

## 読むときの注意点（指標が歪む箇所）

- **`answer.json` は `source` と `layout` を内包しない。** 同じディレクトリに実体があるので
  参照で足りる（内包すると同じ正解が 3 か所に並び、どれが正か分からなくなる）。
- **座標は pt・原点は左上・y は下向き。** `elements.jsonl` には正規化 [0,1] の `bboxes_norm` も
  入れてある。PNG は 150dpi なので **pt × 150/72**（約 2.083 倍）でピクセル座標になる。
- **繰り返し表頭とヘッダ/フッタは PDF のテキスト層に何度も出る。**
  `answer.json` の `pages[].text` からは除いてある（`text_with_furniture` が除く前）。
  `elements.jsonl` の `repeated` が true の fragment は表頭の再掲。
  **ページ別 CER は `pages[].text` と突き合わせる**のが正しい。
- **段組では 1 つの要素が複数の fragment に割れる。** `bboxes` は配列。
- **図の中の文字は PDF のテキスト層に載るが `layout.pages[].text_lines` には出ない**
  （インライン SVG は置換ボックスとして扱われるため）。図の文字の正解は
  `source` の diagram と `layout.figures[].nodes` を見る。
- **`qa.jsonl` の `answer` は型が 3 通りある**（文字列・数値・配列）。1 つの列に混ぜると
  表形式で読めないので、`answer_text`（表示用の文字列）・`answer_number`・`answer_list` に
  分けてある。**正本は各文書の `qa.json`** で、そちらは `answer` 1 本に型そのままで入っている。

## 採点

採点ハーネスを含む生成コード：{code_repo}

```
uv run yakkan eval dataset/<doc_id> --pred pred.json     # 読み取り
uv run yakkan eval --search-run run.json                 # 検索（評価セットは別データセット）
uv run yakkan eval dataset/<doc_id> --oracle             # ハーネスの自己評価（満点が出る）
uv run yakkan eval dataset/<doc_id> --oracle --misread 0.3   # 現実の読み取り誤りで崩して採点
```

指標：ページ別 CER・outline の F1・構造位置 citation の正解率・表 TEDS とセル F1・
図のノード/辺/経路 F1・列挙の順序・読み順の Kendall τ・QA の完全/部分一致。
検索は nDCG@k・Recall@k・`exact_recall@k`・`r_precision`・MRR・`doc@1`・
`confusion@k`・`false_positive_rate`。

予測 JSON の形は `schema/prediction.schema.json`、検索結果の形は
`schema/search_run.schema.json`、語彙と採点のしかたは `docs/evaluation.md`。

## 既知の限界

- **縦書き・ルビは含まない**（描画器が対応せず、正解が作れないため）
- **スキャン劣化画像は含まない**（PDF とその 150dpi レンダリングのみ。
  傾き・汚れ・影・手書き・印影のある紙は評価できない）
- **タグ付き PDF ではない**（アクセシビリティ構造は持たない）
- 法令は名称のみを引用し、条番号は書いていない
- **題材は意図的に偏っている**（10 ジャンル・保険のみ）。
  言語モデルの事前学習コーパスには向かない
- 全件の内訳・母数の小さい観点・不合格文書の理由は **`data-card.md`** に実測で載せてある

## 由来と再現性

Claude Code のセッション内で生成した合成データである（外部 LLM API は使っていない）。
**正解 JSON が唯一の真実で、PDF はその決定論的な描画結果**（JSON → HTML → PDF）なので、
紙面と正解が食い違うことが原理的に起きない。同じ `content_id` / `style_id` / `seed` と
同じ依存バージョンなら、同一の JSON と同一のテキスト層を持つ PDF が再生成できる
（PDF のメタデータ日時は固定値）。

生成の仕組み・執筆の規約・検証の中身は生成元のリポジトリを参照。

## ライセンス

**{license_name}**（`{license_id}`）。全文は {license_legalcode_url}、
要約は {license_url}。同梱の `LICENSE` も参照。

**ただし AI モデルの学習・蒸留には使えない**（上の「⚠ AI モデルの学習・蒸留には使えない」。
CC BY 4.0 の条件ではなく、本文の執筆者が Claude であることに由来する Anthropic Usage Policy
の制限である）。`LICENSE` の `NOT FOR TRAINING AI MODELS` にも同じことを書いてある。

Copyright (c) {copyright_year} {copyright_holder}

**帰属の書き方**（CC BY 4.0 の要求を満たす最小形）：

> 「{pretty_name}」（{copyright_holder}）, {license_name}, {hf_repo_url}

**フォントについて**：`doc.pdf` には描画に使った字形の**サブセットが埋め込まれている**
（Noto Serif JP / Noto Sans JP ＝ SIL Open Font License 1.1、IPAex 明朝 / ゴシック ＝
IPA フォントライセンス v1.0）。いずれも文書への埋め込みと、その文書の再配布を許している。
**フォントそのもの（フォントファイル）はこのデータセットに含まれていない。**
CC BY 4.0 が及ぶのは本データセットの文書・正解データ・評価セットであり、
埋め込まれた字形データには各フォントのライセンスが並行して適用される。
"""

#: 検索評価セット（`dataset/search/`）のカード。**別のデータセットリポジトリの直下**に置く
#: （`dataset/search/README.md`）。HF は直下の `README.md` だけをカードとして読むので、
#: `dataset/search/` をそのまま `SEARCH_HF_REPO_ID` の直下として上げれば、これがカードになる。
#:
#: **構成は姉妹プロジェクト contracts の `render_search_card()` と同じ**（英語面＋日本語面、
#: `What it is for` / `not for`・`Configs`・`Fields`・`Caveats`、日本語面に並び・実測・注意点。
#: docs/decisions.md 2026-10-09）。告知（`NO_TRAINING_EN` / `NO_TRAINING_JA` / `FICTITIOUS_JA`）は
#: 本体のカードと同じ定数を使う。数値と列名はすべて実測から埋める（固定文字列にしない）。
SEARCH_CARD = """---
license: {license_id}
pretty_name: {pretty_name_en}
language:
- ja
multilinguality: monolingual
annotations_creators:
- machine-generated
source_datasets:
- extended|{hf_repo_id}
task_categories:
- text-retrieval
task_ids:
- document-retrieval
tags:
- japanese
- insurance
- legal
- synthetic
- retrieval
- rag-evaluation
- information-retrieval
- bm25
- reranking
- beir
size_categories:
- {size_category}
configs:
- config_name: passages
  default: true
  data_files:
  - split: train
    path: passages.jsonl
- config_name: queries
  data_files:
  - split: train
    path: queries.jsonl
- config_name: qrels
  data_files:
  - split: train
    path: qrels.jsonl
---

# {pretty_name_en}

**A retrieval evaluation set over fully synthetic Japanese insurance policy
documents** — {n_passages} passages, {n_queries} queries in {n_kinds} families and
{n_qrels} relevance judgements. The passages are cut along the real structure of
each policy (article, paragraph, table row, defined term, figure), not by a fixed
window, and the judgements are **derived from the generator's ground truth**, not
from human pooling.

- The documents themselves (PDF, 150 dpi page images, clause trees, tables,
  figures, QA) are in the companion dataset:
  [`{hf_repo_id}`]({hf_repo_url}).
- `passage_id` is `<doc_id>::<element_id>`, so every passage joins back to a
  document and to its `elements.jsonl` row there.
- The corpus takes **one layout per written policy** ({n_corpus_docs} documents) —
  two renderings of the same body would be duplicates for retrieval.
- Released under **{license_id}** © {copyright_year} {copyright_holder}. See `LICENSE`.

{no_training_en}
## What it is for

1. Retrieval evaluation on Japanese insurance / policy text (BM25, dense, hybrid,
   rerankers).
2. **RAG evaluation**: whether the passage that actually carries the answer is
   retrieved (`grade 2`), as opposed to a merely related clause (`grade 1`).
3. Structure-aware retrieval: passages carry their citation (`第2章 第1条`), kind,
   pages, issuer, product name, outgoing references and defined terms used, so
   recall can be sliced by structure.
4. **Metadata filtering**: {n_with_filters} queries carry their scope in a
   `filters` field (issuer / product_name / genre) instead of in the query text.
   A retriever that does not index metadata cannot solve them, so a run must
   declare what it indexed in `index_setting`.
5. **Abstention**: `no_answer` queries ({n_no_answer}) have an **empty gold set** —
   returning nothing is the correct behaviour, scored by `false_positive_rate`.
6. **Confusable negatives**: {n_with_hard_negatives} queries declare
   `hard_negatives` (same-named article of another product, etc.). Their grade
   stays 0, but `confusion@k` measures how often a retriever takes the bait.

## What it is **not** for

- **Any real-world insurance use.** The clauses are dummies written for reading
  evaluation and have not been reviewed by an insurance or legal professional.
- **Training, fine-tuning or distilling any AI / ML model** (see the section
  above; this is a restriction from Anthropic's Usage Policy, not from the
  dataset license).
- Measuring absolute retrieval difficulty: the corpus is small and deliberately
  homogeneous ({n_genres} document genres, all synthetic, all born-digital
  Japanese text).
- Comparing chunking strategies: there is **one segmentation only** (the
  structural one above).

## Configs

| config | rows | what one row is | file |
|---|---|---:|---|
| `passages` | {n_passages} | one retrieval unit, with its citation | `passages.jsonl` |
| `queries` | {n_queries} | one query — kind, optional `filters`, gold size | `queries.jsonl` |
| `qrels` | {n_qrels} | one judgement — grade 2 = answer-bearing, 1 = related | `qrels.jsonl` |

```python
from datasets import load_dataset

passages = load_dataset("{search_hf_repo_id}", "passages", split="train")
queries  = load_dataset("{search_hf_repo_id}", "queries",  split="train")
qrels    = load_dataset("{search_hf_repo_id}", "qrels",    split="train")
```

`id_map.json` (old id → new id, for runs made against v6 or earlier) is a plain
file — take it with `huggingface_hub.hf_hub_download`.

{sample_passage}
## Fields

| file | columns (measured) |
|---|---|
| `passages.jsonl` | {fields_passages} |
| `queries.jsonl` | {fields_queries} |
| `qrels.jsonl` | {fields_qrels} |

## How hard is it?

Three **lexical-only** baselines, measured at generation time (no morphological
analyser, no synonym dictionary). They are the yardstick for whether a query
family can discriminate at all: **a kind whose nDCG@1 is above 0.85 with a spread
below 0.2 across the three has no resolving power** and is flagged below.

{baseline_table}

`term` / `heading` draw on words and headings that **only one document in the
corpus has**, so lexical matching is expected to solve them (the target is still
uniquely determined — they are well-posed). To measure semantic retrieval, use
`definition_masked` / `multi_hop` / `situational`.

## Caveats

- **`grade 1` is capped at {max_related} judgements per query.** Beyond the cap a
  related passage simply does not appear in `qrels`, so scoring treats it as
  non-relevant. `queries.jsonl` carries `related_truncated` and
  `n_related_total`; {n_truncated} of {n_queries} queries are capped. **Do not
  read Recall@k as if the cap were not there** — use `grade 2` (answer-bearing)
  for strict scoring.
- **One layout per written policy.** The document dataset renders some policies in
  two page layouts; retrieval would see them as duplicates, so only one is here.
- **`filters` is part of the query, not a hint.** The same query string with
  different `filters` is a different query.
- **`no_answer` has an empty gold set** and appears in no `qrels` row.
- Queries are generated from the ground truth (defined terms, headings, scoped
  questions, QA pairs and situations), not written by human searchers, so phrasing
  is cleaner than real user queries.
- `teikan` (articles of incorporation) has no table of defined terms — real ones
  do not either — so the corpus has no `definition` passage for that genre.

## Citation

```bibtex
@misc{{yakkan_synth_search,
  title  = {{{pretty_name_en}}},
  author = {{{copyright_holder}}},
  year   = {{{copyright_year}}},
  howpublished = {{Hugging Face Hub}},
  url    = {{{search_hf_repo_url}}},
  note   = {{Version {dataset_version}. Licensed under {license_id}.}}
}}
```

---

# 日本語版 — 検索評価セットの読み方

**日本語保険約款の検索評価セット（合成・passages / queries / qrels）**

**このファイルは `yakkan export` が生成する。手で編集しない**（CLAUDE.md §0.4-3）。
設計の経緯は `docs/search_query_design.md`、実測は `docs/search_query_plan.md`、
採点の指標は `docs/evaluation.md` §2、配布の形は `docs/distribution.md`。

- 生成物は **{license_id}** で配布する（著作権表示：© {copyright_year} {copyright_holder}）。
  本文は `LICENSE`。
- **AI モデルの学習・蒸留には使えない**（次節）。評価・ベンチマークは対象外。
- **文書そのもの（PDF・ページ画像・正解 JSON・QA）は別のデータセットにある**：
  [`{hf_repo_id}`]({hf_repo_url})。こちらはそのコーパスに対する
  passages / queries / qrels だけを持つ。
- 版は `{dataset_version}`（文書本体のデータセットと同じ版）。

{fictitious_ja}
{no_training_ja}
## 並び

```
passages.jsonl   検索に登録する単位（条・項・表の行・定義表の行・図。構造の切れ目で切ってある）
queries.jsonl    クエリ（{n_kinds} 種。`filters` と `hard_negatives` つき）
qrels.jsonl      適合判定（grade 2 = 答えがある / 1 = 関連する）
id_map.json      旧 id → 新 id（v6 以前との対応）
SHA256SUMS       このリポジトリで配布するファイルの SHA256
```

## 検索評価セットの設計

**約款は文書をまたいでほぼ同じ条文を持つ**（告知義務・重大事由による解除・準拠法など）。
そのため「告知義務」のような語をクエリにすると**どの文書を返すべきかが決まらない**。
この評価セットでは、語の出現文書数で 3 通りに振り分けてこれを避けている。

- コーパス中 1 文書だけが持つ語・見出し → **素の項目検索**（`term` / `heading`）
- 複数文書にある見出し → **絞り込み**（`scoped` は会社名・商品名をクエリ文に、
  `filtered` は `filters` フィールドで渡す）
- 広く使われる語 → **網羅クエリ**（`enumeration`。順位ではなく再現率で測る）

さらに、**クエリが正解の字面のコピーにならない系統**を 3 つ持つ
（`definition_masked` / `multi_hop` / `situational`）と、
**根拠が無いときに黙れるかを測る** `no_answer`（gold が空集合）がある。

## 実測（この版の中身）

{passage_kinds_table}
{query_kinds_table}
{grades_table}
## 注意点

- **`passage_id` は `<doc_id>::<element_id>`。** 紙面・bbox・構造上の位置は文書側の
  `elements.jsonl`（[`{hf_repo_id}`]({hf_repo_url})）と突き合わせて引く。
- **コーパスは content ごとに 1 スタイルだけ**採ってある（{n_corpus_docs} 文書）。
  同じ本文を別の版面で描いた文書は検索では重複になるため入れていない
  （版面の頑健性は文書側のデータセットで見る）。
- **grade 1 は 1 クエリ {max_related} 件で打ち切ってある。** 打ち切られた分は qrels に出ないので
  評価上は非適合と同じ扱いになる。どのクエリで切ったかは `queries.jsonl` の
  `related_truncated` と `n_related_total` でわかる（現行の生成では {n_queries} クエリ中
  {n_truncated} 件）。**この件数で Recall@k を解釈しない。**
- **クエリは `filters` を持つことがある**（{n_with_filters} 件）。`filtered` / `qa` /
  `situational` / `definition_masked` / `multi_hop` / `no_answer` は、絞り込み条件を
  **クエリ文ではなく `filters`（issuer / product_name / genre）で渡す**。同じ文言でも
  `filters` が違えば別のクエリ（「「(4)」は何ページにありますか」は 20 文書で同じ文字列になる）。
  メタデータを索引しない検索器は `filtered` を構造的に解けないので、
  **何を索引したかを `search_run.json` の `index_setting` に申告する**。
- **`no_answer` は gold が空集合**で、`qrels.jsonl` に 1 行も出ない（{n_no_answer} 件）。
  **何も返さないのが正解**で、`false_positive_rate` で採点する。
- **`hard_negatives` は「紛らわしいと宣言された非適合」**（他商品の同名条など。{n_with_hard_negatives} 件）。
  grade は 0 のままだが、`confusion@k` でどれだけ釣られたかを測れる。
- **`filters` は行ごとにキーの組み合わせが変わる**ので、`datasets` では `Json` 型に推論される。
  採点の入力でもあるため、**見え方のためにスキーマを変えていない。**
- **素朴な検索器 3 系統のベースライン**は英語面の `How hard is it?` にある。
  「この評価セットが簡単すぎないか」はそこで確認する。

## 採点

```
uv run yakkan eval --search-run run.json            # 検索結果 JSON を採点する
uv run yakkan eval --search-run run.json --oracle   # ハーネスの自己評価（満点が出る）
```

指標：nDCG@k・Recall@k・`exact_recall@k`・`r_precision`・MRR・`doc@1`・
`confusion@k`・`false_positive_rate`。検索結果 JSON の形は `schema/search_run.schema.json`。

採点ハーネスを含む生成コード：{code_repo}
"""

#: `dataset/LICENSE` の本文。
#: **CC BY 4.0 の法文（legalcode）は転記しない。** 7,000 語超を手で写すと誤記が入りうるし、
#: 誤記のあるライセンス本文は参照リンクより害が大きい。CC 自身が推奨する
#: 「表示＋正式な法文への参照」の形を採る（docs/distribution.md）。
LICENSE_NOTICE = """{license_name}

Copyright (c) {copyright_year} {copyright_holder}

This dataset — "{pretty_name}" — is licensed under the
{license_name}.

  Human-readable summary : {license_url}
  Full legal code        : {license_legalcode_url}

The full legal code is NOT reproduced in this file. It is a long, precise legal
document, and a hand-copied version risks introducing errors; the canonical text
at the URL above governs.

You are free to share and adapt this dataset, including commercially, provided
you give appropriate credit, link to the license, and indicate if changes were
made.

NOT FOR TRAINING AI MODELS
--------------------------
THIS DATASET MUST NOT BE USED TO TRAIN, FINE-TUNE, DISTILL, OR OTHERWISE
DEVELOP ANY ARTIFICIAL INTELLIGENCE OR MACHINE LEARNING MODEL, INCLUDING LARGE
LANGUAGE MODELS (LLMs) AND VISION-LANGUAGE MODELS (VLMs).

The documents, the QA pairs and the figure descriptions in this dataset were
written by Claude (Anthropic) inside a Claude Code session; they are Outputs of
that service. Anthropic's Usage Policy prohibits

  "Utilization of inputs and outputs to train an AI model (e.g., 'model
   scraping' or 'model distillation') without prior authorization from
   Anthropic"

  {aup_url}

EVALUATION IS NOT TRAINING. Benchmarking or evaluating document-reading systems
(OCR, layout analysis, VLMs, structured extraction), retrieval and RAG
pipelines, or AI agents against this dataset is the purpose it was built for,
and nothing above restricts it. Neither does using it as test fixtures, as
few-shot examples, or as a retrieval corpus at inference time. What is excluded
is updating model weights from it.

This section is a NOTICE, not an additional condition of the license above.
CC BY 4.0 Section 2(a)(5)(B) forbids imposing further restrictions on
downstream recipients, so this statement is not offered as a term of the CC BY
4.0 grant and does not narrow it. It tells you about a restriction that arises
from Anthropic's Usage Policy and that binds everyone subject to that policy.
If you need to train on data of this kind, obtain prior authorization from
Anthropic first.

ATTRIBUTION
-----------
A minimal attribution that satisfies CC BY 4.0:

  "{pretty_name}" ({copyright_holder}), {license_name},
  {hf_repo_url}

WHAT THIS LICENSE COVERS
------------------------
It covers the documents, the ground-truth JSON, and the evaluation sets in this
dataset.

It does NOT cover the glyph data embedded in `*/doc.pdf`. Each PDF embeds a
SUBSET of the typefaces used to render it:

  Noto Serif JP, Noto Sans JP, Noto Sans Symbols, Noto Sans Symbols 2
      SIL Open Font License 1.1 - https://openfontlicense.org/
  IPAex Mincho, IPAex Gothic
      IPA Font License Agreement v1.0 - https://moji.or.jp/ipafont/license/

Both licenses permit embedding glyphs in a document and redistributing that
document. The font files themselves are NOT included in this dataset.

NOT A REAL INSURANCE POLICY
---------------------------
Every company name, product name, contact detail, URL, form code, person name
and monetary amount in this dataset is FICTITIOUS. The documents imitate the
STRUCTURE of Japanese insurance policy documents; no sentence is copied from a
real policy. The content has NOT been reviewed by insurance or legal
professionals and must not be used as a real policy, for product comparison, or
as a legal reference.
"""

#: `dataset/.gitattributes`。Hugging Face Hub は LFS で追跡しないと大きなファイルを弾く。
#: PNG は 1,458 枚で 600MiB 超、PDF は 113 件で 33MiB あるので、両方を LFS に入れる。
#: **検索評価セットのリポジトリには置かない**（LFS 対象が無い。姉妹プロジェクト contracts と同じ）。
GITATTRIBUTES = """# Hugging Face Hub 用。大きなバイナリは Git LFS で追跡する。
# **このファイルは `yakkan export` が生成する。手で編集しない**（CLAUDE.md §0.4-3）。
*.png filter=lfs diff=lfs merge=lfs -text
*.pdf filter=lfs diff=lfs merge=lfs -text
# 正解とテキストは差分が読めるようにしておく（JSON/JSONL/Markdown は LFS に入れない）。
*.json text
*.jsonl text
*.md text
"""

#: 検索評価セットの `LICENSE`。**本体とは別の短い本文**にする（姉妹プロジェクト contracts と
#: 同じ設計）。配布物が JSONL と JSON だけなので、フォントの節も「及ぶ範囲」の長い説明も要らない。
#: 学習・蒸留の禁止は**両方の LICENSE に出す**（片方だけを見た人に伝わらないため）。
SEARCH_LICENSE_NOTICE = """{pretty_name}

Copyright (c) {copyright_year} {copyright_holder}

The generated files in this repository (JSONL and JSON) are licensed under
{license_id} ({license_name}).

  Human-readable summary : {license_url}
  Full legal code        : {license_legalcode_url}

The passage text is taken from the synthetic documents that are distributed
separately as {documents_url}

NOT FOR TRAINING AI MODELS
--------------------------
THIS DATASET MUST NOT BE USED TO TRAIN, FINE-TUNE, DISTILL, OR OTHERWISE
DEVELOP ANY ARTIFICIAL INTELLIGENCE OR MACHINE LEARNING MODEL, INCLUDING LARGE
LANGUAGE MODELS (LLMs) AND VISION-LANGUAGE MODELS (VLMs).

The policy clauses, the QA pairs and the figure descriptions these passages are
drawn from were written by Claude (Anthropic) inside a Claude Code session; they
are Outputs of that service. Anthropic's Usage Policy prohibits

  "Utilization of inputs and outputs to train an AI model (e.g., 'model
   scraping' or 'model distillation') without prior authorization from
   Anthropic"

  {aup_url}

EVALUATION IS NOT TRAINING. Benchmarking or evaluating retrieval and RAG
pipelines, document-reading systems or AI agents against this dataset is the
purpose it was built for, and nothing above restricts it. Neither does using it
as test fixtures, as few-shot examples, or as a retrieval corpus at inference
time. What is excluded is updating model weights from it.

This section is a NOTICE, not an additional condition of the license above.
CC BY 4.0 Section 2(a)(5)(B) forbids imposing further restrictions on
downstream recipients, so this statement is not offered as a term of the CC BY
4.0 grant and does not narrow it. It tells you about a restriction that arises
from Anthropic's Usage Policy and that binds everyone subject to that policy.

NOT A REAL INSURANCE POLICY
---------------------------
Every company name, product name, contact detail, URL, form code, person name
and monetary amount behind these passages is FICTITIOUS, and the clauses have
NOT been reviewed by insurance or legal professionals. They must not be used as
policy terms, for product comparison, or as a legal reference.
"""


def _count_table(rows: Sequence[dict[str, Any]], key: str, header: str) -> str:
    """`kind` などの件数表を Markdown にする（件数の多い順→名前順で決定論）。

    姉妹プロジェクト contracts の「実測（この版の中身）」と同じ形。
    """
    from collections import Counter

    counts = Counter(str(row.get(key, "?")) for row in rows)
    lines = [f"| {header} | 件数 |", "|---|---:|"]
    for name, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"| `{name}` | {_fmt(count)} |")
    return "\n".join(lines) + "\n"


def _fields(rows: Sequence[dict[str, Any]]) -> str:
    """jsonl の**列名を実測**して並べる（スキーマを固定文字列で書くと生成器と食い違う）。"""
    return ", ".join(f"`{name}`" for name in sorted({k for row in rows for k in row}))


#: Hub の `size_categories`。**既定 config の行数**で決める（姉妹プロジェクト contracts と
#: 同じ慣習）。桁で決まるので**実測から選ぶ**（固定文字列にしない）。
_SIZE_CATEGORIES = ((1_000, "n<1K"), (10_000, "1K<n<10K"), (100_000, "10K<n<100K"), (1_000_000, "100K<n<1M"))


def _size_category(n: int) -> str:
    for limit, label in _SIZE_CATEGORIES:
        if n < limit:
            return label
    return "1M<n<10M"


def _fmt(value: object) -> str:
    """カードに出す数値の 3 桁区切り。**統計値を固定文字列で焼き込まないため**
    すべて呼び出し側の実測から通す（docs/data_card.md §1）。"""
    return f"{value:,}" if isinstance(value, int) else str(value)


def _sample_toggle(title_en: str, title_ja: str, row: dict[str, Any] | None) -> str:
    """1 行ぶんの実データを `<details>` で折りたたんで見せる（姉妹プロジェクト contracts と同じ設計）。

    **先頭行を決定的に採る**（乱数も時刻も使わない。CLAUDE.md §0.4-4）。
    `row` が無ければ節自体を省く。
    """
    if not row:
        return ""
    body = json.dumps(row, ensure_ascii=False, indent=2, sort_keys=False)
    return (
        f"<details>\n<summary><b>Sample {title_en} row</b> / {title_ja}のサンプル1件</summary>\n\n"
        f"```json\n{body}\n```\n\n</details>\n"
    )


def write_card(
    dataset_dir: Path,
    *,
    documents: Sequence[Any] = (),
    passages: Sequence[Any] = (),
    queries: Sequence[Any] = (),
    qrels: Sequence[Any] = (),
    n_corpus_docs: int = 0,
    dataset_version: str = "",
    hf_repo_id: str = HF_REPO_ID,
    search_hf_repo_id: str = SEARCH_HF_REPO_ID,
) -> Path:
    """Hugging Face のデータセットカードを `dataset/README.md` に書き出す。

    **HF はリポジトリ直下の `README.md` だけをカードとして読む。** 以前は
    `README.md`（読み方）と `DATASET_CARD.md`（HF 形式の要約）に分かれていたが、
    2 枚あると数値が食い違いうるうえ HF 側は後者を見ないので 1 枚に統合した
    （docs/decisions.md 2026-10-05）。

    数値はすべて引数で受けた実測から埋める。**固定文字列に焼き込まない**
    （docs/data_card.md §1。`dataset/README.md` が「1,944 クエリ中 28 件」を
    直書きしていて `export` を回しても更新されなかった事故の再発防止）。

    **検索評価セットは別のデータセット**（`SEARCH_HF_REPO_ID`）なので、ここには
    件数とリンクだけを出す。設計・ベースライン・読むときの注意点は
    `write_search_card()` が書く（2026-10-08。docs/distribution.md）。
    """

    def rows(items: Sequence[Any]) -> list[dict[str, Any]]:
        return [i if isinstance(i, dict) else i.model_dump() for i in items]

    docs = [d for d in rows(documents) if d.get("status") == "ready"]
    query_rows = rows(queries)
    sample_qa: dict[str, Any] | None = None
    qa_jsonl_path = dataset_dir / "qa.jsonl"
    if qa_jsonl_path.is_file():
        for line in qa_jsonl_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                sample_qa = json.loads(line)
                break
    path = dataset_dir / "README.md"
    path.write_text(
        CARD.format(
            sample_qa=_sample_toggle("qa", "qa", sample_qa),
            license_id=LICENSE_ID,
            license_name=LICENSE_NAME,
            license_url=LICENSE_URL,
            license_legalcode_url=LICENSE_LEGALCODE_URL,
            fictitious_ja=FICTITIOUS_JA,
            no_training_ja=NO_TRAINING_JA.format(aup_url=AUP_URL),
            copyright_year=COPYRIGHT_YEAR,
            copyright_holder=COPYRIGHT_HOLDER,
            pretty_name=PRETTY_NAME,
            pretty_name_en=PRETTY_NAME_EN,
            no_training_en=NO_TRAINING_EN.format(aup_url=AUP_URL),
            code_repo=CODE_REPO,
            hf_repo_id=hf_repo_id,
            hf_repo_url=f"https://huggingface.co/datasets/{hf_repo_id}",
            search_hf_repo_id=search_hf_repo_id,
            search_hf_repo_url=f"https://huggingface.co/datasets/{search_hf_repo_id}",
            dataset_version=dataset_version or "（未設定）",
            # `size_categories` は**既定 config の行数**で決める（contracts と同じ慣習）
            size_category=_size_category(len(rows(documents))),
            n_docs=_fmt(len(docs)),
            n_doc_rows=_fmt(len(rows(documents))),
            n_contents=_fmt(len({d.get("content_id") for d in docs})),
            n_pages=_fmt(sum(int(d.get("pages") or 0) for d in docs)),
            n_genres=_fmt(len({d.get("genre") for d in docs})),
            n_styles=_fmt(len({d.get("style_id") for d in docs})),
            n_qa=_fmt(sum(int(d.get("qa_items") or 0) for d in docs)),
            n_passages=_fmt(len(passages)),
            n_queries=_fmt(len(query_rows)),
            n_kinds=_fmt(len({q["kind"] for q in query_rows})),
            n_qrels=_fmt(len(qrels)),
            n_corpus_docs=_fmt(n_corpus_docs),
        ),
        encoding="utf-8",
    )
    return path


def write_search_card(
    search_dir: Path,
    *,
    passages: Sequence[Any] = (),
    queries: Sequence[Any] = (),
    qrels: Sequence[Any] = (),
    n_corpus_docs: int = 0,
    baseline_table: str = "（ベースライン未計測）",
    dataset_version: str = "",
    hf_repo_id: str = HF_REPO_ID,
    search_hf_repo_id: str = SEARCH_HF_REPO_ID,
) -> Path:
    """検索評価セットのカードを `dataset/search/README.md` に書き出す。

    **`dataset/search/` をそのまま別のデータセットリポジトリの直下として上げる**ので、
    これがそのリポジトリのカードになる（HF は直下の `README.md` だけをカードとして読む）。

    構成は姉妹プロジェクト contracts の `render_search_card()` に合わせてある
    （英語面＋日本語面。docs/decisions.md 2026-10-09）。**数値・列名・種別の内訳・
    `size_categories` はすべて実測から埋める**（docs/data_card.md §1）。
    """
    from yakkan.search_set import MAX_RELATED

    def rows(items: Sequence[Any]) -> list[dict[str, Any]]:
        return [i if isinstance(i, dict) else i.model_dump() for i in items]

    passage_rows, query_rows, qrel_rows = rows(passages), rows(queries), rows(qrels)
    path = search_dir / "README.md"
    search_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        SEARCH_CARD.format(
            sample_passage=_sample_toggle("passage", "passage", passage_rows[0] if passage_rows else None),
            license_id=LICENSE_ID,
            license_name=LICENSE_NAME,
            license_url=LICENSE_URL,
            license_legalcode_url=LICENSE_LEGALCODE_URL,
            fictitious_ja=FICTITIOUS_JA,
            no_training_ja=NO_TRAINING_JA.format(aup_url=AUP_URL),
            no_training_en=NO_TRAINING_EN.format(aup_url=AUP_URL),
            code_repo=CODE_REPO,
            copyright_year=COPYRIGHT_YEAR,
            copyright_holder=COPYRIGHT_HOLDER,
            pretty_name=SEARCH_PRETTY_NAME,
            pretty_name_en=SEARCH_PRETTY_NAME_EN,
            hf_repo_id=hf_repo_id,
            hf_repo_url=f"https://huggingface.co/datasets/{hf_repo_id}",
            search_hf_repo_id=search_hf_repo_id,
            search_hf_repo_url=f"https://huggingface.co/datasets/{search_hf_repo_id}",
            dataset_version=dataset_version or "（未設定）",
            # 既定 config（`passages`）の行数で決める（contracts と同じ慣習）
            size_category=_size_category(len(passage_rows)),
            n_passages=_fmt(len(passage_rows)),
            n_queries=_fmt(len(query_rows)),
            n_kinds=_fmt(len({q["kind"] for q in query_rows})),
            n_qrels=_fmt(len(qrel_rows)),
            n_corpus_docs=_fmt(n_corpus_docs),
            n_genres=_fmt(len({p.get("genre") for p in passage_rows if p.get("genre")})),
            n_truncated=_fmt(sum(1 for q in query_rows if q.get("related_truncated"))),
            n_with_filters=_fmt(sum(1 for q in query_rows if q.get("filters"))),
            n_with_hard_negatives=_fmt(sum(1 for q in query_rows if q.get("hard_negatives"))),
            n_no_answer=_fmt(sum(1 for q in query_rows if q.get("kind") == "no_answer")),
            max_related=_fmt(MAX_RELATED),
            baseline_table=baseline_table,
            fields_passages=_fields(passage_rows),
            fields_queries=_fields(query_rows),
            fields_qrels=_fields(qrel_rows),
            passage_kinds_table=_count_table(passage_rows, "kind", "パッセージの種別"),
            query_kinds_table=_count_table(query_rows, "kind", "クエリの種別"),
            grades_table=_count_table(
                [{"grade": f"grade {r.get('grade')}"} for r in qrel_rows], "grade", "適合判定"
            ),
        ),
        encoding="utf-8",
    )
    return path


#: かつて `export` が書いていて、いまは書かない成果物。
#: **生成器が出力の名前を変えたら、古い名前の後片付けも生成器の仕事。**
#: 残しておくと「2 枚のカードのどちらが正か」が分からなくなるし、
#: `dataset/` は手編集禁止（CLAUDE.md §0.4-3）なので人手で消す運用にもできない。
RETIRED_ARTIFACTS = (
    # HF は直下の README.md だけをカードとして読むので README.md に統合した（2026-10-05）
    "DATASET_CARD.md",
)

#: 同じく、検索評価セットのリポジトリで書かなくなったもの。
#: `.gitattributes` は LFS 対象が無いリポジトリに置いても意味が無いので、
#: 姉妹プロジェクト contracts の形に合わせて廃止した（2026-10-09）。配布物は `SHA256SUMS` が数える。
RETIRED_SEARCH_ARTIFACTS = (".gitattributes",)


def remove_retired(dataset_dir: Path, names: Sequence[str] = RETIRED_ARTIFACTS) -> list[str]:
    """`export` が書かなくなった成果物を消す。消したファイル名を返す。"""
    removed = []
    for name in names:
        path = dataset_dir / name
        if path.is_file():
            path.unlink()
            removed.append(name)
    return removed


def write_license(dataset_dir: Path) -> Path:
    """`dataset/LICENSE` を書き出す（`TASK.md` T11 で CC BY 4.0 に決定）。"""
    path = dataset_dir / "LICENSE"
    path.write_text(
        LICENSE_NOTICE.format(
            license_name=LICENSE_NAME,
            license_url=LICENSE_URL,
            license_legalcode_url=LICENSE_LEGALCODE_URL,
            copyright_year=COPYRIGHT_YEAR,
            copyright_holder=COPYRIGHT_HOLDER,
            pretty_name=PRETTY_NAME_EN,
            hf_repo_url=f"https://huggingface.co/datasets/{HF_REPO_ID}",
            aup_url=AUP_URL,
        ),
        encoding="utf-8",
    )
    return path


def write_search_license(
    search_dir: Path,
    *,
    hf_repo_id: str = HF_REPO_ID,
    search_hf_repo_id: str = SEARCH_HF_REPO_ID,
) -> Path:
    """検索評価セットの `LICENSE` を `dataset/search/LICENSE` に書き出す。

    **本体より短い専用の本文**（`SEARCH_LICENSE_NOTICE`）。PDF もフォントも無いリポジトリで
    フォントの節を出さない（姉妹プロジェクト contracts と同じ設計）。`search_hf_repo_id` は
    いまは本文に出さないが、呼び出し側の対称性のために受ける。
    """
    search_dir.mkdir(parents=True, exist_ok=True)
    path = search_dir / "LICENSE"
    path.write_text(
        SEARCH_LICENSE_NOTICE.format(
            pretty_name=SEARCH_PRETTY_NAME_EN,
            license_id=LICENSE_ID,
            license_name=LICENSE_NAME,
            license_url=LICENSE_URL,
            license_legalcode_url=LICENSE_LEGALCODE_URL,
            copyright_year=COPYRIGHT_YEAR,
            copyright_holder=COPYRIGHT_HOLDER,
            documents_url=f"https://huggingface.co/datasets/{hf_repo_id}",
            aup_url=AUP_URL,
        ),
        encoding="utf-8",
    )
    return path


def write_gitattributes(dataset_dir: Path) -> Path:
    """`dataset/.gitattributes` を書き出す（HF Hub の LFS 追跡）。"""
    path = dataset_dir / ".gitattributes"
    path.write_text(GITATTRIBUTES, encoding="utf-8")
    return path


#: 配布物の一覧と SHA256 を置くファイル（姉妹プロジェクト contracts と同じ名前・同じ役目）。
SHA256SUMS_NAME = "SHA256SUMS"


def write_search_sha256sums(search_dir: Path) -> Path:
    """`dataset/search/SHA256SUMS` を書き出す。

    **パスは自分のルートからの相対**（`search/passages.jsonl` ではなく `passages.jsonl`）——
    このディレクトリがそのまま別リポジトリの直下になるため。`sha256sum -c` で検証できる形。
    **`SHA256SUMS` 自身と隠しファイルは数えない。**
    """
    import hashlib

    search_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for item in sorted(search_dir.iterdir(), key=lambda q: q.name):
        if not item.is_file() or item.name.startswith(".") or item.name == SHA256SUMS_NAME:
            continue
        digest = hashlib.sha256()
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        lines.append(f"{digest.hexdigest()}  {item.name}")
    path = search_dir / SHA256SUMS_NAME
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_documents_jsonl(dataset_dir: Path, documents: Sequence[Any]) -> int:
    """`manifest.json` の文書一覧を 1 行 1 文書の JSONL にする（HF の `documents` コンフィグ）。

    `manifest.json` は 1 個の JSON オブジェクトなので HF のデータセットビューアが読めない。
    **正本は `manifest.json`** で、こちらはそれを平らにしただけ。`checksums` と `errors` は
    列の型が揺れるので落とす（必要なら `manifest.json` を見る）。
    """

    def rows(items: Sequence[Any]) -> list[dict[str, Any]]:
        return [i if isinstance(i, dict) else i.model_dump() for i in items]

    keep = (
        "doc_id",
        "content_id",
        "style_id",
        "genre",
        "seed",
        "status",
        "pages",
        "page_images",
        "chars",
        "tables",
        "figures",
        "footnotes",
        "refs",
        "qa_items",
    )
    out = [{k: d.get(k) for k in keep} for d in rows(documents)]
    path = dataset_dir / "documents.jsonl"
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in out),
        encoding="utf-8",
    )
    return len(out)


def write_qa_jsonl(dataset_dir: Path, documents: Sequence[Any]) -> int:
    """全文書の QA を 1 行 1 問の JSONL にまとめる（HF の `qa` コンフィグ）。

    **`answer` は型が 3 通りある**（`string` / `number` / `list`）。Arrow は 1 列に
    文字列と数値と配列を混ぜられないので、表形式で読めるよう 3 列に分ける。
    **正本は各文書の `qa.json`**（`answer` 1 本に型そのまま）で、これは派生である。
    """

    def rows(items: Sequence[Any]) -> list[dict[str, Any]]:
        return [i if isinstance(i, dict) else i.model_dump() for i in items]

    out: list[dict[str, Any]] = []
    for doc in rows(documents):
        if doc.get("status") != "ready":
            continue
        qa_path = dataset_dir / str(doc["doc_id"]) / "qa.json"
        if not qa_path.is_file():
            continue
        for item in json.loads(qa_path.read_text(encoding="utf-8"))["items"]:
            answer = item["answer"]
            if isinstance(answer, list):
                text, number, values = "、".join(answer), None, list(answer)
            elif isinstance(answer, bool):  # pragma: no cover - 現行の生成では出ない
                text, number, values = str(answer), None, []
            elif isinstance(answer, (int, float)):
                # 現行の `number` はすべて整数値。`5.0` ではなく `5` と見せる
                text = str(int(answer)) if float(answer).is_integer() else str(answer)
                number, values = float(answer), []
            else:
                text, number, values = str(answer), None, []
            out.append(
                {
                    "doc_id": doc["doc_id"],
                    "content_id": doc.get("content_id"),
                    "style_id": doc.get("style_id"),
                    "genre": doc.get("genre"),
                    "qa_id": item["id"],
                    "type": item["type"],
                    "question": item["question"],
                    "answer_type": item["answer_type"],
                    "answer_text": text,
                    "answer_number": number,
                    "answer_list": values,
                    "evidence": list(item["evidence"]),
                    "page_hint": list(item["page_hint"]),
                    "source": item["source"],
                }
            )
    path = dataset_dir / "qa.jsonl"
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in out),
        encoding="utf-8",
    )
    return len(out)


#: 旧 `passage_id` の接頭辞（`defined_terms` をそのままパッセージにしていた v6 以前）
LEGACY_TERM_PREFIX = "::term::"


def write_id_map(search_dir: Path, passages: Sequence[Any], queries: Sequence[Any]) -> Path:
    """旧 id → 新 id の対応表を書き出す（docs/search_query_plan.md W11）。

    v6 以前との非互換は 2 つある。

    1. `query_id` が通し番号（`q_term_0001`）から生成キーのハッシュになった。
       通し番号は **content が 1 本増えるだけで全部ずれる**ので、版をまたいだ比較ができない。
    2. `passage_id` が `<doc_id>::term::<term_id>` から定義表の行
       （`<doc_id>::<table_id>__r<N>`）になった。前者は**紙面に存在しない**単位だった。

    クエリ側は旧 id を復元できない（通し番号は生成順にしか依存しない）ので、
    **`kind` と生成キーから新 id を引けるようにする**。パッセージ側は
    用語名で突き合わせられるので、旧 id を組み立てて並べる。
    """
    import json

    terms: dict[str, str] = {}
    for passage in passages:
        row = passage if isinstance(passage, dict) else passage.model_dump()
        if row["kind"] != "definition":
            continue
        doc_id, _, _ = row["passage_id"].partition("::")
        terms[f"{doc_id}{LEGACY_TERM_PREFIX}{row['title']}"] = row["passage_id"]
    payload = {
        "note": (
            "v6 以前との対応。queries は kind と生成キーから新 id を引く（旧 id は通し番号で"
            "復元できない）。passages は定義語のパッセージだけが変わった。"
        ),
        "queries": {
            (q if isinstance(q, dict) else q.model_dump())["query_id"]: {
                "kind": (q if isinstance(q, dict) else q.model_dump())["kind"],
                "query": (q if isinstance(q, dict) else q.model_dump())["query"],
            }
            for q in queries
        },
        "passages_by_legacy_term_key": terms,
    }
    search_dir.mkdir(parents=True, exist_ok=True)
    path = search_dir / "id_map.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
