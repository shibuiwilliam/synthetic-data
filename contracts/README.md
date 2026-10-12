# keiyaku-synth — 日本語ビジネス契約書の合成データ生成基盤

**完全に架空でありながら、本物に近い日本語のビジネス契約書**（PDF）と、その内容に対応する
**正解データ**（JSON）を生成するプロジェクトです。

OCR、レイアウト解析、VLM、構造化抽出などの文書読み取りシステムや、
検索・RAG システムの開発・検証を主な用途としています。

## 開発の背景

契約書の読み取りシステムを開発する際、実在する文書には次のような課題があります。

- 実際の契約書には当事者名、金額、取引条件などの機密情報が含まれ、社外に出せません。
- 公開されているひな型は第三者の著作物であり、データセットとして再配布できるとは限りません。
- 文書内の構造、表の意味、参照関係などを示す正解データが付属していません。

このプロジェクトでは、実在する契約書から構造やレイアウトの特徴だけを参考にし、
文章をすべて独自に作成します。**正解 JSON を唯一の情報源（Single Source of Truth）**とし、
PDF を正解 JSON から決定論的に描画するため（JSON → HTML → PDF）、
正解データと紙面の内容が食い違うことは設計上ありません。

先行プロジェクトの [`../insurance-contracts/`](../insurance-contracts/)（yakkan-synth）は、
同じ方式を保険約款で実証しています。本プロジェクトは、その設計と評価方法を
ビジネス契約書向けに拡張したものです。

## 特長

- 秘密保持、業務委託、準委任、コンサルティング、売買、賃貸借、ライセンス、
  システム開発、請負、雇用の 10 文書種別を生成できます。
- 文書種別ごとの構造、必須要素、文体を宣言ファイルで管理します。
- 同じ内容を異なる判型、フォント、罫線、版面で描画できます。
- テキスト、条項構造、表、図、参照関係、QA の 6 観点で正解データを提供します。
- 文書読み取りと検索の評価ハーネスを備えています。

## 現在の状態

**データセット v1 は 2026-10-05 に完成しました。**

| 項目 | 実測値 |
|---|---:|
| 文書種別 | 10 |
| コンテンツ | 50 |
| 文書 | 100 |
| ページ | 657 |
| 表 | 247 |
| 図 | 104 |
| QA | 4,500 問 |

100 文書に対する `eval --all --oracle` は、18 指標すべてで満点です。
全コンテンツが類似度検査を含む lint で error 0 / warn 0、全文書が verify と QA の検査で
error 0 となっています。規則ベースの読み取り、VLM、開発経緯を知らないエージェントによる
盲検評価も実施済みです。

詳しい検証内容は `docs/validation_plan.md`、進捗の経緯は `docs/progress.md` を参照してください。
`dataset/` は生成物のため、このリポジトリでは追跡していません。

## セットアップ

必要な環境は Python 3.12、[uv](https://docs.astral.sh/uv/)、Pango です。

```bash
# macOS
brew install pango

# Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev

uv sync            # 依存関係をインストール（make setup と同じ）
make doctor        # Python、WeasyPrint、Pango、フォント、pypdfium2 を検査
make check         # ruff、pytest、manifest とデータカードの鮮度を検査
make smoke         # 動作確認用の PDF と PNG を scratch/smoke/ に生成
```

### macOS での注意

Homebrew の動的ライブラリは、dyld の既定の検索パスに含まれていません。そのため、
`uv run` を直接実行すると WeasyPrint のインポートに失敗する場合があります。

`make` を経由すると、`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が自動的に設定されます。
詳しくは `docs/gotchas.md` を参照してください。

## 1 文書を生成する

```bash
# 執筆用のスケルトンを作成
uv run keiyaku scaffold --doctype nda --content-id nda-0001 --seed 42

# content/nda-0001/parts/*.json に本文を記述

# lint → build → render → verify → qa を実行
make doc CONTENT=nda-0001 STYLE=ct-a4-1col-mincho

# 全ページの PNG を目視確認
uv run keiyaku review dataset/nda-0001--ct-a4-1col-mincho
```

レイアウトの崩れは自動検査だけでは検出できない場合があるため、ページ画像の目視確認は必須です。

## データセットを再生成する

`content/`（執筆内容）、`specs/`（バッチ定義）、`dataset/`（生成物）は
このリポジトリでは追跡しません。追跡対象は、`blueprints/`、`numbering/`、`styles/`、
`library/` などの宣言と、`keiyaku/` の実装です。

データセットを再生成するには、利用者が `content/` と `specs/` を用意する必要があります。

```bash
# 1. スケルトンを作成し、本文を執筆
uv run keiyaku scaffold --doctype nda --content-id nda-0001 --seed 42
uv run keiyaku lint content/nda-0001

# 2. specs/*.yaml にバッチ定義を作成し、一括生成
uv run keiyaku batch specs/my_batch.yaml
uv run keiyaku manifest update
uv run keiyaku manifest check
uv run keiyaku export
uv run keiyaku eval --all --oracle
```

執筆手順は `CLAUDE.md` §7 を参照してください。

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
| `qa.json` | 自動生成 30 問と執筆 QA 15 問 |
| `render.html` | デバッグ用の中間 HTML。配布対象外 |

`answer.json` は `source.json` と `layout.json` の内容を重複して保持しません。
3 ファイルをまとめて読み込む場合は、`keiyaku.answer.load_answer(dir)` を使用してください。

`dataset/` 直下には、次のデータセット全体のファイルがあります。

- `manifest.json`：全文書の一覧
- `README.md`：Hugging Face 用のデータセットカード
- `data-card.md`：規模、作成方法、品質保証、制限、偏りをまとめたデータカード
- `views/*.jsonl`：Dataset Viewer と `load_dataset()` 向けの平坦なデータ
- `search/`：passages、queries、qrels を含む検索評価セット

これらは `keiyaku export` が実測値から生成します。手作業で変更しないでください。
正解 JSON の各フィールドは `docs/schema.md`、予測形式と採点方法は
`docs/evaluation.md` を参照してください。

## 評価

`keiyaku eval` では、文書読み取りと検索・RAG を評価できます。
`--oracle` を使用すると満点の予測を生成できるため、評価処理自体の検証にも利用できます。

評価対象には、テキスト、アウトライン、構造位置、表、図、読み順、QA、検索順位などが含まれます。
詳しい指標と予測 JSON の形式は `docs/evaluation.md` を参照してください。

## Hugging Face Hub 向けの公開形式

`keiyaku export` または `keiyaku publish update` を実行すると、`dataset/` を
Hugging Face のデータセットリポジトリとして公開できる形式に整えます。

文書本体と検索評価セットは、別々のデータセットとして公開します。

- 文書本体：`dataset/`
- 検索評価セット：`dataset/search/`

検索評価セットを分離することで、検索だけを利用する場合に PDF や PNG を取得する必要がなくなります。
`passage_id` は `<doc_id>::<element_id>` の形式で、文書本体と対応付けられます。

```bash
uv run keiyaku publish check
uv run python scripts/verify_views.py
uv run python scripts/upload_hf.py
uv run python scripts/upload_hf.py --only search
```

`scripts/upload_hf.py` は、既定ではアップロードせず、対象ファイルの数だけを確認します。
公開先、名義、除外設定は `specs/publish.yaml` で管理します。詳しくは
`docs/publishing.md` を参照してください。

## ディレクトリ構成とドキュメント

| ファイル | 内容 |
|---|---|
| `CLAUDE.md` | プロジェクト憲章：必須ルール、設計原則、文書種別、lint、マイルストーン |
| `docs/architecture.md` | yakkan-synth からの移植方針とコア・宣言の境界 |
| `docs/schema.md` | 正解 JSON のデータモデル |
| `docs/doctypes.md` | 10 文書種別、番号体系、スタイルの仕様 |
| `docs/rendering.md` | WeasyPrint を使った描画と検証 |
| `docs/style_guide.md` | 架空化、転載防止、文体、密度、QA の執筆ガイド |
| `docs/authoring_checklist.md` | lint だけでは検出できない欠陥の確認項目 |
| `docs/reference_structures.md` | 参考文書の構造分析方法と課題カタログ |
| `docs/evaluation.md` | 評価対象、指標、予測形式、合格条件 |
| `docs/data_card.md` | `dataset/data-card.md` の生成仕様 |
| `docs/publishing.md` | Hugging Face Hub 向けの公開仕様と手順 |
| `docs/validation_plan.md` | 評価・検証・品質強化の計画 |
| `docs/plan.md` | 実行計画と作業分解（WBS） |
| `docs/lint_rules.md` | lint の各規則と検査ロジック |
| `docs/repo_layout.md` | ディレクトリ構成と運用規則 |
| `docs/decisions.md`、`docs/progress.md`、`docs/gotchas.md` | 設計変更、進捗、環境固有の注意事項 |

## 参考文書の取り扱い

`samples/` には、構造分析に使用する 10 カテゴリ、36 種類の参考文書があります。
出典は `samples/SOURCES.md` に記録しています。

参考文書は第三者の著作物です。見出し階層、条文構成、別紙の有無、表の形式など、
構造やレイアウトのみを参考にし、文章は生成物へ転載しません。PDF 本体は
`.gitignore` で除外し、リポジトリにはコミットしません。

詳しい運用規則は `docs/reference_structures.md` §0 を参照してください。

## 利用上の注意

- 会社名、屋号、人物名、住所、連絡先、契約書番号、物件名はすべて架空です。
- これらの固有名詞は、可能な限り実在しないものを選ぶよう努めています。万が一、実在する
  名称・住所等と偶然一致していることが判明した場合は、該当箇所を修正します。
- 各文書の末尾には、架空の文書であることを明記します。
- 生成物は文書読み取りの検証用データです。法的に有効な契約書ではなく、実務には利用できません。

## ライセンス

- **コード**：`pyproject.toml` の `Proprietary` と、ルートディレクトリの
  [`LICENSE`](../LICENSE) に記載された MIT License が一致していません。公開前に統一する必要があります。
- **同梱フォント**：SIL Open Font License 1.1 または IPA フォントライセンス v1.0
- **生成データセット**：CC BY 4.0（2026-10-06 決定）

生成データセットは Hugging Face Datasets で公開しています（public）。

- 文書本体：[`cvusk/japanese-contract-document-understanding`](https://huggingface.co/datasets/cvusk/japanese-contract-document-understanding)
- 検索評価セット：[`cvusk/japanese-contract-document-understanding-retrieval`](https://huggingface.co/datasets/cvusk/japanese-contract-document-understanding-retrieval)

ライセンス宣言の正本は `specs/publish.yaml` の `license.id` です。

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
詳しくは `dataset/LICENSE`、`dataset/README.md`、`docs/publishing.md` §10 を参照してください。
