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
| bbox（画像からの位置あわせ） | `layout.elements[].fragments[].bbox` | IoU 平均 ／ IoU≥0.5 の当たり率 |
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
      "kind": "paragraph", "citation": "第2章 第1条 (1)",
      "bbox": [39.7, 573.6, 286.3, 758.2] }   // 任意。pt・原点左上。出すと IoU が採点される
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
- `--misread 0.3` を足すと、**現実の読み取り誤り**（字形の取り違え・脱字・表の行の結合・
  端の列の取りこぼし・見出しの取りこぼし・構造位置の浅い読み・段組の取り違え）で崩した
  予測を採点する。崩しは強さについて入れ子なので、**強くするほど指標が単調に悪化する**
  （`tests/unit/test_eval.py` が固定）。単調性は F1 ではなく **recall** で見る
  ——要素を落とすと誤りも落ちて precision が上がり、F1 は跳ねることがある。

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

`queries.jsonl`（`query_id` / `kind` / `query` / `note` / `n_relevant` / `n_exact` /
`n_related` / `n_related_total` / `related_truncated`）と
`qrels.jsonl`（`query_id` / `passage_id` / `grade`）。**grade は 2＝答えがそこにある、1＝関連する。**
qrels に無い組み合わせは 0（非適合）。

**grade 1 は 1 クエリ 20 件で打ち切る**（`MAX_RELATED`）。打ち切ると qrels に出ないので、
評価上は非適合と同じ扱いになる。どのクエリで何件落としたかは
`related_truncated` / `n_related_total` でわかる（現状 1,944 クエリ中 28 件、
おもに「事故」のような頻出の定義語）。**Recall@k をこの 28 件で解釈しない。**
打ち切るときは文書をまたいで均等に拾うので、特定の文書だけが残ることはない。

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

**Recall@k は 1 に届かないことがある。** 適合が k 件を超えるクエリでは、上位 k 件を
すべて適合で埋めても `k / 適合数` が上限になる。満点の並びでも全体の recall@10 は
0.976（term は 0.869）。到達できる上限を `recall_ceiling@k` として併記してあるので、
**Recall@k はこの上限と比べて読む**（docs/remaining_issues.md T2）。
順位の良し悪しを見たいときは nDCG@k を使う。

---

## 3. 予測に使う語彙

**採点は完全一致で行う。** 何を出せばよいかがここに書いていないと当てようがないので、
語彙をここに定める（docs/remaining_issues.md W5。VLM が `section` / `subsection` と出して
`kind` 正解率 0.0 になった）。

### `outline[].kind` と `elements[].kind`

`part` / `chapter` / `rider`（特約）/ `section` / `article` / `paragraph` /
`item` / `subitem` / `subsubitem` / `appendix`（別表・付表）/ `appendix_section`。

**`kind` は紙面の記号ではなく構造の深さを表す。** 条を持たないジャンル
（重要事項説明書）でも、いちばん外の区分が `chapter`、その下が `section`、
本文を持つ単位が `article`、その中の列挙が `item`。

| 紙面 | kind |
|---|---|
| 「第N編」 | `part` |
| 「第N章」／重要事項説明書の「1」「2」の大見出し | `chapter` |
| 番号を持たない特約の題名（「携行品損害補償特約」） | `rider` |
| 「第N節」／重要事項説明書の「(1)」「(2)」 | `section` |
| 「第N条」／重要事項説明書の「①」「②」の小見出し | `article` |
| 条の中の「(1)」「1」の項 | `paragraph` |
| 「①」「1.」の号 | `item` |
| 「別表N」「付表N」「附則」 | `appendix` |
| 別表の中の「第N」 | `appendix_section` |

**迷ったら出さない**（`null`）。出さなければ `kind_acc` の母数から外れるだけで、
他の指標は下がらない。

### `outline` に入れるもの

**見出しだけでなく、番号のある項も入れる。** 「（1）」「2」のように紙面に番号が出る項は
`label` を持つ節点なので outline の一部（`kind: "paragraph"`）。
golf-0001 では 96 件中 57 件がこれで、**入れないと F1 が 0.58、入れると 0.98**になった。
番号も見出し文言も持たない節点（条の最初の項）は入っていない（T7）。

### `tables[].cells`

`grid` は**見た目**（結合を展開した矩形）、`cells` は**意味**（行見出し・列見出し・値の 3 つ組）。
**別々に採点する。** `grid` が完全一致（TEDS 1.0）でも、`cells` を出さなければ
表セル F1 は 0 になる。両方出すこと。

**列挙として組まれた表は `tables` に出さない。** 「次に掲げる事由」の受けのように、
紙面では格子でも読み手には箇条書きであるものは `enumerations` に出す
（採点側も `tables` から外してある）。両方に出す必要はない。

キャプションは**正規化して**突き合わせる。全角の文書で gold が「表１」でも、
予測は「表1」でよい。

### `figures[].nodes` の粒度

図の中の**文字が入る箱はすべて 1 ノード**。段の見出しだけでなく、段に添えた説明行も数える。
種別ごとの `role`：

| 図の種別 | ノード | エッジ |
|---|---|---|
| `flowchart` | 宣言された節点（`start` / `process` / `decision` / `end`） | 宣言された矢印（`flow`） |
| `tree` | 各節点 | 親 → 子（`child`） |
| `steps` | 段（`step`）＋ 段の説明行（`detail`）・お願い（`ask`）・書類例（`doc`） | 段の順（`next`）と 段 → 説明（`child`） |
| `timeline` | 目盛（`tick`）＋ 区間（`span`）＋ できごと（`event`）の3種 | 目盛どうしの順（`tick→tick`、`next`）／区間→両端の目盛（`span→tick`、`from`・`to`）／できごと→対応する目盛（`event→tick`、`at`）。**区間・できごとのノードを介さず目盛どうしを直接つないではいけない**（区間は目盛の弦ではなく、目盛につながる独立したノード） |
| `annotated_mock` | 記載欄（`field`）＋ 凡例（`legend`） | 欄 → 凡例（`explains`） |
| `matrix` | 行（`row`）・列（`col`）・交点（`cell`）・凡例（`legend`） | 行 → 交点 → 列（`cell`） |

`paths` は「入次数 0 のノード → 出次数 0 のノード」の全経路をラベルの列で。
**`role` は採点に使わない**（ノードは `label` の多重集合で突き合わせる）。

## 4. スキーマ

| ファイル | スキーマ | モデル |
|---|---|---|
| 予測 JSON | `schema/prediction.schema.json` | （手書き） |
| 検索結果 JSON | `schema/search_run.schema.json` | （手書き） |
| `elements.jsonl` | `schema/element.schema.json` | `yakkan.export_models.ElementRow` |
| `passages.jsonl` | `schema/passage.schema.json` | `Passage` |
| `queries.jsonl` | `schema/query.schema.json` | `Query` |
| `qrels.jsonl` | `schema/qrel.schema.json` | `Qrel` |

`uv run yakkan schema export` で書き出す。`tests/unit/test_export_models.py` が
「生成物がモデルを通る」「`schema/` が最新」を固定している。

## 5. 生成のしかた

```
uv run yakkan export            # elements.jsonl / passages.jsonl / dataset/search/*
```

`yakkan batch` の最後にも走るので、通常は個別に叩かなくてよい。
