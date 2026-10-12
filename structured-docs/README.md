# structured-docs（docsynth）— 構造化文書の合成データ生成基盤

契約書、Web サービスの利用規約、社内規程、法令、保険約款などを対象に、
**完全に架空でありながら、本物に近い日本語文書**（PDF）と、その内容に対応する
**正解データ**（JSON）を生成するための汎用基盤です。

OCR、レイアウト解析、VLM、構造化抽出などの文書読み取りシステムや、
検索エンジンの開発・検証を主な用途としています。

## 特長

- **正解 JSON を唯一の情報源（Single Source of Truth）**とし、PDF は正解 JSON から
  決定論的に描画します（JSON → HTML → PDF）。
- コア（`docsynth/`）はドメインに依存しません。契約書や保険約款などのドメイン知識は、
  **ファミリー**（`families/`）としてプラグイン化します。
- v1 では、`contract`（契約書）、`terms`（利用規約など）、`regulations`（社内規程）、
  `statute`（法令）、`insurance`（保険約款）の 5 ファミリーを対象とします。
- 先行する 2 つのプロジェクトで実証済みの設計、実測結果、評価ハーネスを継承し、
  同等性テストによって互換性を維持します。

仕様は `CLAUDE.md`（プロジェクト憲章）と `docs/`（詳細仕様）にまとめています。
実装と仕様に相違がある場合は、先に仕様を更新してください。

## 先行プロジェクト

先行プロジェクトは、いずれもこのディレクトリの 1 階層上にあります。
このプロジェクトから直接変更しないでください。

| 項目 | [`../insurance-contracts/`](../insurance-contracts/) | [`../contracts/`](../contracts/) |
|---|---|---|
| 通称 | yakkan-synth | keiyaku-synth |
| 対象 | 保険約款 | ビジネス契約書 |
| 状態 | 完成（`dataset_version: v7`） | データセット v1 完成（2026-10-05） |
| 文書 | 113 文書、1,437 ページ | 100 文書、657 ページ |
| 構成 | 10 ジャンル、100 コンテンツ | 10 文書種別、50 コンテンツ |
| QA | 5,085 問 | 4,500 問 |
| 本プロジェクトでの位置づけ | 基底仕様 | コード移植元の第一候補 |

yakkan-synth からは、スキーマ、描画規約、評価ハーネス、検索評価セット、
データカード、配布手順を継承します。keiyaku-synth では、複数の文書種別、
宣言的な番号体系、当事者参照、各種の検証機能が実装済みです。

keiyaku-synth は、将来 `docsynth` の `families/contract/` として切り出せる構成を
意識して開発されています。そのため、P0〜P1 で予定している移植とコアの汎用化の一部は、
契約書ドメインですでに実装済みです。

## 現在の状態

仕様の策定は完了しており、実装は P0 から開始する段階です。どちらの先行プロジェクトを
P0 の基盤にするかは人による判断が必要で、現在は keiyaku-synth を既定の候補としています。

最新の進捗は `docs/progress.md`、フェーズ別の作業内容は `docs/plan.md` を参照してください。

## セットアップ

以下の手順は、P0 完了後に利用できます。

必要な環境は Python 3.12、[uv](https://docs.astral.sh/uv/)、Pango です。

```bash
uv sync
make doctor        # 環境を検査
make check         # ruff、pytest、manifest とデータカードの鮮度を検査
```

macOS では、`make` を経由すると `DYLD_FALLBACK_LIBRARY_PATH` が自動的に設定されます。
詳しくは `docs/gotchas.md` を参照してください。

## ドキュメント

| ファイル | 内容 |
|---|---|
| `CLAUDE.md` | プロジェクト憲章：必須ルール、設計原則、ファミリー一覧、lint、マイルストーン |
| `docs/architecture.md` | コアとファミリーの境界、先行プロジェクトからの移植方針 |
| `docs/schema.md` | 正解 JSON のデータモデル |
| `docs/families.md` | ファミリーの定義仕様と各ファミリーのカタログ |
| `docs/rendering.md` | WeasyPrint を使った描画と検証 |
| `docs/evaluation.md` | 文書読み取りと検索の評価設計 |
| `docs/data_card.md` | `dataset/data-card.md` の生成仕様 |
| `docs/validation_plan.md` | 評価・検証・品質強化の計画 |
| `docs/plan.md` | 実行計画と作業分解（WBS） |
| `docs/lint_rules.md` | lint の各規則と検査ロジック |
| `docs/style_guide.md` | 架空化、転載防止、文体、QA の執筆ガイド |
| `docs/authoring_checklist.md` | lint だけでは検出できない欠陥の確認項目 |
| `docs/reference_structures.md` | 実在文書の構造分析方法と課題カタログ |
| `docs/distribution.md` | 生成物の配布方法とライセンス表示 |
| `docs/repo_layout.md` | ディレクトリ構成 |
| `docs/decisions.md`、`docs/progress.md`、`docs/gotchas.md` | 設計変更、進捗、環境固有の注意事項 |

## 利用上の注意

- 生成する会社名、サービス名、法令名、自治体名、人物名、住所、連絡先はすべて架空です。
- 実在する文書は構造やレイアウトのみを参考にし、文章は転載しません。
- 各文書の末尾には、架空の文書であることを明記します。
- 生成物は文書読み取りの検証用データです。法的に有効な文書ではなく、実務には利用できません。

## ライセンス

生成物（`dataset/`）の配布条件は未決定であり、人による判断を待っている状態です。
先行する yakkan-synth と keiyaku-synth では、生成物に CC BY 4.0 を採用しています。
詳しくは `docs/distribution.md` を参照してください。

同梱フォントには、SIL Open Font License 1.1（Noto 系）または
IPA フォントライセンス v1.0（IPAex 系）が適用されます。

### AI モデルの学習・蒸留について

**生成物を、LLM、VLM、その他の AI モデルの学習、ファインチューニング、蒸留、
強化学習に利用することはできません。**

本文、表、図の説明、QA は、Claude Code のセッション内で Claude（Anthropic）が生成した出力です。
Anthropic の Usage Policy では、入力と出力を AI モデルの学習に使用すること
（model scraping、model distillation を含む）が、事前の許可なく禁止されています
（<https://www.anthropic.com/legal/aup>）。

一方、文書読み取り、検索、AI エージェントの評価やベンチマークには利用できます。
上記の制限が適用されるのは、モデルの重みを更新する用途です。
この制限は配布ライセンスとは独立しています。詳しくは `docs/distribution.md` §6 を参照してください。
