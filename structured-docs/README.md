# structured-docs (docsynth) — 構造化ドキュメントの合成データ生成基盤

契約書・Webサービス利用規約・社内規程・法令・保険約款などの「本物そっくりだが**完全に架空**」の
日本語文書（PDF）と、その**完全な正解データ**（JSON）を対で生成する。
ドキュメント読み取りシステム（OCR / レイアウト解析 / VLM / 構造化抽出）と検索エンジンの開発検証用。

- 正解 JSON が唯一の真実で、PDF はその決定論的な描画結果（JSON → HTML → PDF）。
- コア（`docsynth/`）はドメイン非依存。ドメイン知識は**ファミリー**（`families/`）としてプラグイン化。
  v1 ファミリー：`contract`（契約書・10 doctype）`terms`（利用規約等）`regulations`（社内規程）
  `statute`（法令）`insurance`（保険約款・同等性検証用）。
- 2 つの先行プロジェクトの汎用化である。**実証済みの設計・実測結果・評価ハーネスは再検証せず継承**し、
  同等性テストで整合を守る。
- 仕様は `CLAUDE.md`（憲章）と `docs/`（詳細）。**実装と食い違ったら仕様側を先に直す。**

## 先行プロジェクト（姉妹。いずれも `../` にあり、ここからは書き換えない）

| | [`../insurance-contracts/`](../insurance-contracts/) | [`../contracts/`](../contracts/) |
|---|---|---|
| 通称 | yakkan-synth（保険約款） | keiyaku-synth（契約書） |
| 進捗 | 完済（`dataset_version: v7`） | データセット v1 完成（2026-10-05） |
| 規模 | 10 genre・100 content・114 文書・1,458 ページ・QA 5,085 | 10 doctype・50 content・100 文書・657 ページ・QA 4,500 |
| 本プロジェクトへの供給 | **基底仕様**（スキーマ・描画規約・評価ハーネス・検索評価セット・データカード・配布手順） | **コード供給元の第一候補**。`family`+`doctype`・宣言的 numbering 3 方式・`{party:}`・`head_matter`・逐条解説・lint L19–L26・verify V01–V11 を**実装済み** |

keiyaku-synth は「将来 docsynth の `families/contract/` として切り出せる形を保つ」という方針で作られており、
本プロジェクトの P0〜P1（移植とコア汎用化）の半分が契約書ドメインで先に済んでいる。
どちらを基盤に P0 を始めるかは**人間の判断待ち**で、既定は keiyaku ベース。

## 状態

**仕様策定済み・実装は P0 から。** 2026-10-05 に姉妹 2 本の到達点（keiyaku の 100 文書と lint L19–L26、
yakkan の v7・検索クエリ 10 種・データカード・配布）へ仕様を追随させた。
現在地は `docs/progress.md`、フェーズ別の詳細タスクは `docs/plan.md`。

## ドキュメント

| ファイル | 中身 |
|---|---|
| `CLAUDE.md` | 憲章：ハードルール・設計原則・ファミリー一覧・lint（L00–L26）・マイルストーン P0–P9 |
| `docs/architecture.md` | コア／ファミリーの境界、姉妹からの移植方針・棚卸し表 |
| `docs/schema.md` | 正解 JSON のデータモデル（基底仕様への差分＋姉妹が実証した拡張一覧＋statute 差分） |
| `docs/families.md` | ファミリー定義仕様と contract / terms / regulations / statute / insurance のカタログ |
| `docs/rendering.md` | レンダリングと検証（WeasyPrint、確定済み描画規約、verify V01–V11） |
| `docs/evaluation.md` | 評価設計（成果物・読み取り 13 指標・検索 8 指標・クエリ 10 種・予測語彙・合格条件） |
| `docs/data_card.md` | データカード（`dataset/data-card.md`）の仕様と自動更新 |
| `docs/validation_plan.md` | 検証・硬化計画（V-A〜V-F：oracle → misread → 規則ベース → VLM → 盲検 → HITL） |
| `docs/plan.md` | 実行計画とタスク分解（WBS） |
| `docs/lint_rules.md` | lint 各規則の実装位置と検査ロジック |
| `docs/style_guide.md` | 執筆ガイド（架空化・転載の指紋・文体・QA） |
| `docs/authoring_checklist.md` | **lint が通っても残る欠陥**の一覧（執筆前に必読） |
| `docs/reference_structures.md` | 実在文書の構造分析の進め方（転載禁止）・課題カタログ G1–G13 |
| `docs/distribution.md` | 生成物の配布とライセンス表示（判断と実行は人間） |
| `docs/repo_layout.md` | ディレクトリ構成 |
| `docs/decisions.md` `progress.md` `gotchas.md` | 運用ログ |

## セットアップ（P0 完了後に有効）

必要なもの：Python 3.12、[uv](https://docs.astral.sh/uv/)、Pango（`brew install pango` / `apt install libpango-1.0-0 …`）。

```bash
uv sync
make doctor        # 環境検査
make check         # ruff + pytest + manifest 鮮度 + データカード鮮度
```

macOS では `make` 経由で `DYLD_FALLBACK_LIBRARY_PATH` が自動で付く（詳細は `docs/gotchas.md`）。

## ライセンスと架空性

生成される文書の会社名・サービス名・法令題名・自治体名・人物名・住所・連絡先はすべて架空。
参考にした実在文書は**構造のみ**で、文章は一切引用していない。各文書末尾に架空である旨を明記する。
**生成物は読み取り検証用のダミーであり、法的に有効な文書ではない。実務に使わないこと。**

生成物（`dataset/`）の配布条件は**未決**（人間の判断待ち）。
先行例として yakkan-synth と keiyaku-synth はいずれも Hugging Face Datasets・**CC BY 4.0** で配っている。
手順と注意点は `docs/distribution.md`。同梱フォントは SIL Open Font License 1.1（Noto 系）と
IPA フォントライセンス v1.0（IPAex 系）で、いずれも再配布と埋め込みが認められている。

**生成物を LLM・VLM・その他 AI モデルの学習・ファインチューニング・蒸留に使ってはならない。**
本文・表・図の説明・QA は Claude Code セッション内で Claude（Anthropic）が書いた Output であり、
Anthropic の Usage Policy が「入力と出力を AI モデルの学習（model scraping・model distillation を含む）に
用いること」を**事前許可なしに禁じている**（<https://www.anthropic.com/legal/aup>）。
**この制約は配布ライセンスの選択と独立**で、どれを選んでも消えない。
一方、**読み取り・検索・AI エージェントの評価とベンチマークはこのデータの目的そのもの**で、
上の制限は一切かからない（除かれるのはモデルの重みを更新する用途だけ）。詳細は `docs/distribution.md` §6。
