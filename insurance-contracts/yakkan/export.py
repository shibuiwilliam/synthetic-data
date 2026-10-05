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
HF_REPO_ID = "cvusk/synthetic-japanese-insurance-documents"

#: 配布ライセンス。`TASK.md` T11 で 2026-10-05 に **CC BY 4.0** と決まった。
#: 変えるときは `LICENSE` の本文（`LICENSE_NOTICE`）と対で変える。
LICENSE_ID = "cc-by-4.0"
LICENSE_NAME = "Creative Commons Attribution 4.0 International (CC BY 4.0)"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
LICENSE_LEGALCODE_URL = "https://creativecommons.org/licenses/by/4.0/legalcode"
COPYRIGHT_HOLDER = "shibuiwilliam"
COPYRIGHT_YEAR = "2026"

CARD = """---
language:
  - ja
license: {license_id}
task_categories:
  - question-answering
  - text-retrieval
  - document-question-answering
  - image-to-text
task_ids:
  - extractive-qa
  - document-retrieval
tags:
  - insurance
  - japanese
  - synthetic
  - document-understanding
  - document-ai
  - ocr
  - layout-analysis
  - information-retrieval
  - rag
pretty_name: 日本語保険約款 合成ドキュメントデータセット (yakkan-synth)
size_categories:
  - 10K<n<100K
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
  - config_name: search-passages
    data_files:
      - split: train
        path: search/passages.jsonl
  - config_name: search-queries
    data_files:
      - split: train
        path: search/queries.jsonl
  - config_name: search-qrels
    data_files:
      - split: train
        path: search/qrels.jsonl
---

# 日本語保険約款 合成ドキュメントデータセット（yakkan-synth）

日本語の保険約款（やっかん）の**構造的特徴を忠実に再現した、完全に架空の文書**と、
その**完全な正解データ**を対にしたデータセット。ドキュメント読み取り
（OCR・レイアウト解析・VLM・構造化抽出）と**検索／RAG** の開発検証用。

**このファイルは `yakkan export` が生成する。手で編集しない**（CLAUDE.md §0.4-3）。

| | |
|---|---|
| 文書（PDF） | **{n_docs} 点** / **{n_pages} ページ**（1 文書 20 ページ以下） |
| ジャンル | **{n_genres} 種**（下記） |
| 版面（スタイル） | **{n_styles} 種**（A4/B5/横長・1 段/2 段・明朝/ゴシック） |
| QA | **{n_qa} 問**（自動生成 30 問＋執筆 15 問／文書） |
| 検索評価セット | パッセージ **{n_passages}** / クエリ **{n_queries}**（{n_kinds} 種）/ qrels **{n_qrels}** |
| 版 | `{dataset_version}`（`manifest.json` の `dataset_version`） |
| 言語 | 日本語のみ（横書き） |

ジャンル：総合自動車保険・1 日型自動車保険・地震保険・傷害疾病保険・生命保険（ご契約のしおり＋約款）・
保険会社の定款・海外旅行保険・賠償責任保険（ゴルファー保険）・団体保険・重要事項説明書。
**重要事項説明書は「条」を 1 つも持たない**文書で、見出し階層が他と違う。

## ⚠ すべて架空である

**会社名・商品名・ペットネーム・連絡先・URL・様式番号・人物名・金額はすべて架空**で、
実在の保険会社・実在の商品・実在の約款とは一切関係がない。
電話番号はゼロ埋め（`0120-000-000`）、ドメインは `example.jp` / `example.co.jp` /
`example.com` のみ。各文書の奥付に免責を明記してある。

**実在の約款の文章は、部分的にも、語順を変えただけでも含まれていない。**
参考にしたのは構造・要素の種類・レイアウト慣行のみである。

**保険商品としての内容は検証されていない。** 条文は読み取り評価のために書いたダミーで、
保険実務・法務の校閲を受けていない。**実務の参考・商品の比較・法的な参照に使ってはならない。**

## 使い方

```python
from datasets import load_dataset

docs     = load_dataset("{hf_repo_id}", "documents")        # 文書の一覧とメタデータ
qa       = load_dataset("{hf_repo_id}", "qa")               # 問答 {n_qa} 問
passages = load_dataset("{hf_repo_id}", "search-passages")  # 検索コーパス
queries  = load_dataset("{hf_repo_id}", "search-queries")   # クエリ
qrels    = load_dataset("{hf_repo_id}", "search-qrels")     # 適合判定
```

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
search/                  検索評価セット（コーパス全体。content ごとに 1 スタイル）
  passages.jsonl           検索エンジンに登録する単位
  queries.jsonl            クエリ（{n_kinds} 種）
  qrels.jsonl              適合判定（grade 2 = 答えがある / 1 = 関連する）
  id_map.json              旧 id → 新 id（v6 以前との対応）
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
| 検索・RAG | `search/passages.jsonl` ＋ `queries.jsonl` ＋ `qrels.jsonl` |

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
- **検索コーパスは重複を避けて content ごとに 1 スタイルだけ**採っている（{n_corpus_docs} 文書）。
- **qrels の grade 1 は 1 クエリ {max_related} 件で打ち切ってある。** 打ち切ると qrels に出ないので
  評価上は非適合と同じ扱いになる。どのクエリで切ったかは `queries.jsonl` の
  `related_truncated` と `n_related_total` でわかる（現行の生成では {n_queries} クエリ中
  {n_truncated} 件）。**この件数で Recall@k を解釈しない。**
- **クエリは `filters` を持つことがある。** `filtered` / `qa` / `situational` /
  `definition_masked` / `multi_hop` / `no_answer` は、絞り込み条件を**クエリ文ではなく
  `filters`（issuer / product_name / genre）で渡す**。同じ文言でも `filters` が違えば別のクエリ
  （「「(4)」は何ページにありますか」は 20 文書で同じ文字列になる）。
  メタデータを索引しない検索器は `filtered` を構造的に解けないので、
  **何を索引したかを `search_run.json` の `index_setting` に申告する**。
- **`no_answer` は gold が空集合**で、`qrels.jsonl` に 1 行も出ない。
  **何も返さないのが正解**で、`false_positive_rate` で採点する。
- **`hard_negatives` は「紛らわしいと宣言された非適合」**（他商品の同名条など）。
  grade は 0 のままだが、`confusion@k` でどれだけ釣られたかを測れる。
- **`qa.jsonl` の `answer` は型が 3 通りある**（文字列・数値・配列）。1 つの列に混ぜると
  表形式で読めないので、`answer_text`（表示用の文字列）・`answer_number`・`answer_list` に
  分けてある。**正本は各文書の `qa.json`** で、そちらは `answer` 1 本に型そのままで入っている。

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

## 素朴な検索器のベースライン

**評価セットが簡単すぎないかの目安**（`yakkan export` が実測して埋め込む）。
字面を照合するだけの 3 系統で、形態素解析も同義語辞書も使っていない。
**nDCG@1 が 0.85 を超え、かつ 3 系統の差（スプレッド）が 0.2 未満の kind は、
順位の良し悪しを測る分解能が無い**ので印を付けてある。

{baseline_table}

`term` / `heading` は「コーパス中 1 文書だけが持つ語・見出し」を引く項目検索なので、
**字面一致で解けて当然**（それでも対象が一意に決まる well-posed なクエリである）。
意味で引く力を測りたいときは `definition_masked` / `multi_hop` / `situational` を使う。

## 採点

採点ハーネスは生成元のリポジトリに入っている（`yakkan eval`）。

```
uv run yakkan eval dataset/<doc_id> --pred pred.json     # 読み取り
uv run yakkan eval --search-run run.json                 # 検索
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
- `teikan`（定款）は用語の定義表を持たない（実物の定款にも無い）ため、
  検索コーパスに `teikan` の `definition` パッセージが無い
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

Copyright (c) {copyright_year} {copyright_holder}

**帰属の書き方**（CC BY 4.0 の要求を満たす最小形）：

> 「{pretty_name}」（{copyright_holder}）, {license_name}, {hf_repo_url}

**フォントについて**：`doc.pdf` には描画に使った字形の**サブセットが埋め込まれている**
（Noto Serif JP / Noto Sans JP ＝ SIL Open Font License 1.1、IPAex 明朝 / ゴシック ＝
IPA フォントライセンス v1.0）。いずれも文書への埋め込みと、その文書の再配布を許している。
**フォントそのもの（フォントファイル）はこのデータセットに含まれていない。**
CC BY 4.0 が及ぶのは本データセットの文書・正解データ・評価セットであり、
埋め込まれた字形データには各フォントのライセンスが並行して適用される。

## 引用

```bibtex
@misc{{yakkan_synth,
  title  = {{{pretty_name}}},
  author = {{{copyright_holder}}},
  year   = {{{copyright_year}}},
  url    = {{{hf_repo_url}}},
  note   = {{Synthetic Japanese insurance policy documents with complete ground truth.
            Version {dataset_version}. Licensed under {license_id}.}}
}}
```
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
GITATTRIBUTES = """# Hugging Face Hub 用。大きなバイナリは Git LFS で追跡する。
# **このファイルは `yakkan export` が生成する。手で編集しない**（CLAUDE.md §0.4-3）。
*.png filter=lfs diff=lfs merge=lfs -text
*.pdf filter=lfs diff=lfs merge=lfs -text
# 正解とテキストは差分が読めるようにしておく（JSON/JSONL/Markdown は LFS に入れない）。
*.json text
*.jsonl text
*.md text
"""


def _fmt(value: object) -> str:
    """カードに出す数値の 3 桁区切り。**統計値を固定文字列で焼き込まないため**
    すべて呼び出し側の実測から通す（docs/data_card.md §1）。"""
    return f"{value:,}" if isinstance(value, int) else str(value)


def write_card(
    dataset_dir: Path,
    *,
    documents: Sequence[Any] = (),
    passages: Sequence[Any] = (),
    queries: Sequence[Any] = (),
    qrels: Sequence[Any] = (),
    n_corpus_docs: int = 0,
    baseline_table: str = "（ベースライン未計測）",
    dataset_version: str = "",
    hf_repo_id: str = HF_REPO_ID,
) -> Path:
    """Hugging Face のデータセットカードを `dataset/README.md` に書き出す。

    **HF はリポジトリ直下の `README.md` だけをカードとして読む。** 以前は
    `README.md`（読み方）と `DATASET_CARD.md`（HF 形式の要約）に分かれていたが、
    2 枚あると数値が食い違いうるうえ HF 側は後者を見ないので 1 枚に統合した
    （docs/decisions.md 2026-10-05）。

    数値はすべて引数で受けた実測から埋める。**固定文字列に焼き込まない**
    （docs/data_card.md §1。`dataset/README.md` が「1,944 クエリ中 28 件」を
    直書きしていて `export` を回しても更新されなかった事故の再発防止）。
    """
    from yakkan.search_set import MAX_RELATED

    def rows(items: Sequence[Any]) -> list[dict[str, Any]]:
        return [i if isinstance(i, dict) else i.model_dump() for i in items]

    docs = [d for d in rows(documents) if d.get("status") == "ready"]
    query_rows = rows(queries)
    pretty_name = "日本語保険約款 合成ドキュメントデータセット（yakkan-synth）"
    path = dataset_dir / "README.md"
    path.write_text(
        CARD.format(
            license_id=LICENSE_ID,
            license_name=LICENSE_NAME,
            license_url=LICENSE_URL,
            license_legalcode_url=LICENSE_LEGALCODE_URL,
            copyright_year=COPYRIGHT_YEAR,
            copyright_holder=COPYRIGHT_HOLDER,
            pretty_name=pretty_name,
            hf_repo_id=hf_repo_id,
            hf_repo_url=f"https://huggingface.co/datasets/{hf_repo_id}",
            dataset_version=dataset_version or "（未設定）",
            n_docs=_fmt(len(docs)),
            n_pages=_fmt(sum(int(d.get("pages") or 0) for d in docs)),
            n_genres=_fmt(len({d.get("genre") for d in docs})),
            n_styles=_fmt(len({d.get("style_id") for d in docs})),
            n_qa=_fmt(sum(int(d.get("qa_items") or 0) for d in docs)),
            n_passages=_fmt(len(passages)),
            n_queries=_fmt(len(query_rows)),
            n_kinds=_fmt(len({q["kind"] for q in query_rows})),
            n_qrels=_fmt(len(qrels)),
            n_corpus_docs=_fmt(n_corpus_docs),
            n_truncated=_fmt(sum(1 for q in query_rows if q.get("related_truncated"))),
            max_related=_fmt(MAX_RELATED),
            baseline_table=baseline_table,
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


def remove_retired(dataset_dir: Path) -> list[str]:
    """`export` が書かなくなった成果物を消す。消したファイル名を返す。"""
    removed = []
    for name in RETIRED_ARTIFACTS:
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
            pretty_name="日本語保険約款 合成ドキュメントデータセット（yakkan-synth）",
            hf_repo_url=f"https://huggingface.co/datasets/{HF_REPO_ID}",
        ),
        encoding="utf-8",
    )
    return path


def write_gitattributes(dataset_dir: Path) -> Path:
    """`dataset/.gitattributes` を書き出す（HF Hub の LFS 追跡）。"""
    path = dataset_dir / ".gitattributes"
    path.write_text(GITATTRIBUTES, encoding="utf-8")
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
