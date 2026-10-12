# insurance-contracts-calculation — 保険約款の計算・判定条項生成

保険約款の合成データ生成基盤 [`insurance-contracts`](..)（yakkan-synth。以下「本体」）を
拡張するプロジェクトです。

既存の約款 JSON に**計算・判定条項**（条、表、算式、図）を追加し、その内容に対応する
**正解プログラム**（Python）と**評価用テストデータ**を、同じ計算仕様から生成します。

## 特長

- **計算仕様（CalcSpec）を唯一の情報源（Single Source of Truth）**とします。
- 約款の文言、正解プログラム、テストの期待値を同じ仕様から生成します。
- 文言とプログラムを別々に作成しないため、両者が構造上食い違いません。
- 検証ゲート G1〜G12 をすべて通過した文書だけを出力します。
- 同じ基準約款、seed、生成器のバージョンからは、同じ内容を決定論的に生成します。

プロジェクトの規則は `CLAUDE.md`、実測結果や公開手順などの詳細は `docs/` にまとめています。

## 対象

次の 8 ジャンルを対象としています。

- `auto`
- `quake`
- `health`
- `oneday`
- `travel`
- `golf`
- `group`
- `life`

`teikan` は計算条項がなく、`jyusetsu` は条を持たないため、対象外です。

## 現在の状態

計算条項、正解プログラム、テストデータの生成と、検証ゲート G1〜G12 を実装済みです。
Hugging Face 向けの公開パッケージも作成できますが、ライセンスは仮設定であり、
公開作業はまだ行っていません。

## 前提条件

このプロジェクトは**単体では動作しません**。本体の `insurance-contracts/` と、
本体が管理する Python 環境が必要です。

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Pango（WeasyPrint が使用）
- 本体の `content/` にある執筆済みの保険約款

## セットアップ

まず、本体の環境を準備してください。

```bash
cd insurance-contracts
uv sync
make doctor
```

macOS で WeasyPrint を使用する場合は、
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が必要です。
詳しくは本体の `docs/gotchas.md` を参照してください。

## 使い方

このプロジェクトは、本体の uv 環境を利用します。本体の `pyproject.toml` は変更しません。

```bash
cd insurance-contracts/insurance-contracts-calculation
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib

# 1 文書を生成
# --base には content/<id>/ または dataset/*/source.json を指定可能
PYTHONPATH=src uv run --project .. \
    python -m insurance_contracts_calculation.cli \
    generate --base ../content/auto-0001 --out out --seed 1

# 生成したテストを正解プログラムで実行（全件合格が期待値）
uv run --project .. python -m pytest out/auto-0001-c1/calc/tests -q

# 意図的に誤らせた実装で実行（不合格の発生が期待値）
uv run --project .. python -m pytest examples/auto-0001-c1/calc/tests \
    --impl examples/wrong_impl.py -q

# 提出プログラムを評価
PYTHONPATH=src uv run --project .. \
    python -m insurance_contracts_calculation.cli \
    eval --submission examples/wrong_impl.py --data examples/auto-0001-c1

# 8 ジャンルを各 5 文書ずつ生成
PYTHONPATH=src uv run --project .. \
    python -m insurance_contracts_calculation.cli \
    batch --genres auto quake health oneday travel golf group life \
          --per-genre 5 --min-slack 1.8 --out out/v1
```

出力先には `out/` または、このプロジェクトの `dataset/` を指定できます。
どちらも Git の追跡対象外です。

本体の `dataset/` への書き込みは禁止しています。本体の `manifest check` が
不整合になるためです。

### データカードを更新する

```bash
PYTHONPATH=src uv run --project .. \
    python -m insurance_contracts_calculation.cli \
    datacard update dataset
```

`dataset/data-card.md` には規模や内訳などの実測値を、`dataset/_run_report.json` には
生成時の記録を出力します。データカードは生成物を追加したときに自動更新され、
`make check` が鮮度を検査します。

### プロジェクトを検査する

- `make check`：ruff、生成器のテスト、データカードの鮮度を検査
- `make test-all`：広い seed 範囲を含めて検査
- `cd .. && make check`：本体に影響がないことを検査

## 生成物

| ファイル | 内容 |
|---|---|
| `policy.json` | 計算条項を追加した約款 JSON。本体が `derived` を再計算 |
| `<doc_id>/doc.pdf` | 本体が描画した PDF |
| `<doc_id>/layout.json` | 本体が生成したレイアウト情報 |
| `<doc_id>/pages/*.png` | 本体が生成したページ画像 |
| `calc/spec.json` | 計算仕様（CalcSpec v0.2）。唯一の情報源 |
| `calc/programs/calc_*.py` | 標準ライブラリだけで動作する正解プログラム |
| `calc/cases.jsonl` | テストケース |
| `calc/tests/` | pytest 形式のテスト |
| `calc/tasks*.jsonl` | ヒント H0、H1、H2 を含む評価用タスク |
| `calc/answer_key.json` | 各ルールと根拠となる文書要素の対応 |
| `calc/manifest.json` | バージョン、seed、ハッシュ、検証結果 |
| `<出力先>/data-card.md` | 規模、内訳、正解データ、検証結果、制限、偏りをまとめたデータカード |

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `src/.../base_adapter.py` | 本体の読み込み、パッチ適用、描画、lint、verify を呼び出す唯一の場所 |
| `src/.../spec/` | CalcSpec v0.2 の型、検査、参照インタプリタ |
| `src/.../patterns/` | 計算パターン P01〜P18 |
| `src/.../planning/` | 文脈の読み取り、パターン選択、配置、表現方法の決定 |
| `src/.../realize/` | 日本語の文型、ノード、ブロック、図、計算例、パッチの生成 |
| `src/.../codegen/` | 正解プログラムの生成 |
| `src/.../testgen/` | 境界値、不明値、変異、タスク、pytest の生成 |
| `src/.../verify/` | 検証ゲート、発見可能性、解答可能性、基準約款の検査 |
| `src/.../evalkit/` | 提出プログラムの隔離実行と評価レポート |
| `src/.../export/` | 出力、公開用パッケージ、データカードの生成 |
| `packs/` | 8 ジャンルの語彙と値域を定義する YAML |
| `tests/` | 回帰、決定性、規則、seed sweep を含む生成器のテスト |
| `scripts/` | 本体の変更検出とデータカードの独立検算 |
| `examples/` | seed 4 の回帰基準と、意図的に誤らせた実装 |

## 運用上の原則

- 計算仕様を唯一の情報源とし、文言、プログラム、期待値を個別に変更しません。
- 生成物を手作業で変更しません。修正はパターン、組み立て処理、コンパイラに対して行います。
- 検証ゲートを無効化しません。失敗した場合は生成側を修正します。
- 会社名、商品名、人物名、連絡先などはすべて架空です。

## 配布

このリポジトリで追跡するのは、生成器（`src/`）と 1 文書分の回帰基準（`examples/`）です。
データセット本体（`out/`、`dataset/`）は追跡せず、`generate` または `batch` で再生成します。
`examples/` にも PDF や PNG は含めず、比較に必要な `policy.json` と `calc/` だけを保存します。

Hugging Face 向けの公開パッケージは、次のコマンドで作成できます。
このコマンドはファイルを組み立てるだけで、push やアップロードは行いません。

```bash
PYTHONPATH=src uv run --project .. \
    python -m insurance_contracts_calculation.cli \
    package dataset --format hf --out dist/hf --version v2.3 \
    --license cc-by-4.0 --repo-id <account>/yakkan-calc
```

ライセンスは `cc-by-4.0` で仮設定しています。公開前に確定してください。
詳しい手順と確認項目は `docs/hf_publication.md` を参照してください。

評価時には、正解プログラムや期待値を評価対象の学習データに混ぜないでください。
公開対象と非公開対象の分離は、エクスポート処理が機械的に行います。

## ライセンス

コードには、ルートディレクトリの [`LICENSE`](../../LICENSE) に記載された MIT License が適用されます。
生成物の配布ライセンスは公開前に確定する必要があります。

### AI モデルの学習・蒸留について

**生成物を、LLM、VLM、その他の AI モデルの学習、ファインチューニング、蒸留、
強化学習に利用することはできません。**

生成物の本文や QA には、Claude Code のセッション内で Claude（Anthropic）が生成した出力が含まれます。
Anthropic の Usage Policy では、入力と出力を AI モデルの学習に使用すること
（model scraping、model distillation を含む）が、事前の許可なく禁止されています
（<https://www.anthropic.com/legal/aup>）。

一方、文書読み取り、検索、AI エージェントの評価やベンチマークには利用できます。
上記の制限が適用されるのは、モデルの重みを更新する用途です。
