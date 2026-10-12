# yakkan-synth — 日本語保険約款の合成データ生成基盤

**完全に架空でありながら、本物に近い日本語の保険約款**（PDF）と、その内容に対応する
**正解データ**（JSON）を生成するプロジェクトです。

OCR、レイアウト解析、VLM、構造化抽出などの文書読み取りシステムや、
検索・RAG システムの開発・検証を主な用途としています。

## 特長

- **正解 JSON を唯一の情報源（Single Source of Truth）**とし、PDF は正解 JSON から
  決定論的に描画します（JSON → HTML → PDF）。
- 各文書は 20 ページ以内で、テキスト、章・節・項の構造、表、図、参照関係、QA の
  正解データを保持します。
- 同じ内容を異なるレイアウトで描画できるため、レイアウトに対する読み取り性能を比較できます。
- 文書読み取りと検索の評価ハーネスを備えています。

仕様は `CLAUDE.md`（プロジェクト憲章）と `docs/`（詳細仕様）にまとめています。
実装と仕様に相違がある場合は、先に仕様を更新してください。

## 現在の状態

`dataset_version: v7` は完成しています。

| 項目 | 実測値 |
|---|---:|
| ジャンル | 10 |
| コンテンツ | 100 |
| 文書 | 113（`ready` 113、`failed` 0） |
| ページ | 1,437 |
| QA | 5,085 問 |

規模、内訳、検証結果、制限、偏りについては、生成物に含まれる
`dataset/data-card.md` を最初に確認してください。

## セットアップ

必要な環境は Python 3.12、[uv](https://docs.astral.sh/uv/)、Pango です。

```bash
# macOS
brew install pango

# Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev

uv sync            # 依存関係をインストール（make setup と同じ）
make doctor        # Python、WeasyPrint、Pango、フォント、pypdfium2 を検査
make check         # ruff と pytest を実行
make smoke         # 動作確認用の PDF と PNG を scratch/smoke/ に生成
```

### macOS での注意

Homebrew の動的ライブラリは、dyld の既定の検索パスに含まれていません。そのため、
`uv run` を直接実行すると WeasyPrint のインポートに失敗する場合があります。

`make` を経由すると、`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が自動的に設定されます。
コマンドを直接実行する場合は、次のように環境変数を指定してください。

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run yakkan doctor
```

詳しくは `docs/gotchas.md` を参照してください。

## 基本的な使い方

```bash
make help

# 執筆用のスケルトンを作成
uv run yakkan scaffold --genre auto --content-id auto-0004 --seed 4

# 執筆内容を検査
uv run yakkan lint content/auto-0001 --similarity

# 1 文書を生成（build → render → verify）
make doc CONTENT=auto-0001 STYLE=nl-a4-2col-mincho

# バッチ生成（lint → build → render → verify → qa）
make batch SPEC=specs/batch_v1.yaml
```

個別の処理は、次のコマンドでも実行できます。

```bash
uv run yakkan doctor
uv run yakkan build content/auto-0001
uv run yakkan render content/auto-0001 --style <id> --report
uv run yakkan verify dataset/<doc_id>
uv run yakkan qa dataset/<doc_id> --validate --report
uv run yakkan manifest update
uv run yakkan datacard update
uv run yakkan export
uv run yakkan schema export
uv run yakkan clean --stale
```

描画結果は `dataset/<doc_id>/pages/*.png` で確認してください。ページ数や lint に問題がなくても、
レイアウトが崩れている場合があるため、目視確認が必要です。手順は
`.claude/commands/review.md` と `docs/authoring_checklist.md` に記載しています。

## データセットの再生成

`content/`（執筆内容）、`specs/`（バッチ定義）、`dataset/`（生成物）は
このリポジトリでは追跡しません。

データセットを再生成する場合は、`blueprints/` から `scaffold` で執筆用ファイルを作成し、
本文を執筆したうえで、`batch` を実行してください。生成された `dataset/` を
手作業で変更しないでください。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `CLAUDE.md` | プロジェクト憲章：必須ルール、設計原則、lint、マイルストーン |
| `docs/` | スキーマ、描画、執筆、評価などの詳細仕様と運用記録 |
| `yakkan/` | モデル、番号付け、描画、レイアウト抽出、検証、QA、CLI を含む Python パッケージ |
| `blueprints/`、`styles/`、`library/` | ジャンル定義、スタイル、条文ライブラリ |
| `content/<content_id>/` | 執筆内容。追跡対象外 |
| `specs/batch_*.yaml` | コンテンツ、スタイル、seed を指定するバッチ定義。追跡対象外 |
| `dataset/<doc_id>/` | 生成物。追跡対象外かつ手作業での変更は禁止 |
| `assets/fonts/` | 同梱フォント。出典は `assets/fonts/SOURCES.md` |
| `insurance-contracts-calculation/` | 計算・判定条項と正解プログラムを生成する独立した拡張プロジェクト |

配置規則の正本は `docs/repo_layout.md` です。新しいファイルを追加する前に確認してください。

## 生成物

`dataset/<doc_id>/` が 1 文書分の生成物です。`doc_id` は
`<content_id>--<style_id>` の形式です。同じ内容を別のレイアウトで描画した文書は、
`content_id` が同じで `style_id` が異なります。

| ファイル | 内容 |
|---|---|
| `doc.pdf` | フォント埋め込み済み、テキスト層あり、タグなしの PDF |
| `pages/page-NNN.png` | 150 dpi のページ画像 |
| `source.json` | 内容と意味を保持する、レイアウト非依存の正解データ |
| `layout.json` | ページや要素ごとの bbox、読み順、ヘッダ、フッタ |
| `answer.json` | ページ別の期待テキストとアウトライン |
| `elements.jsonl` | 1 行 1 要素の平坦な索引。評価スクリプトで最初に利用するファイル |
| `passages.jsonl` | 検索評価用に `elements.jsonl` をまとめたパッセージ |
| `qa.json` | 自動生成 30 問と執筆 QA 15 問 |
| `render.html` | デバッグ用の中間 HTML。配布対象外 |

`answer.json` は `source.json` と `layout.json` の内容を重複して保持しません。
3 ファイルをまとめて読み込む場合は、`yakkan.answer.load_answer(dir)` を使用してください。

`dataset/` 直下には、データセット全体の情報を格納します。

| パス | 内容 |
|---|---|
| `manifest.json` | 全文書の一覧、統計値、状態、`dataset_version` |
| `data-card.md` | 規模、内訳、正解データ、検証結果、制限、偏りをまとめたデータカード |
| `README.md` | Hugging Face 用のデータセットカード |
| `LICENSE` | CC BY 4.0 と帰属表示、埋め込みフォントの取り扱い |
| `.gitattributes` | PDF と PNG を Git LFS で追跡するための設定 |
| `qa.jsonl` | 全文書の QA を 1 行 1 問にしたファイル |
| `documents.jsonl` | `manifest.json` を 1 行 1 文書にしたファイル |
| `search/` | passages、queries、qrels、id_map を含む検索評価セット |

これらのファイルは手作業で変更せず、`export`、`manifest update`、
`datacard update` で再生成してください。

## 正解データを扱う際の注意

### 座標系

- bbox の単位は PDF ポイント（pt）です。
- 原点はページの左上で、y 軸は下向きです。
- PNG 座標に変換する場合は `dpi / 72` 倍します。同梱 PNG は 150 dpi のため、倍率は約 2.083 です。
- ページの幅と高さは `layout.page_size_pt` に格納されています。

### 繰り返し表頭とヘッダ・フッタ

PDF のテキスト層には、正解データ上の 1 件に対して同じ文字列が複数回現れる場合があります。

- 表がページや段をまたぐと、表頭が繰り返し表示されます。繰り返された断片は
  `layout.elements[cell_id].fragments[].repeated` が `true` になります。
- ヘッダとフッタは `layout.pages[].header` と `.footer` に保持し、`reading_order` には含めません。
- `answer.pages[].text` は、繰り返し表頭を最初の 1 回だけ含み、ヘッダとフッタを含みません。
  これらを含む文字列が必要な場合は `text_with_furniture` を使用してください。

ページ別の CER は、PDF から単純に抽出した文字列ではなく、`answer.pages[].text` と比較してください。

### QA

QA の `type` は、`locate`、`extract`、`definition`、`table_lookup`、
`table_reason`、`figure_path`、`figure_fact`、`crossref`、`count`、
`negative`、`apply` の 11 種類です。

- `apply` は、場面に規定を当てはめて値を導く形式で、執筆 QA にのみ含まれます。
- `source` は `auto` または `authored` です。
- `evidence` は `layout.elements` に存在する要素 ID で、bbox を取得できます。
- `answer_type` は `string`、`number`、`list` のいずれかです。

### データ分割

同じ `content_id` を持つ文書は、内容が同じでレイアウトだけが異なります。
学習用データと評価用データに分割する場合は、同じ文章が両方に含まれないよう、
`doc_id` ではなく `content_id` を基準にしてください。

### その他

- 同じ `content_id`、`style_id`、依存バージョンからは、同じ JSON と
  同じテキスト層を持つ PDF を生成します。
- 20 ページを超えた文書は生成失敗となり、データセットには含まれません。
- 図中の文字は PDF のテキスト層には含まれますが、`layout.pages[].text_lines` には含まれません。
  図の正解は `source` の diagram と `layout.figures[].nodes` を参照してください。
- v1 は縦書き、ルビ、スキャン風の劣化画像を対象としていません。

## 評価

```bash
# 文書読み取りを評価（--oracle で評価系自体を検証）
uv run yakkan eval dataset/<doc_id> --pred pred.json

# 検索を評価
uv run yakkan eval --search-run run.json
```

- **文書読み取り**：ページ別 CER、outline F1、構造位置 citation、表 TEDS、
  セル F1、図のノード・辺・経路 F1、読み順 Kendall τ、QA 一致
- **検索・RAG**：nDCG@k、Recall@k、`exact_recall@k`、`r_precision`、MRR、
  `doc@1`、`confusion@k`、`false_positive_rate`

予測 JSON の形式は `schema/prediction.schema.json`、検索結果の形式は
`schema/search_run.schema.json`、語彙と採点方法は `docs/evaluation.md` を参照してください。

検索クエリは `term`、`heading`、`scoped`、`filtered`、`enumeration`、`qa`、
`definition_masked`、`multi_hop`、`situational`、`no_answer` の 10 種類です。
設計の経緯は `docs/search_query_design.md`、実測結果は `docs/search_query_plan.md` に記載しています。

## 利用上の注意

- 会社名、商品名、人物名、連絡先、URL、様式番号はすべて架空です。
- URL には `example.jp` 系のドメインを、電話番号にはゼロ埋めした番号を使用しています。
- 実在する保険約款は構造やレイアウトのみを参考にし、文章は転載していません。
- 生成物は文書読み取りの検証用データであり、実在の保険会社や商品とは関係ありません。

## ライセンス

- **コード、仕様、執筆内容**：ルートディレクトリの [`LICENSE`](../LICENSE) に記載された MIT License
- **同梱フォント**：SIL Open Font License または IPA フォントライセンス
- **生成データセット**：CC BY 4.0（2026-10-05 決定）

生成データセットは Hugging Face Datasets で公開しています（public）。

- 文書本体：[`cvusk/japanese-insurance-document-understanding`](https://huggingface.co/datasets/cvusk/japanese-insurance-document-understanding)
- 検索評価セット：[`cvusk/japanese-insurance-document-understanding-retrieval`](https://huggingface.co/datasets/cvusk/japanese-insurance-document-understanding-retrieval)

詳しい配布手順は `docs/distribution.md` を参照してください。

### AI モデルの学習・蒸留について

**生成物を、LLM、VLM、その他の AI モデルの学習、ファインチューニング、蒸留、
強化学習に利用することはできません。**

本文、QA、図の説明は、Claude Code のセッション内で Claude（Anthropic）が生成した出力です。
Anthropic の Usage Policy では、入力と出力を AI モデルの学習に使用すること
（model scraping、model distillation を含む）が、事前の許可なく禁止されています
（<https://www.anthropic.com/legal/aup>）。

一方、文書読み取り、検索、AI エージェントの評価やベンチマークには利用できます。
上記の制限が適用されるのは、モデルの重みを更新する用途です。

これは CC BY 4.0 の条件ではなく、Anthropic の Usage Policy に基づく告知です。
詳しくは `dataset/LICENSE`、`dataset/README.md`、`docs/distribution.md` §7 を参照してください。
