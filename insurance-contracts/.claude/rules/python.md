---
paths:
  - "**/*.py"
---

# Python コーディング規約（CLAUDE.md §13）

- Python 3.12 / uv。`ruff`（format + lint）に通す。型ヒント必須。
- pydantic モデルの外で dict を裸で回さない。
- 乱数は `random.Random(seed)` を明示的に受け渡す。`datetime.now()` を生成物に入れない（決定論、CLAUDE.md §0.4-4）。
- 識別子は英語、コメント・docstring・ユーザー向け文字列は日本語可。ログは `logging`、CLI は `typer`。
- コミット前に `make check`（ruff + pytest）を通す。
