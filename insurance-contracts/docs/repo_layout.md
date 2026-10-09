# repo_layout.md — リポジトリ構成

> CLAUDE.md §10 の全文を 2026-09-21 にそのまま移設したもの（一字一句の変更なし）。
> ファイルを新規作成・移動する作業では、**着手前に必ず本ファイルを読む**こと。

## 10. リポジトリ構成
```
yakkan-synth/
├─ CLAUDE.md                     # 本ファイル（要約版へ縮約予定、§0.3）
├─ README.md                     # 人間向け概要・セットアップ
├─ pyproject.toml / uv.lock
├─ Makefile                      # make setup / check / doc CONTENT=… STYLE=… / batch SPEC=…
├─ docs/
│   ├─ decisions.md  progress.md  gotchas.md
│   ├─ schema.md  rendering.md  style_guide.md  blueprints.md  reference_structures.md
├─ schema/                       # JSON Schema（export 生成物、コミットする）
├─ blueprints/<genre>.yaml
├─ styles/<style_id>.yaml  + styles/css/<style_id>.css
├─ library/clauses/<genre>/*.json
├─ assets/fonts/  assets/icons/  assets/fonts/SOURCES.md
├─ yakkan/                       # Python パッケージ
│   ├─ models.py  numbering.py  richtext.py  scaffold.py  compose.py  build.py
│   ├─ lint/ (rules.py, denylist.txt, similarity.py, budget.py)
│   ├─ render/ (html.py, weasy.py, templates/, diagrams/{flowchart,tree,steps,timeline,mock,matrix}.py, formula.py)
│   ├─ layout/ (extract.py, fallback_align.py)
│   ├─ verify/ (checks.py, normalize.py)
│   ├─ qa/ (auto.py, validate.py)
│   ├─ eval/ (metrics.py, teds.py)
│   └─ cli.py
├─ content/<content_id>/ (doc.json, parts/*.json, source.json)   # コミットしない（2026-10-05）
├─ dataset/<doc_id>/ …  dataset/manifest.json, README.md（HF カード）, data-card.md, LICENSE  # コミットしない
├─ specs/batch_v1.yaml           # 生成バッチ定義（content×style×seed）コミットしない
├─ tests/ (unit + golden)
├─ scripts/                      # 実験・保守用。パッケージには入れない
│   ├─ authoring.py              # 執筆ヘルパ（表・列挙表・条の組み立て）
│   ├─ verify_data_card.py       # データカードの測り方を別経路で再計算して検算する
│   ├─ fill_records.py           # 表の records を grid から埋める
│   ├─ calibrate_styles.py       # 実物のページ数から 1 ページの容量を当てる
│   ├─ analyze_reference_pdf.py  # 参考 PDF の構造を測る（転載はしない）
│   └─ probe_*.py                # WeasyPrint の私的 API の挙動確認（CLAUDE.md §14）
└─ .claude/
    ├─ commands/ author.md review.md batch.md   # /author <content_id> 等
    ├─ agents/ author.md reviewer.md render-debugger.md
    └─ settings.json             # hooks: 編集後に ruff/lint、危険コマンド抑止
```


## 分割後（2026-09-21）の追加・変更点

上のツリーは CLAUDE.md §10 の原文。分割によって `docs/` の中身が次のとおり増えた。

```
docs/
├─ decisions.md  progress.md  gotchas.md      # 運用ログ（§0.3）
├─ schema.md          # 旧 §1.1 + §5（データモデル）
├─ rendering.md       # 旧 §6（レンダリングパイプライン）
├─ style_guide.md     # 旧 §7（コンテンツ生成・文体）
├─ blueprints.md      # 旧 §4.1 + §4.2 + 付録A + 付録B
├─ reference_structures.md  # 旧 §3（構造分析カタログ + 参考URL + 分析ログ）
└─ repo_layout.md     # 旧 §10（本ファイル）
```

- ルートは現状 `insurance-contracts/`（親の `synthetic-data` リポジトリのサブディレクトリ）。§10 のツリーが示す `yakkan-synth/` はこのディレクトリに読み替える。
- `.claude/rules/*.md` は frontmatter の `paths:` で対象ファイルを限定する（§0.3）。

## 2026-09-22 に足したもの（評価データセット）

| パス | 役目 |
|---|---|
| `yakkan/figure_graph.py` | 図 6 種を共通の有向グラフに正規化する（`docs/eval_dataset_plan.md` P1） |
| `yakkan/export.py` | `elements.jsonl` / `passages.jsonl` / `qa.jsonl` / `documents.jsonl` と、**2 つの HF データセットの配布物**（本体の `dataset/README.md`・`LICENSE`・`.gitattributes` と、検索評価セットの `dataset/search/README.md`・`LICENSE`・`.gitattributes`）を書き出す（`docs/distribution.md`） |
| `yakkan/datacard.py` | `dataset/data-card.md`（利用者向けデータカード）を実測から生成し、鮮度を検査する（`docs/data_card.md`） |
| `yakkan/search_set.py` | 検索評価のパッセージ・クエリ・qrels を作る |
| `yakkan/eval/metrics.py` | CER・F1・TEDS・Kendall τ・nDCG などの指標 |
| `yakkan/eval/harness.py` | 予測 JSON の採点 |
| `yakkan/eval/oracle.py` | 満点の予測を作る（予測フォーマットの実装例／自己評価） |
| `yakkan/eval/search.py` | 検索結果の採点 |
| `schema/prediction.schema.json` | 読み取り予測の形 |
| `schema/search_run.schema.json` | 検索結果の形 |
| `docs/evaluation.md` | 予測の形と採点のしかた |
| `docs/eval_dataset_plan.md` | 充足性レビューと改修計画（P1〜P10） |

## 2026-10-03 に足したもの（検索クエリの改修提案・判断待ちの整理）

| パス | 役目 |
|---|---|
| `TASK.md`（ルート） | **判断待ちタスクの一覧（人間向けの入口）**。T1〜T7。各件の詳細は `HITL_TODO.md` の H 番号へ |
| `HITL_TODO.md`（ルート） | 人間の判断・レビューが要る残件の詳細。H1〜H13 |
| `docs/search_query_design.md` | 検索クエリ（`term`／`heading`）が対象を特定できない欠陥の**実測と設計**（診断 C1〜C6・施策 AA-1〜AA-15） |
| `docs/search_query_plan.md` | 上の**実施計画**（作業単位 W0〜W20・テスト T-1〜T-15・レビュー R-A〜R-E・評価 §5・リスク §6・DoD §7）。**実装はこちらを正とする** |
| `scripts/probe_search_queries.py` | 検索クエリの弁別力を 6 通りに測る（標準ライブラリのみ）。素朴な文字 2-gram BM25 を同梱 |

ルート直下の md は 4 本：`CLAUDE.md`（仕様）・`README.md`（人間向け概要）・
`TASK.md`（判断待ち）・`HITL_TODO.md`（判断の詳細・**git の追跡外**）。
**判断の記入は `TASK.md` に集約する**（`HITL_TODO.md` は経緯と手順を持つ）。

## 2026-10-05 に整理したもの（コミット可能な状態への棚卸し）

| パス | 扱い |
|---|---|
| `insurance-contracts-calculation/` | **別プロジェクト**（本体に計算・判定の規定とその正解プログラムを足す拡張）。本体のコミットには含めず個別に対応する。`.gitignore` には入れない（いずれコミットするため）。独自の `CLAUDE.md` `DESIGN.md` `TASK.md` を持つので、そちらを触る作業ではそのディレクトリのドキュメントを読む |
| `HITL_TODO.md` | `.gitignore` 済み（2026-10-05 に `git rm --cached` で追跡を外した）。**ローカル作業ファイル**であり、公開リポジトリには含めない。`TASK.md` の H 番号参照はローカルファイルへの参照と読む |
| `dataset_bkup/` | 作業前バックアップ（`.gitignore` 済み）。再生成できるので必要がなくなったら消してよい |
| `scratch/` | probe と smoke の出力先（`.gitignore` 済み）。`make clean` で消える |
| `.venv/` `.pytest_cache/` `.ruff_cache/` `__pycache__/` `.DS_Store` | いずれも `.gitignore` 済み。`__pycache__` 等は**親リポジトリの `.gitignore`** が受け持つ |

**`.gitignore` は 2 枚ある。** 親（リポジトリルート）の Python 汎用テンプレートと、本ディレクトリの補正。

## 2026-10-05 に足したもの（参考URL一覧の分離）

`docs/reference_structures.md` §3.2（参考URLの表）を `docs/reference_urls.md` に分離し `.gitignore` した
（実在保険会社の公開PDFへの直接URLをGitHubにコミットしないため。`docs/decisions.md`）。
構造分析カタログ・分析ログ本体は従来どおり `docs/reference_structures.md` にコミットする。

## 2026-10-05 に変更したもの（content/・specs/ の非コミット化）

ユーザー決定により、`content/`・`specs/` も `dataset/` と同じく**コミット対象外**にした。
公開後の第三者は `blueprints/` ＋ `yakkan/` ＋ `library/clauses/` から `scaffold`→執筆→`lint`→`build`→
`render`→`batch` を自分で実行し、`content/`・`specs/`・`dataset/` を独自に再生成する前提（`docs/decisions.md`）。

- これに伴い、親の `parts/`（setuptools 由来）除外を打ち消す `!parts/` `!content/**/parts/` は不要になり削除した
  （`content/` 自体を丸ごと除外するため、配下の `parts/` を個別に再包含する理由がなくなった）。
- `git rm --cached` で既存の追跡（`content/` 350ファイル＋`specs/` 2ファイル）を外した。**git 履歴には残る**（force-push や履歴書き換えはしていない）。
- 執筆済みの `content/` は LLM が書いた一点物であり、`dataset/` のように決定論的に再生成できるものではない。
  再生成すれば**別の文書**になる（§2 設計原則1は様式の決定論のみを保証し、文章そのものではない）。
  この差分は把握済みでユーザーが承認した上での決定（2026-10-05）。
