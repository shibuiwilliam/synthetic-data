# yakkan-synth — 日本語保険約款の合成データ生成基盤

実在の保険約款そっくりだが **完全に架空** の日本語文書（PDF）と、その **完全な正解データ**（JSON）を
対で生成する。ドキュメント読み取りシステム（OCR / レイアウト解析 / VLM / 構造化抽出）の開発検証用。

- 正解 JSON が唯一の真実で、PDF はその決定論的な描画結果（JSON → HTML → PDF）。
- 1 文書 20 ページ以下。テキスト・章節項構造・表・図・参照関係・QA を正解として持つ。
- 仕様は `CLAUDE.md`（憲章）と `docs/`（詳細）。**実装と食い違ったら仕様側を先に直す。**

現況（`dataset_version: v7`）：**10 ジャンル・100 content・114 データセット**
（うち `ready` 113／`failed` 1）・**1,458 ページ**・QA 5,085 問。
素性（規模・内訳・検証結果・制限と偏り）は生成物側の **`dataset/data-card.md`** を最初に読む。

## セットアップ

必要なもの：Python 3.12（uv が入れる）、[uv](https://docs.astral.sh/uv/)、Pango。

```bash
# macOS
brew install pango
# Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev

uv sync            # 依存の導入（= make setup）
make doctor        # 環境の検査（Python / WeasyPrint / Pango / フォント / pypdfium2）
make check         # ruff + pytest
make smoke         # 動作確認用の PDF と PNG を scratch/smoke/ に生成
```

### macOS の注意

Homebrew の dylib は dyld の既定検索パスに無いため、素の `uv run` では WeasyPrint の import が失敗する。
`make` 経由なら `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が自動で渡る。直接叩くときは自分で付ける。

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run yakkan doctor
```

詳細と他の落とし穴は `docs/gotchas.md`。

## ディレクトリ

| パス | 中身 |
|---|---|
| `CLAUDE.md` | プロジェクト憲章（ハードルール・設計原則・lint 一覧・マイルストーン） |
| `docs/` | 詳細仕様（schema / rendering / style_guide / blueprints / repo_layout）と運用ログ（decisions / progress / gotchas） |
| `yakkan/` | Python パッケージ（モデル・番号付け・描画・レイアウト抽出・検証・QA・CLI） |
| `blueprints/` `styles/` `library/` | ジャンル定義・スタイル・条文ライブラリ（宣言） |
| `content/<content_id>/` | 執筆成果（コミットする） |
| `specs/batch_*.yaml` | 生成バッチの定義（content × style × seed）。`dataset/` はここから再生成する |
| `dataset/<doc_id>/` | 生成物（コミットしない。`specs/` から再生成する。**手編集禁止**） |
| `assets/fonts/` | 同梱フォント（OFL / IPA ライセンス。出典は `SOURCES.md`） |
| `TASK.md` | 人間の判断・作業を待っている項目の一覧（AI は未回答の判断を代わりに下さない） |
| `insurance-contracts-calculation/` | 計算・判定の規定とその正解プログラムを足す**別プロジェクト**。本体とは独立に扱う |

配置の正本は `docs/repo_layout.md`。新しいファイルを置く前にそちらを読む。

## データセットの読み方

`dataset/<doc_id>/` が 1 文書ぶん。`doc_id` は `<content_id>--<style_id>`
（同じ内容を別のレイアウトで描いたものは `content_id` が同じで `style_id` が違う）。

| ファイル | 中身 |
|---|---|
| `doc.pdf` | 生成 PDF。フォント埋め込み・テキスト層あり・タグ無し |
| `pages/page-NNN.png` | 150dpi のページ画像（画像ベースの読み取り検証用） |
| `source.json` | 内容と意味。**レイアウト非依存**（判型・段組を変えても不変） |
| `layout.json` | 描画結果。ページ・要素ごとの bbox・読み順・ヘッダ／フッタ |
| `answer.json` | 派生（ページ別の期待テキスト・アウトライン）。**`source` と `layout` は内包しない**（同じ場所に実体がある）。3 つをまとめて扱うときは `yakkan.answer.load_answer(dir)` |
| `elements.jsonl` | 1 行 1 要素の平らな索引。**評価スクリプトはまずこれを読む** |
| `passages.jsonl` | 1 行 1 パッセージ（検索評価の単位）。`elements.jsonl` を検索向けに束ねたもの |
| `qa.json` | 問答（自動生成 30 問＋執筆 15 問） |
| `render.html` | デバッグ用の中間 HTML（配布対象外） |

`dataset/` の直下にはコーパス全体のファイルがある。

| パス | 中身 |
|---|---|
| `manifest.json` | 全文書の一覧（ページ数・字数・表/図/脚注/参照の数・status）と `dataset_version` |
| `data-card.md` | **利用者向けデータカード**（規模・内訳・正解の中身・検証結果・制限と偏り）。最初に読む |
| `README.md` | **Hugging Face のデータセットカード**（要約・読み方・ベースライン表・ライセンス・引用） |
| `LICENSE` | CC BY 4.0 の表示と帰属の書き方（埋め込みフォントの扱いも） |
| `.gitattributes` | HF Hub 用。`*.png` と `*.pdf` を Git LFS で追跡する |
| `qa.jsonl` | 全文書の QA を 1 行 1 問に平らにしたもの（HF の `qa` コンフィグ） |
| `documents.jsonl` | `manifest.json` を 1 行 1 文書に平らにしたもの（HF の `documents` コンフィグ） |
| `search/` | 検索評価セット：`passages.jsonl`／`queries.jsonl`／`qrels.jsonl`／`id_map.json` |

これらは手で書かず `uv run yakkan export` ／ `manifest update` ／ `datacard update` で作り直す。

### answer.json の構造

```jsonc
{
  "doc_id": "auto-0001--nl-a4-2col-mincho",
  "source": { /* 内容と意味。下記 */ },
  "layout": { /* 描画結果。下記 */ },
  "pages":  [ { "number": 1, "text": "…", "text_with_furniture": "…", "chars": 1234 } ],
  "outline":[ { "id": "ch1_a1", "depth": 1, "label": "第1条", "title": "この条項の補償内容",
                "heading_text": "第1条（この条項の補償内容）", "page": 3 } ]
}
```

**`source`** — 執筆した内容に、`build` が派生を足したもの。

- `body[]` / `appendices[]`：`Node` の木（part / chapter / rider / section / article / paragraph / item …）。
  `rider`（特約）は**番号を持たない**種別で、中の条は特約ごとに第1条から始まる。
  `jyusetsu`（重要事項説明書）は**条を 1 つも持たない**文書で、大見出し ›（N）› ① の 3 階層。
- `derived.labels[node_id].run_in_label`：条見出しを条の上に置く体裁（`group`）で、
  **条ラベルが本文の先頭に走り込む**ときのラベル。条そのものの `label` は別に残る。
- `body[].badges`：見出しの右に付く分類ラベル（「契約概要」「注意喚起情報」）。
  `<node_id>__badge<i>` の id で `derived.plain_text` と `layout.elements` に入る。
  `Node` は **見出しの文言（`title`）しか持たない**。「第1条」のような番号ラベルは持たず、
  木の位置と番号方式から導出して `derived.labels` に入れる。
- `derived.labels[node_id]`：`{ label, title, heading_text, path, depth }`。
  読み取り側の粒度差を測れるよう、**ラベル・文言・連結形の 3 つを別々に持つ**。
- `derived.plain_text[element_id]`：マークアップを解き参照を解決した期待テキスト。
  `with_label`（「第1条（…）」を含む）と `without_label` の 2 系統。
- `derived.refs[]`：条項間参照。`{ from_id, to_id, mode, rendered }`。`rendered` が紙面上の表記。
- `derived.tables[table_id].header_path[cell_id]`：セルの意味座標 `{ row_headers, col_headers }`。
  結合セルを展開したうえでの行見出し・列見出しなので、表の意味検索の正解に使える。
- `derived.figures[fig_id]`：`node_order`（描画順）と `paths`（flowchart の開始→終了の全経路）、
  `resolved_labels`（図の中に書いたトークンの「生文字列 → 解決後」）。
  **紙面に出るのは解決後の文字列**なので、図のラベルを正解として使うときはこれを当てる。
  `derived.formulas[formula_id].resolved_labels` も同じ。
- 表は `grid`（結合セル込みの見た目）と `records`（意味レコード）の**二重表現**を持つ。

**`layout`** — 同じ内容を別スタイルで描けば変わる部分。

- `pages[]`：`number` / `columns` / `header` / `footer` / `reading_order`（要素 id の列）/
  `text_lines[]`（行単位の bbox・文字列・`region`）。
- `elements[element_id]`：`fragments[]`（`page` と `bbox`）。
  **段またぎ・改ページで分割された要素は fragment が複数になる。**
- `figures[fig_id]`：図そのものの bbox と `nodes[node_id]` の bbox（**ページ座標**）。

### 座標系

- 単位は **PDF ポイント（pt）**、原点は**ページ左上**、y は下向き。
- PNG 座標に直すには `dpi / 72` 倍する（同梱の PNG は 150dpi なので約 2.083 倍）。
- `layout.page_size_pt` にページの幅と高さが入っている。

### 繰り返し表頭とヘッダ／フッタの扱い（重要）

PDF のテキスト層には、**正解 1 件に対して複数回現れる文字列**がある。二重に数えると指標が歪む。

- **繰り返し表頭**：表がページや段をまたぐと表頭が再掲される。
  `layout.elements[cell_id].fragments[].repeated` が `true` の断片がそれ。
  `answer.pages[].text` には**最初の 1 回だけ**入れてある。
- **ヘッダ・フッタ**：`layout.pages[].header` / `.footer` にだけ入れ、`reading_order` には含めない。
  `answer.pages[].text` にも入っていない。両方を含む文字列が要るときは `text_with_furniture` を使う。
- したがって、**ページ別 CER は `pages[].text` と突き合わせる**のが正しい。
  PDF から素朴に抽出した文字列とは、この 2 点ぶんずれる。

### qa.json

```jsonc
{ "doc_id": "…",
  "items": [ { "id": "qa_auto_001", "type": "table_lookup", "question": "…",
               "answer": "…", "answer_type": "string",
               "evidence": ["tbl_x__r2c3"], "page_hint": [5], "source": "auto" } ] }
```

- `type` は 11 種別：`locate` `extract` `definition` `table_lookup` `table_reason`
  `figure_path` `figure_fact` `crossref` `count` `negative` `apply`。
  `apply` は「場面に規定を当てはめて値を導く」型で、執筆 QA にのみ現れる。
- `source` が `auto` なら機械生成（1 文書 30 問）、`authored` なら人が書いたもの（15 問）。
  執筆 QA の原本は `content/<content_id>/qa_authored.json` にあり、`yakkan qa` が合流させる。
- `evidence` は `layout.elements` に存在する要素 id なので、**そこから bbox が引ける**。
- `answer_type` は `string` / `number` / `list`。

### 注意点

- **同じ `content_id` の別 `style_id` は、内容が同じでレイアウトだけが違う。**
  レイアウト頑健性を測るときはこの対を使う。学習と評価に分けるときは `content_id` で分けること
  （`doc_id` で分けると同じ文章が両側に入る）。
- **決定論**：同じ `content_id` / `style_id` / 依存バージョンなら、同じ JSON と同じテキスト層の PDF が出る。
  PDF のメタデータ日時は固定値。
- **1 文書 20 ページ以下**。これを超えるものは生成失敗として扱っており、データセットに入っていない。
- **図の中の文字は PDF のテキスト層に載るが、`layout.pages[].text_lines` には出ない**
  （インライン SVG は置換ボックスとして扱われるため）。図の文字の正解は
  `source` の diagram と `layout.figures[].nodes` を見る。
- 縦書き・ルビ・スキャン風の劣化画像は v1 では作っていない。
- 会社名・商品名・連絡先・様式番号・人物名はすべて架空。URL は `example.jp` 系、
  電話番号はゼロ埋めのみ。実在の約款の文章は 1 文も入っていない。

## 主なコマンド

```bash
make help                              # ターゲット一覧
uv run yakkan doctor                   # 環境検査
make doc CONTENT=auto-0001 STYLE=nl-a4-2col-mincho   # 1 文書の生成（build → render → verify）
make batch SPEC=specs/batch_v1.yaml    # バッチ生成（lint → build → render → verify → qa）

uv run yakkan scaffold --genre auto --content-id auto-0004 --seed 4   # 執筆用スケルトン
uv run yakkan lint content/auto-0001 [--similarity]                   # 執筆物の検査
uv run yakkan build content/auto-0001                                 # derived を付ける
uv run yakkan render content/auto-0001 [--style <id>] [--report]      # PDF と PNG
uv run yakkan verify dataset/<doc_id>                                 # 正解の検証
uv run yakkan qa dataset/<doc_id> [--validate] [--report]             # answer.json と QA
uv run yakkan manifest update                                         # 一覧の作り直し
uv run yakkan datacard update                                         # dataset/data-card.md
uv run yakkan export                                                  # 評価向けの派生成果物
uv run yakkan schema export                                           # schema/*.schema.json
uv run yakkan clean --stale                                           # 古い生成物の掃除

uv run yakkan eval dataset/<doc_id> --pred pred.json   # 読み取りの採点（--oracle で自己評価）
uv run yakkan eval --search-run run.json               # 検索の採点
```

版面の目視レビュー（崩れはページ数と lint が通っても起きる）は、`render` が既定で出す
`dataset/<doc_id>/pages/*.png` を開いて行う。手順は `.claude/commands/review.md`（`/review <doc_id>`）と
`docs/authoring_checklist.md`。

## 評価

| 対象 | コマンド | 指標 |
|---|---|---|
| 読み取り（OCR / レイアウト / 表 / 図 / QA） | `yakkan eval dataset/<doc_id> --pred pred.json` | ページ別 CER・outline F1・構造位置 citation・表 TEDS とセル F1・図のノード/辺/経路 F1・読み順 Kendall τ・QA 一致 |
| 検索 / RAG | `yakkan eval --search-run run.json` | nDCG@k・Recall@k・`exact_recall@k`・`r_precision`・MRR・`doc@1`・`confusion@k`・`false_positive_rate` |

予測 JSON の形は `schema/prediction.schema.json`、検索結果の形は `schema/search_run.schema.json`、
語彙と採点のしかたは `docs/evaluation.md`。`--oracle` で満点の予測を作れるので、
採点側の実装を検証してから本番の予測を流すとよい。

検索クエリは 10 種（`term` `heading` `scoped` `filtered` `enumeration` `qa`
`definition_masked` `multi_hop` `situational` `no_answer`）。素朴な文字 2-gram BM25 で
飽和する kind（`term`・`heading`）には `dataset/README.md` のベースライン表で印を付けてある。
設計の経緯は `docs/search_query_design.md`、実測は `docs/search_query_plan.md`。

## ライセンスと架空性

生成される文書の会社名・商品名・連絡先・様式番号はすべて架空で、実在の保険会社・商品とは関係がない。
参考にした実在約款は **構造のみ**（見出し階層・表の列構成・図の種別）で、文章は一切引用していない。
参考にした URL の一覧は `docs/reference_structures.md` §3.2。

- **コード・仕様・執筆成果（`yakkan/` `docs/` `content/` ほか）**：親リポジトリの `LICENSE`（MIT）。
- **同梱フォント**：OFL / IPA フォントライセンス。出典・版・SHA256 は `assets/fonts/SOURCES.md`。
- **生成データセット（`dataset/`）**：**CC BY 4.0**（`TASK.md` T11・2026-10-05 決定）。
  本文と帰属の書き方は `dataset/LICENSE`。配布先は Hugging Face Datasets
  `cvusk/synthetic-japanese-insurance-documents`（控えを GitHub Releases）。
  手順は **`docs/distribution.md`**。
  なお `doc.pdf` には描画に使った字形の**サブセットが埋め込まれている**（OFL / IPA）。
  フォントファイル自体はデータセットに含まれない。
