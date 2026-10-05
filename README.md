# synthetic-data

日本語ドキュメント読み取り（OCR・レイアウト解析・VLM・構造化抽出）と検索エンジンの
開発・検証に使う、**完全に架空だが本物そっくりな日本語文書**と**その完全な正解データ**を
対で生成するプロジェクト群のモノレポ。

生成物はいずれも同じ原則に立つ。

- **正解 JSON が唯一の真実**（single source of truth）で、PDF はその決定論的な描画結果
  （JSON → HTML → PDF）。正解と紙面が食い違うことは原理的に起きない。
- 会社名・商品名・人物名・連絡先・URL はすべて架空（`example.jp` 系 URL・ゼロ埋め電話番号）。
  実在文書の**文章は転載せず、構造・レイアウト慣行だけ**を参考にする。
- テキスト・章節項構造・表・図・参照関係・QA を評価軸として正解に持ち、採点用の評価ハーネスを同梱する。

## 構成

| ディレクトリ | 通称 | 対象文書 | 状態 |
|---|---|---|---|
| [`insurance-contracts/`](insurance-contracts/) | yakkan-synth | 保険約款（自動車・地震・生命・旅行 等 10 ジャンル） | 完済（`dataset_version: v7`）。10 ジャンル・100 content・114 データセット・1,458 ページ・QA 5,085 問 |
| [`contracts/`](contracts/) | keiyaku-synth | ビジネス契約書（秘密保持・業務委託・売買・雇用 等 10 doctype） | v1 データセット完成（2026-10-05）。10 doctype・100 文書 |
| [`structured-docs/`](structured-docs/) | docsynth | 上記 2 つの汎用化。契約書・利用規約・社内規程・法令・保険約款を「ファミリー」として扱う | 仕様のみ（`docs/`・`CLAUDE.md`）。実装は未着手 |

各本体には、契約書・約款に**計算・判定条項の正解プログラム**を足す拡張サブプロジェクトが同居する
（本体のコミットには含めず別管理）。

| ディレクトリ | 内容 |
|---|---|
| [`contracts/contracts-calculation/`](contracts/contracts-calculation/) | keiyaku-synth の契約書に計算条項を追加し、正解 Python プログラムとテストケースを同時生成 |
| [`insurance-contracts/insurance-contracts-calculation/`](insurance-contracts/insurance-contracts-calculation/) | yakkan-synth の約款に同様の計算条項を追加 |

`structured-docs`（docsynth）は `insurance-contracts` と `contracts` の実証済みの設計・評価ハーネスを
再検証せずに継承し、ドメイン知識を `families/` としてプラグイン化する汎用基盤の構想である。

## 使い方

各ディレクトリは自己完結したプロジェクトで、仕様・規約・コマンドはすべて中にある。
**作業を始める前に、そのディレクトリの `CLAUDE.md`（憲章）と `README.md` を読むこと。**

```bash
cd insurance-contracts && cat CLAUDE.md   # 保険約款（yakkan-synth）
cd contracts && cat CLAUDE.md             # ビジネス契約書（keiyaku-synth）
cd structured-docs && cat CLAUDE.md       # 汎用化の仕様（docsynth）
```

生成に使った執筆成果（`content/`）・バッチ定義（`specs/`）・生成物（`dataset/`）はいずれも
このリポジトリにはコミットしない。コード（`yakkan/` `keiyaku/` `blueprints/` 等）と宣言だけを
追跡し、第三者は各プロジェクトのコマンド（`scaffold` → 執筆 → `batch`）で自分のデータセットを
再生成する前提にしている。進行中の計画・残作業・人間の判断待ちは、各プロジェクト内の
`TASK.md`／`HITL_TODO.md`（追跡対象外。ローカルにのみ存在）を見る。

## データセットの公開

- **保険約款（yakkan-synth）**：Hugging Face Datasets
  `cvusk/synthetic-japanese-insurance-documents` として公開準備が完了（ライセンス CC BY 4.0）。
  アップロードは人手で行う。
- **契約書（keiyaku-synth）**：Hugging Face Hub への公開形は整えたが、配布ライセンスは未決定。
  アップロードは未実施。

いずれも詳細は各プロジェクトの `docs/distribution.md` ／ `docs/publishing.md` を参照。

## ライセンス

リポジトリのコード（このルートの `LICENSE`）は MIT。
**生成されたデータセット（`dataset/` の PDF・JSON・PNG 等）の配布条件は各プロジェクトで別途定める**
（上記「データセットの公開」を参照。プロジェクトごとに `pyproject.toml` の宣言が異なる場合がある）。
