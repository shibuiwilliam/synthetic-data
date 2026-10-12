# contracts-calculation — 契約書の計算・判定条項生成

ビジネス契約書の合成データ生成基盤 [`contracts`](../)（keiyaku-synth。以下「本体」）を
拡張するプロジェクトです。

既存の契約書 JSON に**計算・判定条項**（本文、頭書、別紙の表、図）を追加するか、
既存条項に計算仕様を関連付け、その内容に対応する**正解プログラム**（Python）と
**評価用テストデータ**を生成します。

契約書から計算や判定を必要とする条項を見つけ、実装し、テストするシステムの評価に利用できます。
文書読み取り自体の評価データとしても使用できます。

## 特長

- **計算仕様（CalcSpec）を唯一の情報源（Single Source of Truth）**とします。
- 契約書の文言、正解プログラム、テストの期待値を同じ仕様から生成します。
- 参照インタプリタと生成した Python の結果が、すべてのテストケースで一致することを検査します。
- 追加モードと付与モードの 2 種類を提供します。
- 同じ基準契約書、seed、プロファイルからは、同じ内容を決定論的に生成します。

```text
計算仕様 ──┬─▶ 契約書 JSON への追加・関連付け ─▶ 本体で索引を再計算し、PDF を生成
（唯一の正）├─▶ 正解プログラム（Python）
           ├─▶ テストケース（入力と期待値）と pytest
           └─▶ 正解表（ルールと根拠となる文書要素の対応）
```

プロジェクトの規則は [`CLAUDE.md`](CLAUDE.md) にまとめています。

## 現在の状態

開発フェーズ M0〜M6 は完了し、現在は運用段階です。計算・判定パターンは
K01〜K31 の 31 種類です。

生成物には、次の 2 系統があります。

- **v1**：`data/<profile>/<content_id>/` に配置する、4 プロファイル × 20 基準契約のデータ
- **Hugging Face 公開用**：`dataset/` に配置する 100 文書のデータ

公開用データセットは、`standard`、`hard`、`basic`、`challenge` の各プロファイルと、
`calc_seed` 1〜6 を組み合わせています。

規模、内訳、品質保証、制限、偏りについては、各出力先の `data-card.md` を確認してください。
データカードと説明書は実測値から生成され、生成物の追加に応じて更新されます。

## 前提条件

このプロジェクトは**単体では動作しません**。`contracts/` の直下に配置し、
本体の環境とコンテンツを利用します。

- 基準となる契約書を `../content/<content_id>/` から読み込みます。本体のファイルは変更しません。
- lint、索引の再計算、PDF 描画には、本体の `keiyaku` CLI を使用します。
- Python 環境には本体の uv プロジェクトを使用します（`uv run --project ..`）。

生成器自体の実行時依存は Python の標準ライブラリだけです。WeasyPrint などの依存関係が必要になるのは、
本体を呼び出して PDF を生成するときだけです。本体への呼び出しは `base_adapter.py` に集約しています。

## セットアップ

先に本体の [`README.md`](../README.md) に従って、`uv sync` と Pango の導入を完了してください。

```bash
cd contracts/contracts-calculation

# 生成器のテスト
uv run --project .. python -m pytest -q

# 静的解析
uv run --project .. ruff check src tests scripts
```

macOS で本体の描画コマンドを直接実行する場合は、
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が必要です。
`base_adapter.py` から実行する場合は自動的に設定されます。

## 使い方

コンソールスクリプトは登録していません。
`python -m contracts_calculation.cli`（表示名 `contracts-calc`）として実行します。

```bash
cd contracts/contracts-calculation
export PYTHONPATH=src

# 追加モード：基準契約書に計算条項を追加
uv run --project .. python -m contracts_calculation.cli generate \
    --base ../content/ots-0001 --calc-seed 1 --profile standard --out data --png
uv run --project .. python -m contracts_calculation.cli generate \
    --all-bases --calc-seed 1 --profile standard --out data/standard

# 付与モード：既存の計算条項に仕様を関連付ける
uv run --project .. python -m contracts_calculation.cli bind \
    --all-bases --out data_bind --no-render

# 生成物を検証
uv run --project .. python -m contracts_calculation.cli verify data/ots-0101

# 正解プログラムを提出結果として評価し、満点になることを確認
uv run --project .. python -m contracts_calculation.cli eval --data data --oracle

# 基準契約書の計算条項を検査
uv run --project .. python -m contracts_calculation.cli lint-base
```

プロファイルは難易度ごとの出現割合を定義し、`basic`、`standard`、`hard`、
`challenge` の 4 種類があります。`challenge` には、意図的な欠落や例外的な条件を含めます。
詳しくは `config.py` を参照してください。

### データカードを生成・検査する

```bash
# 説明書とデータカードを実測値から生成
uv run --project .. python -m contracts_calculation.cli datasheet --data dataset

# データカードの鮮度を検査
uv run --project .. python -m contracts_calculation.cli datacard check --data dataset

# 別の計測経路で独立検算
uv run --project .. python scripts/verify_data_card.py --data dataset
```

### Hugging Face 向けの公開形式を作成する

```bash
uv run --project .. python -m contracts_calculation.cli \
    publish --data dataset --out dist/hf
```

このコマンドは公開用ファイルを組み立てるだけで、アップロードは行いません。

**`dataset/` をそのままアップロードしないでください。** `_render/*/render.html` には
ローカルの絶対パスや実行ユーザー名が含まれ、中間生成物や重複ファイルもあります。
`publish` は許可リスト方式で公開対象を選び、公開前ゲート P1〜P6 によって、
絶対パス、副産物、実在名称、データカードなどを検査します。

詳しい仕様は `docs/hf_publish.md` を参照してください。

## 生成物

```text
<out>/
├── README.md                  # 実測値から生成するデータセット説明書
├── data-card.md               # 実測値から生成するデータカード
├── oracle_report.json         # 正解プログラムを使った評価結果
└── <content_id>/              # 1 文書分の計算パック
    ├── contract.json          # 計算条項を追加した契約書
    ├── <content_id>--<style_id>.pdf
    ├── _render/               # source.json、layout.json、render.html、doc.pdf
    └── calc/
        ├── spec.json          # 計算仕様。唯一の情報源
        ├── patch.json         # 基準契約書に対する変更内容
        ├── answer_key.json    # ルール、根拠、表現方法、難易度の対応
        ├── manifest.json      # 生成条件、パターン、ゲート結果、ハッシュ
        ├── calendar.json      # 使用する祝日の固定データ
        ├── cases.jsonl        # 入力と期待値
        ├── tasks.jsonl        # 評価対象システムへのタスク
        ├── programs/calc_<cid>.py
        └── tests/             # 提出実装へ差し替え可能な pytest
```

## 検証

すべての必須ゲートを通過した文書だけを出力します。

| ゲート | 検査内容 |
|---|---|
| G1〜G2 | 仕様のスキーマ、型、単位を検査し、仕様の引用が契約書に存在することを確認 |
| G3〜G4 | 必要な説明文が存在し、本文、頭書、別紙から読み取った値が仕様と一致することを確認 |
| G5〜G6 | 契約書内の計算例、参照インタプリタ、正解プログラムの結果が一致することを確認 |
| G7〜G8 | テストがすべての変異を検出し、日付規則に暦の境界ケースが含まれることを確認 |
| G9〜G10 | 既存の条項、定数、定義語、別紙番号と衝突せず、本体の lint、索引再計算、描画が成功することを確認 |
| G11〜G12 | 根拠となる文書要素を発見でき、同じ seed で再生成したハッシュが一致することを確認 |
| G13 | 基準システムが H2 のヒントで合格することを確認する任意ゲート。2026-10-04 に導入を見送り |

意味論の正本は `spec/interp.py` の参照インタプリタです。G6 と `eval --oracle` が、
生成した Python と参照インタプリタの一致を全テストケースで確認します。

## ディレクトリ構成

| パス | 内容 |
|---|---|
| `src/contracts_calculation/` | 生成器本体 |
| `packs/` | パラメータ候補、入力概念の語彙、祝日の固定データ |
| `tests/` | 生成器のテスト |
| `examples/` | 回帰基準となる 3 文書 |
| `docs/` | 調査、レビュー、設計判断の記録 |
| `scripts/` | 祝日データ、回帰基準、データカードの管理スクリプト |

`data/`、`data_bind/`、`dataset/` は生成物のため、このリポジトリでは追跡しません。

## ドキュメント

| ファイル | 内容 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | プロジェクト憲章と運用規則 |
| [`docs/hf_publish.md`](docs/hf_publish.md) | Hugging Face 向け公開形式と公開前ゲート |
| [`docs/data_card.md`](docs/data_card.md) | データカードの生成仕様 |
| [`docs/README.md`](docs/README.md) | 調査、レビュー、設計判断の記録への索引 |

実装と文書に相違がある場合は、先に文書を更新してください。

## 利用上の注意

- 会社名、人物名、金額、日付などはすべて架空です。
- 実在するひな型の文章は転載していません。
- 生成物は文書読み取りの検証用データです。法的に有効な契約書ではなく、実務には利用できません。
- 税率、法定利率、祝日は法令の実装ではありません。契約書内の値または外部入力として扱います。
- 祝日は 2026〜2033 年の固定データ（`packs/calendar/holidays_jp.json`）を使用します。
- 生成処理中に LLM や外部サービスを呼び出しません。

## ライセンス

コード（`src/`、`scripts/`、`tests/`）には、ルートディレクトリの
[`LICENSE`](../../LICENSE) に記載された MIT License が適用されます。

生成物の配布条件は **CC BY 4.0**（2026-10-12 決定）です。Hugging Face Datasets で
公開しています（public）。

- [`cvusk/japanese-contract-document-understanding-calculation`](https://huggingface.co/datasets/cvusk/japanese-contract-document-understanding-calculation)

詳しくは `docs/hf_publish.md` を参照してください。

### AI モデルの学習・蒸留について

**生成物を、LLM、VLM、その他の AI モデルの学習、ファインチューニング、蒸留、
強化学習に利用することはできません。**

生成物の本文や QA には、Claude Code のセッション内で Claude（Anthropic）が生成した出力が含まれます。
Anthropic の Usage Policy では、入力と出力を AI モデルの学習に使用すること
（model scraping、model distillation を含む）が、事前の許可なく禁止されています
（<https://www.anthropic.com/legal/aup>）。

一方、文書読み取り、検索、AI エージェントの評価やベンチマークには利用できます。
上記の制限が適用されるのは、モデルの重みを更新する用途です。
