# evaluation.md — 予測 JSON の形と採点のしかた

> CLAUDE.md §9 の実装。`docs/eval_dataset_plan.md` の P6・P7・P8。
> 読み取り側（LLM/VLM・レイアウト解析・検索）がこの形で出せば、`yakkan eval` がそのまま採点する。

## 0. 何を評価するか

| 観点 | 評価データ | 指標 |
|---|---|---|
| ページ本文の読み取り | `answer.json` の `pages[].text` | CER（文字誤り率。低いほど良い） |
| 見出しツリー | `answer.json` の `outline` | F1／見出しの種別・ページ・位置づけの正解率 |
| **構造内の位置づけ** | `derived.labels[].citation` | 本文が当たった要素のうち citation が一致した割合 |
| 表の構造 | `grid`（結合展開後）＋ `header_path` | TEDS ／ セル値 F1（行見出し・列見出し・値の 3 つ組） |
| 図の構造 | `derived.figures[].graph` ＋ `paths` | ノード F1 ／ エッジ F1 ／ 経路 F1 |
| 列挙の位置づけ | `derived.enumerations` | 項目の順番つき一致率 |
| 読み順 | `layout.pages[].reading_order` | Kendall の τ |
| QA | `qa.json` | 完全一致 ／ 部分一致 |
| 検索 | `dataset/search/{passages,queries,qrels}.jsonl` | nDCG@k ／ Recall@k ／ MRR |

**突合はすべて中身で行う。** 予測に我々の内部 id は無い前提なので、
テキストの正規化一致（NFKC ＋ 空白除去）、見出しは `(label, title)`、
表と図は `caption_label`（無ければ出現順）、QA だけ `id` で対応づける。

---

## 1. 読み取りの予測 JSON

```jsonc
{
  "doc_id": "auto-0001--nl-a4-2col-mincho",

  // ページ本文。ヘッダ・フッタ・図中の文字は含めない（answer.pages[].text と同じ範囲）
  "pages": [ { "number": 1, "text": "…" } ],

  // 見出しツリー。文書順に並べる
  "outline": [
    { "label": "第2章", "title": "賠償責任条項", "heading_text": "第2章　賠償責任条項",
      "kind": "chapter", "page": 6, "citation": "第2章" }
  ],

  // 本文の要素。**読み順に**並べる（読み順の τ はこの並びで測る）
  "elements": [
    { "text": "当会社は、被保険者が…支払います。", "page": 6,
      "kind": "paragraph", "citation": "第2章 第1条 (1)" }
  ],

  // 表。grid は**結合を展開した**矩形。cells は意味座標つきの値
  "tables": [
    { "caption_label": "表1",
      "grid": [["用語", "定義"], ["被保険者", "…"]],
      "cells": [ { "row_headers": ["被保険者"], "col_headers": ["定義"], "value": "…" } ] }
  ],

  // 図。nodes[].id は予測内で一意なら何でもよい（edges から参照するためだけに使う）
  "figures": [
    { "caption_label": "図1",
      "nodes": [ { "id": "n1", "label": "事故の発生", "role": "start" } ],
      "edges": [ { "from": "n1", "to": "n2", "relation": "flow" } ],
      "paths": [ ["事故の発生", "当会社へ連絡"] ] }
  ],

  // 列挙。citation は親（導入文）の位置づけ
  "enumerations": [ { "citation": "第2章 第3条 (1)", "items": ["…", "…"] } ],

  // QA。id は qa.json のものをそのまま使う
  "qa": [ { "id": "qa_auto_001", "answer": "3倍" } ]
}
```

- すべてのキーは**任意**。無い観点はその指標が 0 になるだけで、他の観点は採点される。
- スキーマは `schema/prediction.schema.json`。
- **満点の予測の作り方**は `yakkan/eval/oracle.py` が実装例。`yakkan eval <dataset/doc> --oracle` で
  自分で満点の予測を作って採点できる（ハーネスの自己評価に使う）。

### 採点

```
uv run yakkan eval dataset/auto-0001--nl-a4-2col-mincho --pred pred.json
uv run yakkan eval dataset/auto-0001--nl-a4-2col-mincho --oracle       # 自己評価
uv run yakkan eval dataset/auto-0001--nl-a4-2col-mincho --pred pred.json --out score.json
```

---

## 2. 検索の評価

### コーパス

`dataset/search/passages.jsonl`。**検索エンジンに登録する単位**で、1 行 1 パッセージ。

| フィールド | 意味 |
|---|---|
| `passage_id` | `"<doc_id>::<element_id>"`。qrels の突合キー |
| `doc_id` / `content_id` / `genre` / `product_name` / `issuer` | 絞り込み・メタ検索用 |
| `kind` | `article` / `paragraph` / `table` / `figure` / `definition` / `other` |
| `title` | 条の見出し文言・表題・用語 |
| `citation` | 「第2章 第1条」。**構造で絞り込む検索の評価に使う** |
| `text` | 登録する本文（表は行ごとに平文化、図は alt ＋ facts ＋ 経路） |
| `element_ids` / `pages` | 元の要素とページ（ハイライト・出典表示の検証用） |

**コーパスは content ごとに 1 スタイル**だけを採る。同じ内容を別スタイルで描いた文書は
本文が同一で、検索評価では重複ノイズにしかならないため。

### クエリと qrels

`queries.jsonl`（`query_id` / `kind` / `query` / `note` / `n_relevant`）と
`qrels.jsonl`（`query_id` / `passage_id` / `grade`）。**grade は 2＝答えがそこにある、1＝関連する。**
qrels に無い組み合わせは 0（非適合）。

| kind | 作り方 | 何を測るか |
|---|---|---|
| `term` | 定義語そのもの | 項目検索。正解は**全文書の**その語の定義パッセージ |
| `heading` | 条の見出し文言 | 項目検索。**同名の条が複数文書にある**ので、網羅性が要る |
| `scoped` | 「商品名＋見出し」 | 絞り込み。同名の条があるなかで**その文書だけ**を当てる |
| `qa` | 既存 QA の問い | 意味検索。正解は evidence を含むパッセージ（同じ条の別項は grade 1） |

### 検索結果の形

```jsonc
{ "runs": [ { "query_id": "q_head_0001", "passages": ["doc::ch1_a1", "doc::ch2_a3", "…"] } ] }
```

```
uv run yakkan eval --search-run run.json
uv run yakkan eval --oracle                 # 満点の並びで自己評価
```

nDCG@1/5/10・Recall@1/5/10・MRR を、**クエリ種別ごとと全体で**報告する。

---

## 3. 生成のしかた

```
uv run yakkan export            # elements.jsonl / passages.jsonl / dataset/search/*
```

`yakkan batch` の最後にも走るので、通常は個別に叩かなくてよい。
