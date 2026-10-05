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
| 検索 | `dataset/search/{passages,queries,qrels}.jsonl` | nDCG@k ／ Recall@k ／ `exact_recall@k` ／ `r_precision` ／ MRR ／ `doc@1` ／ `confusion@k` ／ `false_positive_rate` |

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
| `context_header` | 「〈商品名〉／〈発行者〉／〈citation〉」の 1 行。**索引に前置するかは利用者の選択** |

**コーパスは content ごとに 1 スタイル**だけを採る。同じ内容を別スタイルで描いた文書は
本文が同一で、検索評価では重複ノイズにしかならないため。

**`definition` は定義表（`semantic_type: definitions`）の 1 行**である。
`source.json` の `defined_terms` は `{term:}` 解決用のメタデータで**紙面に描画されていない**ので、
パッセージにしない（紙面に存在しない正解を作らないため。`outline` から紙面に出ない節点を
外した `docs/remaining_issues.md` T7 と同じ方針）。定義表そのものは `table` として別に出ているので、
**同じ定義文が `definition`（行）と `table`（表全体）の 2 つの粒度で引ける**。
`term` クエリでは行が grade 2、表が grade 1 になる。

### クエリと qrels

`queries.jsonl` と `qrels.jsonl`（`query_id` / `passage_id` / `grade`）。
**grade は 2＝答えがそこにある、1＝関連する。** qrels に無い組み合わせは 0（非適合）。

| フィールド | 意味 |
|---|---|
| `query_id` | `q_<kind>_<生成キーのハッシュ>`。**content が増えても変わらない**（旧版の通し番号との対応は `id_map.json`） |
| `kind` | 下表の 10 種 |
| `query` | 検索器に渡すクエリ文 |
| `filters` | 構造化した絞り込み条件（`issuer` / `product_name` / `genre`）。**空でなければクエリの一部** |
| `facet_in_text` | 絞り込みの手がかりがクエリ文そのものに入っているか |
| `relevance_rule` | この gold がどの規則で作られたか（何を返せばよいかが読めるように） |
| `hard_negatives` | **字面は一致するが非適合**なパッセージ（他商品の同名条など）。grade は 0 |
| `n_relevant` / `n_exact` / `n_related` / `n_related_total` / `related_truncated` | 適合の件数と打ち切りの印 |

**`filters` はクエリの一部である。** 同じ文言でも `filters` が違えば別のクエリとして採点する
（「「(4)」は何ページにありますか」は 20 文書で同じ文字列になり、
文書を絞らないと答えが決まらない。`qa` の 56% が「第N条」「表N」のような文書ローカルな
番号だけを手がかりにしている）。**メタデータを索引していない検索器は `filtered` を
構造的に解けない**ので、何を索引したかを `search_run.json` の `index_setting` に申告する。

**grade 1 は 1 クエリ 20 件で打ち切る**（`MAX_RELATED`）。打ち切ると qrels に出ないので、
評価上は非適合と同じ扱いになる。どのクエリで何件落としたかは
`related_truncated` / `n_related_total` でわかる。正確な件数は文書構成が変わるたびに動くため
ここには固定値を書かない（`dataset/README.md` が実測値を埋め込んで生成される）。

| kind | 作り方 | gold | 何を測るか |
|---|---|---|---|
| `term` | **コーパス中 1 文書だけが定義している語**（`df_docs == 1`） | grade 2 = その語の定義行、grade 1 = 同じ文書でその語を使っている条 | 項目検索。**字面一致で解けて当然**だが対象は一意に決まる |
| `heading` | **1 文書だけが持つ条見出しの文言**（番号ラベルは落とす） | grade 2 = 同名の条、grade 1 = その条の表・図とその条を参照する条 | 同上 |
| `scoped` | 「会社名＋商品名＋見出し」 | grade 2 = **その文書の同名の条すべて** | テキストだけで文書を絞れるか |
| `filtered` | 見出しの文言のみ＋`filters` | 同上 | メタデータ索引・ハイブリッド絞り込み |
| `enumeration` | **広く使われる語・見出しの網羅要求**（「…をすべて挙げてください」） | grade 2 = 全文書のその語の定義行／同名の条。**grade 1 は作らない** | 網羅。`Recall@100` と `r_precision` で読む |
| `qa` | 既存 QA の問い＋`filters` | grade 2 = evidence を含むパッセージ、grade 1 = 同じ条の別のパッセージ | 意味検索 |
| `definition_masked` | **その語を使っている条文**を文脈として与え、語を `〔用語〕` に隠す | grade 2 = その語の定義行、grade 1 = 出題に使った条文 | 意味で結びつける力。**字面では解けない** |
| `multi_hop` | 参照元の文言（参照先の見出しは書かない） | grade 2 = **参照先**の条、grade 1 = 参照元 | 参照を辿れるか |
| `situational` | 執筆 QA の `apply` から**場面の記述だけ**を採る | grade 2 = 根拠の条、grade 1 = 同じ条の別のパッセージ | 場面から条文を引く力 |
| `no_answer` | その文書に**無い**見出し・用語を `filters` で絞って聞く | **空集合**（`qrels.jsonl` に 1 行も出ない） | 根拠が無いときに黙れるか |

**広く使われる語を素のクエリにしない**のが設計の要点である。「保険金」は 80 文書・
1,969 パッセージに出るのに定義表に項目を立てているのは 2 文書だけで、
**どの文書を返すべきかがクエリから決まらない**。`df_literal >= 10`（コーパス 90 文書の
約 1/9 ＝ 1 ジャンルぶん）の語は `enumeration` に回し、順位ではなく網羅を測る
（設計の根拠は `docs/search_query_design.md`、実施の記録は `docs/search_query_plan.md`）。

### 検索結果の形

```jsonc
{
  "index_setting": "text_only",   // text_only / with_context_header / with_metadata
  "runs": [ { "query_id": "q_heading_1f3a…", "passages": ["doc::ch1_a1", "doc::ch2_a3", "…"] } ]
}
```

```
uv run yakkan eval --search-run run.json
uv run yakkan eval --oracle                 # 満点の並びで自己評価
```

**`no_answer` のクエリには空の `passages` を返す**（何も返さないのが正解）。
`runs` に含めなければ採点されない。

### 指標

**kind ごとと全体で報告する。** kind によって意味のある指標が違う。

| 指標 | 読み方 |
|---|---|
| `ndcg@1/5/10/100` | 順位の良し悪し。`term` / `heading` / `scoped` / `filtered` / `qa` の主指標 |
| `recall@k` ／ `recall_ceiling@k` | **上限と比べて読む。** 適合が k 件を超えるクエリでは `k / 適合数` が上限（T2） |
| `exact_recall@5/10` | **grade 2 だけを見た再現率。** grade 1 が字面で簡単に取れる kind（`definition_masked` はクエリ文が grade 1 の引用）では、「答えそのもの」を引けたかが `recall@k` から読めない |
| `r_precision` | 上位 R 件（R = 適合数）の適合率。`enumeration` の主指標 |
| `mrr` | 最初の適合の順位 |
| `doc@1` / `doc_recall@5/10` | **正しい文書を引けたか。** 文書同定と文書内の順位付けは別の能力（実測：`scoped` は doc@1 0.904 なのに ndcg@1 0.058 ＝ 文書は当たるが条が当たらない） |
| `confusion@5/10` | 上位 k 件に占める `hard_negatives` の割合。**広く使われる単語で釣られていないか** |
| `false_positive_rate` | `no_answer` で 1 件以上返したか。**0.0 が正解** |

`no_answer` の行は `ndcg` 等が 0.0 と表示されるが、これは**その kind では測れない**という意味で、
読むべきは `false_positive_rate` だけである。

**評価セットが簡単すぎないかの目安**として、`dataset/README.md` に素朴な検索器 3 系統
（`title` 完全一致・文字 2-gram BM25・文字 unigram TF-IDF）のスコア表が
`yakkan export` のたびに実測されて埋め込まれる。**nDCG@1 が 0.85 を超え、かつ 3 系統の差が
0.2 未満の kind は、順位の良し悪しを測る分解能が無い**ので印が付く。
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
| 検索結果 JSON | `schema/search_run.schema.json` | `SearchRun`（`index_setting` つき） |
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
