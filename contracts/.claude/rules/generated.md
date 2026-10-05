---
paths:
  - "dataset/**"
  - "schema/**"
---

# 生成物を手で編集しない

- `dataset/` 配下（source.json / layout.json / answer.json / qa.json / doc.pdf / pages/）と `schema/*.schema.json` は生成物。**手編集は禁止**（CLAUDE.md §0.4-3）。
- 直したいときは入力（`content/<cid>/parts/`、`blueprints/`、`numbering/`、`styles/`、`keiyaku/`）を直し、`keiyaku build` → `render` → `verify` で作り直す。
- `schema/` は `uv run keiyaku schema export` の出力。モデル（`keiyaku/models.py`）を直してから再生成する。
