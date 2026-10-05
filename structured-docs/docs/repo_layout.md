# repo_layout.md — リポジトリ構成

> ファイルを新規作成・移動する作業では、**着手前に必ず本ファイルを読む**こと。
> ここに無い置き場所を作るときは、先に本ファイルを更新してから作る。

```
structured-docs/
├─ CLAUDE.md                     # プロジェクト憲章（ハードルール・原則・lint・マイルストーン）
├─ README.md                     # 人間向け概要・セットアップ
├─ HITL_TODO.md                  # 人間の判断・レビュー待ちの台帳（D1〜。docs/validation_plan.md §5）
├─ pyproject.toml / uv.lock / Makefile / .python-version
├─ docs/
│   ├─ architecture.md           # コア／ファミリー境界・yakkan 移植方針・棚卸し表
│   ├─ schema.md                 # データモデル（yakkan-synth 基底仕様への差分＋基底確定後の拡張一覧）
│   ├─ families.md               # ファミリー定義仕様＋初期5ファミリーのカタログ＋追加手順
│   ├─ rendering.md              # レンダリング（基底仕様への差分・確定済み描画規約・新ブロック・要probe）
│   ├─ evaluation.md             # 評価設計（成果物・13+8 指標・クエリ 10 種・予測語彙・採点の原則・DoD）
│   ├─ data_card.md              # データカード（dataset/data-card.md）の仕様と自動更新
│   ├─ validation_plan.md        # 検証・硬化計画（V-A〜V-F：oracle→misread→規則→VLM→盲検→HITL）
│   ├─ plan.md                   # 実行計画とタスク分解（WBS。CLAUDE.md §12 の詳細版）
│   ├─ lint_rules.md             # lint 各規則の実装位置・検査ロジック（L00–L26 ＋ FLxx）
│   ├─ style_guide.md            # 執筆ガイド（架空化・文体・QA）
│   ├─ authoring_checklist.md    # lint が通っても残る欠陥の一覧（執筆前に必読）
│   ├─ reference_structures.md   # 実在文書の構造分析の進め方・転載禁止・課題カタログ G1–G13
│   ├─ distribution.md           # 生成物の配布とライセンス表示（判断と実行は人間）
│   ├─ repo_layout.md            # 本ファイル
│   └─ decisions.md  progress.md  gotchas.md    # 運用ログ
├─ schema/                       # JSON Schema（docsynth schema export の生成物。コミットする）
│                                #   source_draft/source/layout/answer/qa/prediction/search_run/
│                                #   element/passage/query/qrel
├─ docsynth/                     # Python パッケージ（コア。ドメイン知識を置かない）
│   ├─ models.py  numbering.py  richtext.py  ids.py  env.py  fonts.py
│   ├─ scaffold.py  compose.py  build.py  answer.py  manifest.py  batch.py
│   ├─ export.py  export_models.py  search_set.py  figure_graph.py
│   ├─ families.py               # ファミリーレジストリ（family.yaml の読込・検証・フックのロード）
│   ├─ lint/    (base.py, runner.py, rules.py, structure.py, quality.py, budget.py,
│   │            qa_authored.py, table_headers.py, similarity.py, walk.py, denylist_common.txt)
│   ├─ render/  (html.py, inline.py, weasy.py, formula.py, templates/base/, diagrams/)
│   ├─ layout/  (extract.py, fallback_align.py)
│   ├─ verify/  (checks.py, normalize.py)
│   ├─ qa/      (auto.py, validate.py)
│   ├─ eval/    (harness.py, metrics.py, oracle.py, search.py)
│   ├─ datacard.py               # dataset/data-card.md の生成と鮮度検査（docs/data_card.md）
│   └─ cli.py
├─ families/<family>/            # ドメイン知識（docs/families.md §1 の規約）
│   │                            #   contract / terms / regulations / statute / insurance
│   ├─ family.yaml  denylist.txt  hooks.py(MAY)
│   ├─ numbering/<scheme>.yaml
│   ├─ blueprints/<doctype>.yaml
│   ├─ styles/<style_id>.yaml + styles/css/ + styles/templates/(MAY)
│   ├─ library/                  # 条文ライブラリ（オリジナル文のみ）
│   └─ docs/ (structures.md, style.md)
├─ assets/fonts/                 # 同梱フォント（yakkan と同一。.ttf 版＋出典検証用 .otf。SOURCES.md 必須）
├─ content/<content_id>/         # 執筆成果（doc.json, parts/*.json, qa_authored.json, source.json）。コミットする
├─ dataset/<doc_id>/ …           # 生成物。コミットしない・手編集禁止
│   └─ dataset/manifest.json  dataset/search/  dataset/README.md  dataset/data-card.md
├─ specs/                        # バッチ定義（content×style×seed）
├─ scripts/                      # probe_*.py, calibrate_styles.py, fill_records.py, authoring.py,
│                                #   baseline_reader.py, analyze_reference_pdf.py, otf_to_ttf.py 等
├─ scratch/                      # 使い捨ての実験出力（コミットしない）
├─ tests/  (unit / golden / render_smoke / fixtures)
└─ .claude/
    ├─ commands/  author.md review.md batch.md
    ├─ agents/    author.md reviewer.md render-debugger.md
    ├─ rules/     *.md（frontmatter の paths: で対象を限定）
    └─ settings.json             # hooks: JSON 保存後 lint --quick、dataset/ 手編集禁止 等
```

## 運用ルール

- `content_id` は `<doctype>-NNNN`（例 `nda-0001`）。`doc_id` は `<content_id>--<style_id>`。
  doctype 名はファミリーをまたいで一意にする（`docsynth families` が衝突を検査）。
- コミットする：`docs/` `schema/` `docsynth/` `families/` `content/` `specs/` `tests/` `assets/` `scripts/`。
  コミットしない：`dataset/` `scratch/` `.venv/`（`.gitignore` で除外）。
- 親リポジトリ（`synthetic-data`）の `.gitignore` に Python 汎用の `parts/` `lib/` `build/` 等がある。
  本ディレクトリの `.gitignore` で**ディレクトリ単位の否定**（`!parts/`）を先に書いて打ち消す
  （yakkan の実害。`git check-ignore -v` で確認する）。
- **姉妹 2 本（`../insurance-contracts/`・`../contracts/`）は読み取り専用の参照**。本プロジェクトから
  書き換えない。同等性テストだけが `../insurance-contracts/content/`（insurance）と
  `../contracts/content/`（contract）を相対パスで読む（存在しない環境ではスキップ）。
- **参考にした実在文書（PDF・画像）はリポジトリに置かない。** 出典一覧（URL・入手日・
  構造メモ）だけを `families/<f>/docs/structures.md` に残す（`docs/reference_structures.md` §0。
  keiyaku は `samples/` を `.gitignore` して `SOURCES.md` だけ残す運用にしている）。
- `dataset/data-card.md` は生成物。**手で書かない**（`docsynth datacard update`）。
- `dataset/` の掃除も手の `rm` ではなくコマンドで行う（`docsynth clean --stale`。手編集禁止と
  区別がつかなくなるため）。
