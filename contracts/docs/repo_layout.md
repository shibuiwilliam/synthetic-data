# repo_layout.md — リポジトリ構成

> ファイルを新規作成・移動する作業では、**着手前に必ず本ファイルを読む**こと。
> ここに無い置き場所を作るときは、**先に本ファイルを更新してから**作る。

```
contracts/                          # = keiyaku-synth（親リポジトリ synthetic-data のサブディレクトリ）
├─ CLAUDE.md                        # プロジェクト憲章（ハードルール・原則・doctype・lint・マイルストーン）
├─ README.md                        # 人間向け概要・セットアップ・データセットの読み方
├─ TASK.md                          # contracts/ 全体（本体＋サブ）の計画と残作業の入口
├─ CURRENT_STATUS.md                # ある時点の状況報告（規模・品質・フェーズ）
├─ PROMPT.md                        # 開発プロンプト集（人間が貼るもの。Claude は自動で読まない）
├─ HITL_TODO.md                     # 人間の判断の依頼・記録・管理（docs/validation_plan.md §5）
├─ HITL_apply_review.md             # apply QA の検算シート（生成物だがコミットする。下節）
├─ pyproject.toml / uv.lock / Makefile / .python-version / .gitignore / .gitattributes
├─ docs/
│   ├─ architecture.md              # yakkan 移植方針・棚卸し表・コードと宣言の境界
│   ├─ schema.md                    # データモデル（yakkan 基底仕様への差分＋契約書の追加要素）
│   ├─ doctypes.md                  # 10 doctype のカタログ・番号方式・style プリセット
│   ├─ rendering.md                 # レンダリングと検証（確定済み描画規約・契約書固有の描画・要probe）
│   ├─ style_guide.md               # 執筆ガイド（架空化・転載の指紋・文体・密度・QA）
│   ├─ authoring_checklist.md       # lint が通っても残る欠陥（執筆前に必読）
│   ├─ reference_structures.md      # samples の構造分析の進め方・課題カタログ CT・分析ログ
│   ├─ evaluation.md                # 評価設計（成果物・指標・予測に使う語彙・DoD）
│   ├─ data_card.md                 # データカード（dataset/data-card.md）の仕様と自動更新
│   ├─ publishing.md                # 公開（Hugging Face Hub）の仕様。views・frontmatter・LFS・手順
│   ├─ validation_plan.md           # 検証・硬化計画（oracle→misread→規則→VLM→盲検→HITL）
│   ├─ plan.md                      # 実行計画とタスク分解（WBS）
│   ├─ lint_rules.md                # lint 各ルールの実装位置と検査ロジック
│   ├─ repo_layout.md               # 本ファイル
│   └─ decisions.md  progress.md  gotchas.md      # 運用ログ
├─ schema/                          # JSON Schema（`keiyaku schema export` の生成物。コミットする）
│                                   #   source_draft / source / layout / answer / qa / prediction /
│                                   #   search_run / element / passage / query / qrel
├─ keiyaku/                         # Python パッケージ（機構。契約書の「知識」は置かない）
│   ├─ models.py  numbering.py  richtext.py  ids.py  env.py  fonts.py
│   ├─ scaffold.py  compose.py  build.py  blueprints.py  styles.py  library.py
│   ├─ answer.py  manifest.py  batch.py  doctypes.py
│   ├─ export.py  export_models.py  search_set.py  figure_graph.py  datacard.py  publish.py
│   ├─ lint/    (base.py, runner.py, rules.py, structure.py, quality.py, budget.py,
│   │            qa_authored.py, table_headers.py, similarity.py, parties.py, walk.py, denylist.txt)
│   ├─ render/  (html.py, inline.py, weasy.py, formula.py, templates/, diagrams/)
│   ├─ layout/  (extract.py, fallback_align.py)      # 実測済みの核心。触らない
│   ├─ verify/  (checks.py, normalize.py)
│   ├─ qa/      (auto.py, validate.py)
│   ├─ eval/    (harness.py, metrics.py, oracle.py, search.py)
│   └─ cli.py
├─ blueprints/<doctype>.yaml         # 10 件（docs/doctypes.md）
├─ numbering/<scheme>.yaml           # contract-standard.yaml / contract-form.yaml / contract-kanji.yaml
├─ styles/<style_id>.yaml + styles/css/<style_id>.css.j2 + styles/css/_base.css.j2
├─ library/clauses/<scheme>/*.json   # 定型条の型（番号方式ごと。オリジナル文のみ。転載厳禁）
│                                   #   現状は contract-standard/ の 7 件のみ。全 doctype 共通の条を
│                                   #   置く common/ は枠だけ用意してある（keiyaku/library.py）
├─ assets/fonts/                     # 同梱フォント（**.ttf 版**＋出典検証用 .otf。SOURCES.md 必須）
├─ content/<content_id>/             # 執筆成果（doc.json, parts/*.json, qa_authored.json, source.json）
│                                    #   **コミットしない**（2026-10-05 決定。第三者が独自に生成する前提）
├─ dataset/<doc_id>/ …               # 生成物。**コミットしない・手編集禁止**
│   ├─ manifest.json  data-card.md  search/
│   └─ **公開用の面**（`keiyaku publish` の生成物。docs/publishing.md）：
│      README.md（= Hub のデータセットカード。frontmatter つき）・views/*.jsonl・
│      licenses/・SHA256SUMS・.gitattributes・.gitignore・（決まれば）LICENSE
├─ specs/                           # バッチ定義ほか（content × style × seed）。**コミットしない**（同上。
│                                   #   ただし publish.yaml だけは例外で追跡する）
│   ├─ batch_v1.yaml                #   v1 の 41 文書
│   ├─ batch_v2.yaml                #   拡張ぶんの 59 文書（合わせて 100 文書）
│   ├─ apply_notes.yaml             #   apply QA の検算メモの正本（HITL_apply_review.md の素）
│   └─ publish.yaml                 #   **公開の宣言（唯一コミットする specs/）**。ライセンス・
│                                   #   Hub のリポジトリ・除外・LFS・引用。人間の決定の正本
├─ samples/                          # 参考 PDF（**コミットしない**。SOURCES.md だけ残す）
│   ├─ SOURCES.md                    # 出典一覧（コミットする）
│   └─ <category>/*.pdf              # 10 カテゴリ・39 ファイル
├─ scripts/                          # probe_*.py, calibrate_styles.py, fill_records.py, authoring.py,
│                                    #   baseline_reader.py, analyze_reference_pdf.py, otf_to_ttf.py,
│                                    #   smoke_render.py, verify_data_card.py,
│                                    #   **upload_hf.py**（Hub へ上げる。既定 dry-run）,
│                                    #   **verify_views.py**（views が表形式に落ちるかの検査）
├─ scratch/                          # 使い捨ての実験出力（コミットしない）
├─ tests/  (unit / golden / render_smoke / fixtures)
├─ contracts-calculation/           # 独立したサブプロジェクト（計算・判定条項の生成器）。
│                                   #   **本体とは別にコミットする**。本体の ruff/pytest の対象外
└─ .claude/
    ├─ commands/  author.md review.md batch.md
    ├─ agents/    author.md reviewer.md render-debugger.md
    ├─ rules/     *.md（frontmatter の paths: で対象を限定）
    └─ settings.json                 # hooks: JSON 保存後 lint --quick、dataset/ 手編集禁止 等
```

## 運用ルール

- `content_id` は `<doctype>-NNNN`（例 `nda-0001`）。`doc_id` は `<content_id>--<style_id>`。
  doctype 名は一意（`keiyaku doctypes` が衝突と参照先の存在を検査する）。
- **コミットする**：`docs/` `schema/` `keiyaku/` `blueprints/` `numbering/` `styles/` `library/`
  `tests/` `assets/` `scripts/` `samples/SOURCES.md` `TASK.md` `CURRENT_STATUS.md` `PROMPT.md`
  ＋ **`specs/publish.yaml`**（公開の宣言。下記）。
- **コミットしない**：`content/` `specs/`（**`specs/publish.yaml` を除く**）`dataset/` `dataset_bkup/` `scratch/` `.venv/` `samples/*.pdf`
  `*.log` `.DS_Store`（`.gitignore`）。**`content/`・`specs/` は 2026-10-05 にコミット対象から外した**
  （`docs/decisions.md` 152）。公開後にこのリポジトリを使う第三者は、コードと宣言（`keiyaku/`
  `blueprints/` `numbering/` `styles/` `library/`）から自分の `content/`・`specs/`・`dataset/` を
  独自に生成する前提とする。`HITL_TODO.md` `HITL_apply_review.md` も非公開のため既にコミットしない
  （`.gitignore`）。
  **例外は `specs/publish.yaml`**：公開（Hugging Face）の配布条件・リポジトリ名・名義は
  **人間の決定の記録**であり、公開物を作るコード（`keiyaku/publish.py`）の入力でもあるので追跡する。
  `.gitignore` では `specs/*` ＋ `!specs/publish.yaml` と書く（**ディレクトリ単位の除外では
  配下を再包含できない**。`parts/` と同じ罠。変えたら `git check-ignore -v specs/publish.yaml`）。
  宣言が無い環境でも `keiyaku export` は止まらない（`publish.default_spec()` に落ち、公開だけがふさがる）。
- **本体のコミットに含めない**：`contracts-calculation/`。独立したサブプロジェクトで、
  別のコミットで扱う（`.gitignore` では**意図的に除外していない**。TASK.md §0.3）。
  本体の `make check` の対象からは `pyproject.toml` の `[tool.ruff] extend-exclude` で外してある。
- `assets/fonts/**` は `.gitattributes` で `-text`（改行変換を禁止）。`SOURCES.md` の SHA256 と
  バイト単位で一致させるため。
- 親リポジトリ（`synthetic-data`）の `.gitignore` に Python 汎用の `parts/` `lib/` `build/` がある。
  **`content/` 自体を丸ごと除外する**ため、`content/<cid>/parts/` を個別に打ち消す必要はない
  （2026-10-05 以前は `!parts/` `!content/**/parts/` で打ち消していたが、`content/` 全体が
  非対象になったので撤去した）。
- `dataset/` の掃除も手の `rm` ではなくコマンドで行う（`keiyaku clean --stale`。
  **手編集禁止と区別がつかなくなる**ため）。`dataset/` 直下に文書以外のディレクトリを足したら
  **`keiyaku/cli.py` の `PROTECTED_DIRS` に入れる**（`search/` `views/` `licenses/`。
  入れないと `clean --stale` が doc_id に無いものとして消す）。
- `../insurance-contracts/` と `../structured-docs/` は**読み取り専用の参照**。本プロジェクトから書き換えない。
- `samples/` の PDF は**構造分析のためだけに開く**。取得した本文をリポジトリに保存しない
  （スクリーンショットも保存しない。`docs/reference_structures.md` §0）。


## 生成物だがコミットするもの

- `HITL_apply_review.md`：`apply` QA の検算シート（`scripts/apply_review.py` の出力）。
  人間が判断するための材料なので、コマンドを走らせなくても読めるようにリポジトリに置く。
  **手で編集しない**——問い・答え・根拠は `content/<cid>/qa_authored.json` と `dataset/`、
  検算メモと「見てほしい点」は **`specs/apply_notes.yaml`** が正本。
- `HITL_TODO.md` には**未決の判断だけ**を置く。決まった項目は `docs/validation_plan.md` §5 へ移す。
