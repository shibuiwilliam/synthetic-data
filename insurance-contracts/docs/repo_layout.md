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
├─ content/<content_id>/ (doc.json, parts/*.json, source.json)
├─ dataset/<doc_id>/ …  dataset/manifest.json
├─ specs/batch_v1.yaml           # 生成バッチ定義（content×style×seed）
├─ tests/ (unit + golden)
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
