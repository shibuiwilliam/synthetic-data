# synthetic-data

日本語文書の読み取り技術（OCR、レイアウト解析、VLM、構造化抽出）や検索エンジンの
開発・検証に利用できる、**完全に架空でありながら、本物に近い日本語文書**を生成する
プロジェクト群をまとめたモノレポです。生成した文書には、内容に対応する**正解データ**が付属します。

このリポジトリは、次の原則に基づいています。

- **正解 JSON を唯一の情報源（Single Source of Truth）** とし、PDF は正解 JSON から
  決定論的に描画します（JSON → HTML → PDF）。そのため、正解データと紙面の内容が
  食い違うことは設計上ありません。
- 会社名、商品名、人物名、連絡先、URL はすべて架空です。URL には `example.jp` 系の
  ドメインを、電話番号にはゼロ埋めした番号を使用しています。実在する文書の文章は転載せず、
  文書の構造や一般的なレイアウトのみを参考にしています。これらの固有名詞は、可能な限り
  実在しないものを選ぶよう努めています。万が一、実在する名称・住所等と偶然一致している
  ことが判明した場合は、該当箇所を修正します。
- テキスト、章・節・項の構造、表、図、参照関係、QA を正解データとして保持し、
  採点用の評価ハーネスも提供します。

## プロジェクト構成

| ディレクトリ | 通称 | 対象文書 | 状態 |
|---|---|---|---|
| [`insurance-contracts/`](insurance-contracts/) | yakkan-synth | 保険約款（自動車、地震、生命、旅行などの 10 ジャンル） | 完成（`dataset_version: v7`）。10 ジャンル、100 コンテンツ、113 文書、1,437 ページ、QA 5,085 問 |
| [`contracts/`](contracts/) | keiyaku-synth | ビジネス契約書（秘密保持、業務委託、売買、雇用などの 10 文書種別） | v1 データセット完成（2026-10-05）。10 文書種別、100 文書 |
| [`structured-docs/`](structured-docs/) | docsynth | 上記 2 プロジェクトを汎用化し、契約書、利用規約、社内規程、法令、保険約款を「ファミリー」として扱う基盤 | 仕様のみ（`docs/`、`CLAUDE.md`）。実装は未着手 |

契約書と保険約款の各プロジェクトには、**計算・判定条項の正解プログラム**を追加する
拡張サブプロジェクトもあります。これらは本体のコミットには含めず、別に管理しています。

| ディレクトリ | 内容 |
|---|---|
| [`contracts/contracts-calculation/`](contracts/contracts-calculation/) | keiyaku-synth の契約書に計算条項を追加し、正解となる Python プログラムとテストケースを同時に生成します。 |
| [`insurance-contracts/insurance-contracts-calculation/`](insurance-contracts/insurance-contracts-calculation/) | yakkan-synth の保険約款に、同様の計算条項を追加します。 |

`structured-docs`（docsynth）は、`insurance-contracts` と `contracts` で実証済みの設計や
評価ハーネスを継承し、ドメイン知識を `families/` としてプラグイン化する汎用基盤の構想です。

## 使い方

各ディレクトリは、それぞれ独立して利用できるプロジェクトです。仕様、規約、コマンドは
各ディレクトリ内にまとめています。**作業を始める前に、対象ディレクトリの `CLAUDE.md`（憲章）と
`README.md` を確認してください。**

```bash
cd insurance-contracts && cat CLAUDE.md   # 保険約款（yakkan-synth）
cd contracts && cat CLAUDE.md             # ビジネス契約書（keiyaku-synth）
cd structured-docs && cat CLAUDE.md       # 汎用化の仕様（docsynth）
```

執筆したコンテンツ（`content/`）、バッチ定義（`specs/`）、生成物（`dataset/`）は、
このリポジトリでは追跡しません。コード（`yakkan/`、`keiyaku/`、`blueprints/` など）と
宣言ファイルのみを追跡しています。

データセットを利用する際は、各プロジェクトの手順（`scaffold` → 執筆 → `batch`）に従って
再生成してください。進行中の計画、残作業、人による判断が必要な項目については、
各プロジェクト内の `TASK.md` または `HITL_TODO.md` を参照してください。これらのファイルは
追跡対象外であり、ローカル環境にのみ存在します。

## データセットの公開

6 つのデータセットすべてを Hugging Face Datasets で公開しています（public・CC BY 4.0）。

| プロジェクト | 公開データセット |
|---|---|
| 保険約款（yakkan-synth） | [`cvusk/japanese-insurance-document-understanding`](https://huggingface.co/datasets/cvusk/japanese-insurance-document-understanding)（文書本体）／[`cvusk/japanese-insurance-document-understanding-retrieval`](https://huggingface.co/datasets/cvusk/japanese-insurance-document-understanding-retrieval)（検索評価セット） |
| 契約書（keiyaku-synth） | [`cvusk/japanese-contract-document-understanding`](https://huggingface.co/datasets/cvusk/japanese-contract-document-understanding)（文書本体）／[`cvusk/japanese-contract-document-understanding-retrieval`](https://huggingface.co/datasets/cvusk/japanese-contract-document-understanding-retrieval)（検索評価セット） |
| 保険約款＋計算（yakkan-calc） | [`cvusk/japanese-insurance-document-understanding-calculation`](https://huggingface.co/datasets/cvusk/japanese-insurance-document-understanding-calculation) |
| 契約書＋計算（keiyaku-calc） | [`cvusk/japanese-contract-document-understanding-calculation`](https://huggingface.co/datasets/cvusk/japanese-contract-document-understanding-calculation) |

詳しくは、各プロジェクトの `docs/distribution.md` または `docs/publishing.md`、計算式データセットは
`insurance-contracts/insurance-contracts-calculation/docs/hf_publication.md` または
`contracts/contracts-calculation/docs/hf_publish.md` を参照してください。

### AI モデルの学習・蒸留について

**配布するデータセットを、LLM、VLM、その他の AI モデルの学習、ファインチューニング、
蒸留、強化学習に利用することはできません。**

生成物の本文、表、図の説明、QA は、Claude Code のセッション内で **Claude（Anthropic）が
生成した出力**です。いずれのプロジェクトでも、外部の LLM API は使用していません。

Anthropic の Usage Policy では、入力と出力を AI モデルの学習に使用すること
（model scraping、model distillation を含む）が、事前の許可なく禁止されています
（<https://www.anthropic.com/legal/aup>）。この規定は競合モデルだけに限定されていないため、
文書読み取り用の小規模なモデルも文面上は対象となります。学習目的で使用する必要がある場合は、
事前に Anthropic の許可を得てください。

一方で、**評価は学習には該当しません。** ドキュメント読み取り（OCR、レイアウト解析、VLM、
構造化抽出）、検索・RAG、AI エージェントの**評価やベンチマークは、このデータセット本来の用途**です。
テストフィクスチャ、few-shot の例、推論時の検索コーパスとしても利用できます。
上記の制限が適用されるのは、モデルの重みを更新する用途です。

なお、**この説明は告知であり、ライセンス条件ではありません。** CC BY 4.0 では、下流の受領者に
追加の制限を課すことが禁止されています（第 2 条(a)(5)(B)）。そのため、上記の禁止事項を
CC BY 4.0 の利用条件には含めていません。この制限は Anthropic の Usage Policy に基づくもので、
同ポリシーの適用対象者に対して効力を持ちます。**この制限は配布ライセンスとは独立しており、
ライセンスの選択によってなくなるものではありません。**

成果物内での記載方法（記載するファイルや節、正式な文面、テストで固定している内容）は、
`insurance-contracts/docs/distribution.md` §7、`contracts/docs/publishing.md` §10、
`structured-docs/docs/distribution.md` §6 を参照してください。

## ライセンス

このリポジトリのコードには、ルートディレクトリの `LICENSE` に記載された MIT License が
適用されます。**生成されたデータセット（`dataset/` 内の PDF、JSON、PNG など）の配布条件は、
プロジェクトごとに定めています。** 詳しくは、上記の「データセットの公開」を参照してください。
プロジェクトによっては、`pyproject.toml` に異なるライセンスが記載されている場合があります。

配布条件とは別に、**生成データを AI モデルの学習や蒸留に利用することはできません。**
詳しくは、上記の「AI モデルの学習・蒸留について」を参照してください。
評価やベンチマークは、この制限の対象外です。
