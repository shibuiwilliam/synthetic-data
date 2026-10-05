# keiyaku-synth — 日本語ビジネス契約書の合成データ生成基盤

実在の契約書そっくりだが **完全に架空** の日本語契約書（PDF）と、その **完全な正解データ**（JSON）を
対で生成する。ドキュメント読み取りシステム（OCR / レイアウト解析 / VLM / 構造化抽出）と
検索エンジンの開発検証用。

## なぜ作るのか

契約書の読み取りを開発するとき、手元にある契約書はどれも使えない。

- **本物の契約書**は当事者名・金額・取引条件が入っており、社外に出せない。
- **公開されているひな型**（公的機関のモデル契約書・法律事務所のサンプル）は第三者の著作物で、
  データセットとして再配布できない。
- どちらにも「**どこに何が書いてあるか**」の正解が付いていない。第4条第2項の本文はどこからどこまでか、
  この表のセルはどの行見出し × どの列見出しに属するか、「別紙1」はどの別紙を指すか——人手で付けるしかない。

そこで **構造的特徴だけを実在契約書から学び、文章は全部オリジナルに書いた合成契約書**と、
**機械が生成した完全な正解**を対で作る。正解 JSON が唯一の真実で、PDF はその決定論的な描画結果
（JSON → HTML → PDF）なので、正解と紙面が食い違うことが原理的に起きない。

先行プロジェクト [`../insurance-contracts/`](../insurance-contracts/)（yakkan-synth）が保険約款で
この方式を成立させ、規則ベース読み取り器・VLM・**構築経緯を知らない盲検エージェント**の3段で
「外部の読み手が使えるデータセットである」ことまで実証している。本プロジェクトはその実装を
**契約書ドメインに特化して転用**したものである。

## 何ができるか

- 10 種類の契約書（秘密保持・業務委託・準委任・コンサルティング・売買・賃貸借・ライセンス・
  システム開発・請負・雇用）を、doctype ごとの骨格・必須要素・文体の宣言から生成する。
- 同じ内容を別のレイアウト（判型・フォント・罫線・様式型の版面）で描き直せる。
  内容の正解は不変で、bbox と読み順だけが変わる——**レイアウト頑健性の検証データが安価に増える**。
- 6 観点の正解：テキスト／条項構造／表／図／参照関係（`{ref:}`・別紙・当事者呼称）／QA。
- 読み取り精度の採点（13 指標）と検索の採点（7 指標）をコマンド 1 本で行える。

## 状態

**データセット v1 完成（2026-10-05 時点）。** 10 doctype × 5 content ＝ **50 本の契約書**を
1〜2 レイアウトで描いた **100 文書**（657 ページ・表 247・図 104・QA 4,500 問）。
`eval --all --oracle` は 100 文書 × 18 指標すべて満点、全 content が lint（類似度込み）error 0 / warn 0、
全文書が verify・qa とも error 0。規則ベース読み取り・VLM・**構築経緯を知らない盲検エージェント 5 本**まで
検証済み（`docs/validation_plan.md` の V-A〜V-F）。

進捗の詳しい経緯は `docs/progress.md`。

`dataset/` は生成物なのでリポジトリに入れていない。下の手順で再生成する。

## セットアップ

必要なもの：[uv](https://docs.astral.sh/uv/)（Python 3.12 を入れる）、Pango。

```bash
# macOS
brew install pango
# Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev

uv sync            # 依存の導入（= make setup）
make doctor        # 環境の検査（Python / WeasyPrint / Pango / フォント / pypdfium2）
make check         # ruff + pytest + manifest とデータカードの鮮度
make smoke         # 動作確認用の PDF と PNG を scratch/smoke/ に生成
```

macOS では Homebrew の dylib が dyld の既定検索パスに無いため、素の `uv run` では WeasyPrint の
import が失敗する。`make` 経由なら `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が自動で渡る。
直接叩くときは自分で付ける。他の落とし穴は `docs/gotchas.md`。

## 1 文書を作る

```bash
uv run keiyaku scaffold --doctype nda --content-id nda-0001 --seed 42   # 執筆用スケルトン
#  … content/nda-0001/parts/*.json を執筆 …
make doc CONTENT=nda-0001 STYLE=ct-a4-1col-mincho    # lint → build → render → verify → qa
uv run keiyaku review dataset/nda-0001--ct-a4-1col-mincho   # 全ページ PNG を目視（必須）
```

## データセットを丸ごと再生成する

`content/`（執筆物）・`specs/`（バッチ定義）・`dataset/`（生成物）はコミットしていない
（2026-10-05 決定。`docs/decisions.md` 152）。このリポジトリにコミットしてあるのは宣言
（`blueprints/` `numbering/` `styles/` `library/`）と実装（`keiyaku/`）だけなので、第三者は
`content/`・`specs/` を自分で用意する必要がある。

```bash
# 1. 各 doctype ごとに執筆用スケルトンを作り、本文を書く（CLAUDE.md §7 の執筆プロトコル）
uv run keiyaku scaffold --doctype nda --content-id nda-0001 --seed 42
#  … content/nda-0001/parts/*.json を執筆 …
uv run keiyaku lint content/nda-0001

# 2. バッチ定義（specs/*.yaml）を自分で書き、まとめて生成する
uv run keiyaku batch specs/my_batch.yaml
uv run keiyaku manifest update && uv run keiyaku manifest check
uv run keiyaku export                       # elements.jsonl / search / README / data-card.md
uv run keiyaku eval --all --oracle          # 全文書・全指標が満点になること
```

## ドキュメント

| ファイル | 中身 |
|---|---|
| `CLAUDE.md` | **プロジェクト憲章**：ハードルール・設計原則・doctype 一覧・lint（L00–L26）・マイルストーン P0–P8 |
| `docs/architecture.md` | yakkan からの移植方針・モジュール棚卸し表・コアと宣言の境界 |
| `docs/schema.md` | 正解 JSON のデータモデル（yakkan 基底仕様への差分＋契約書の追加要素） |
| `docs/doctypes.md` | 10 doctype のカタログ（必須要素・variants）・番号方式・style プリセット |
| `docs/rendering.md` | レンダリングと検証（WeasyPrint・確定済み描画規約・契約書固有の描画・要probe） |
| `docs/style_guide.md` | 執筆ガイド（架空化・転載の指紋・文体・密度要件・QA の型） |
| `docs/authoring_checklist.md` | **lint が通っても残る欠陥**の一覧（執筆前に必読） |
| `docs/reference_structures.md` | `samples/` の構造分析の進め方（転載禁止）・課題カタログ CT1〜 |
| `docs/evaluation.md` | 評価設計（成果物・指標・**予測に使う語彙**・合格条件） |
| `docs/data_card.md` | データカード（`dataset/data-card.md`）の仕様と自動更新 |
| `docs/publishing.md` | **データセットの公開（Hugging Face Hub）**：カードの frontmatter・Viewer 用の `views/`・LFS・手順 |
| `docs/validation_plan.md` | 検証・硬化計画（oracle → misread → 規則ベース → VLM → 盲検 → HITL） |
| `docs/plan.md` | 実行計画とタスク分解（WBS） |
| `docs/lint_rules.md` | lint 各ルールの実装位置と検査ロジック |
| `docs/repo_layout.md` | ディレクトリ構成と運用ルール |
| `docs/decisions.md` `progress.md` `gotchas.md` | 運用ログ（設計変更履歴／進捗／環境の癖） |

## データセットの読み方

`dataset/<doc_id>/` が 1 文書ぶん。`doc_id` は `<content_id>--<style_id>`
（同じ内容を別レイアウトで描いたものは `content_id` が同じで `style_id` が違う）。

| ファイル | 中身 |
|---|---|
| `doc.pdf` | 生成 PDF。フォント埋め込み・テキスト層あり・タグ無し |
| `pages/page-NNN.png` | 150dpi のページ画像（画像ベースの読み取り検証用） |
| `source.json` | 内容と意味。**レイアウト非依存**（判型・フォントを変えても不変） |
| `layout.json` | 描画結果。ページ・要素ごとの bbox・読み順・ヘッダ／フッタ |
| `answer.json` | ページ別の期待テキストとアウトライン。**`source` と `layout` は内包しない**（同じ場所に実体がある。3 つまとめて扱うときは `keiyaku.answer.load_answer(dir)`） |
| `elements.jsonl` | 1 行 1 要素の平らな索引。**評価スクリプトはまずこれを読む** |
| `qa.json` | 問答（自動生成 30 問＋執筆 15 問） |
| `render.html` | デバッグ用の中間 HTML（配布対象外） |

全文書の一覧は `dataset/manifest.json`、検索評価セットは `dataset/search/`、
実測値入りの概要は `dataset/README.md`、規模・作り方・品質保証・制限と偏りをまとめた
**データカードは `dataset/data-card.md`**（いずれも `keiyaku export` が実測して生成する）。
正解 JSON の各フィールドの意味は `docs/schema.md`、読み取り予測の形と採点は `docs/evaluation.md`。

### 公開（Hugging Face Hub）

`keiyaku export`（または `keiyaku publish update`）は、`dataset/` を **Hugging Face の
データセットリポジトリとしてそのまま上げられる形**にする：`dataset/README.md` は frontmatter つきの
データセットカードになり、`views/{documents,pages,qa}.jsonl`（Dataset Viewer と `load_dataset()` 用の
平らな射影）・`.gitattributes`（PDF・PNG を LFS）・`licenses/`（PDF に埋め込まれているフォントの本文）・
`SHA256SUMS` が付く。`render.html` は配布しない。

```
uv run keiyaku publish check                   # 公開用の面の鮮度と、公開をふさいでいる条件
uv run python scripts/verify_views.py          # views が parquet に落ちるかの検査
uv run python scripts/upload_hf.py             # 何が上がるかを数えるだけ（既定。通信しない）
```

公開先・名義・除外などの**決定は `specs/publish.yaml`**（`specs/` で唯一コミットするファイル）。
**配布条件（ライセンス）が未決のあいだアップロードは拒否される**（下記を参照）。
仕様は `docs/publishing.md`。

## 参考サンプル（`samples/`）

10 カテゴリ・36 種の実在ひな型（公的機関・業界団体・法律事務所が公開しているもの）を
構造分析のために集めてある。出典の一覧は `samples/SOURCES.md`。

> **これらは第三者の著作物である。** 参考にしてよいのは構造（見出し階層・条文構成・別紙の有無・
> 表の形式）だけで、**文章は 1 文も生成物に持ち込まない**。「公的機関のひな型だから著作権はない」と
> 判断しない。PDF 本体はリポジトリにコミットしない（`.gitignore` で除外。`SOURCES.md` だけ残す）。
> 運用の詳細は `docs/reference_structures.md` §0。

## ライセンスと架空性

生成される文書の会社名・屋号・人物名・住所・連絡先・契約書番号・物件名はすべて架空で、
参考にした実在ひな型からは**構造のみ**を採っている。各文書の末尾に架空である旨を明記する。
**生成物は読み取り検証用のダミーであり、法的に有効な契約書ではない。実務に使わないこと。**

- **コード**：`pyproject.toml` の宣言は `Proprietary`。親リポジトリ直下の `LICENSE`（MIT）と
  食い違っているので、公開の前にどちらかへ揃える（未決）。
- **同梱フォント**（`assets/fonts/`）：SIL Open Font License 1.1（Noto 系）と
  IPA フォントライセンス v1.0（IPAex 系）。いずれも再配布と埋め込みが認められている。
  出典・版・SHA256 は `assets/fonts/SOURCES.md`。
- **生成物**（`dataset/` の PDF・JSON・PNG）の配布条件は**未決**。
  決まるまで外部配布しない。公開（Hugging Face）の準備は済んでいるが、
  `specs/publish.yaml` の `license.id` が `undecided` のあいだ、カードは「未決」と表示し、
  frontmatter に `license` を出さず、`scripts/upload_hf.py` は**アップロードを拒否する**。
