# repo_layout.md — リポジトリ構成

> ファイルを新規作成・移動する作業では、**着手前に必ず本ファイルを読む**こと。
> ここに無い置き場所を作るときは、先に本ファイルを更新してから作る。

```
structured-docs/
├─ CLAUDE.md                     # プロジェクト憲章（ハードルール・原則・lint・マイルストーン）
├─ README.md                     # 人間向け概要・セットアップ
├─ pyproject.toml / uv.lock / Makefile / .python-version
├─ docs/
│   ├─ architecture.md           # コア／ファミリー境界・yakkan 移植方針・棚卸し表
│   ├─ schema.md                 # データモデル（yakkan-synth 基底仕様への差分）
│   ├─ families.md               # ファミリー定義仕様＋初期4ファミリーのカタログ＋追加手順
│   ├─ rendering.md              # レンダリング（基底仕様への差分・新ブロック・要probe）
│   ├─ style_guide.md            # 執筆ガイド（架空化・文体・チェックリスト）
│   ├─ reference_structures.md   # 実在文書の構造分析の進め方・転載禁止
│   ├─ repo_layout.md            # 本ファイル
│   └─ decisions.md  progress.md  gotchas.md    # 運用ログ
├─ schema/                       # JSON Schema（docsynth schema export の生成物。コミットする）
├─ docsynth/                     # Python パッケージ（コア。ドメイン知識を置かない）
│   ├─ models.py  numbering.py  richtext.py  ids.py  env.py  fonts.py
│   ├─ scaffold.py  compose.py  build.py  answer.py  manifest.py  batch.py
│   ├─ families.py               # ファミリーレジストリ（family.yaml の読込・検証・フックのロード）
│   ├─ lint/    (rules.py, denylist_common.txt, similarity.py, budget.py)
│   ├─ render/  (html.py, weasy.py, formula.py, templates/base/, diagrams/)
│   ├─ layout/  (extract.py, fallback_align.py)
│   ├─ verify/  (checks.py, normalize.py)
│   ├─ qa/      (auto.py, validate.py)
│   ├─ eval/    (metrics.py, teds.py)
│   └─ cli.py
├─ families/<family>/            # ドメイン知識（docs/families.md §1 の規約）
│   ├─ family.yaml  denylist.txt  hooks.py(MAY)
│   ├─ numbering/<scheme>.yaml
│   ├─ blueprints/<doctype>.yaml
│   ├─ styles/<style_id>.yaml + styles/css/ + styles/templates/(MAY)
│   ├─ library/                  # 条文ライブラリ（オリジナル文のみ）
│   └─ docs/ (structures.md, style.md)
├─ assets/fonts/                 # 同梱フォント（yakkan と同一。SOURCES.md 必須）
├─ content/<content_id>/         # 執筆成果（doc.json, parts/*.json, source.json）。コミットする
├─ dataset/<doc_id>/ …  dataset/manifest.json   # 生成物。コミットしない・手編集禁止
├─ specs/                        # バッチ定義（content×style×seed）
├─ scripts/                      # probe_*.py, calibrate_styles.py 等（yakkan から移植）
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
  doctype 名はファミリーをまたいで一意にする（`families` コマンドが衝突を検査）。
- コミットする：`docs/` `schema/` `docsynth/` `families/` `content/` `specs/` `tests/` `assets/`。
  コミットしない：`dataset/` `scratch/` `.venv/`（`.gitignore` で除外）。
- yakkan-synth（`../insurance-contracts/`）は**読み取り専用の参照**。本プロジェクトから書き換えない。
  insurance ファミリーの同等性テストだけが `../insurance-contracts/content/` を相対パスで読む
  （存在しない環境ではスキップ）。
