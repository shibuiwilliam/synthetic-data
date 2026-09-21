---
paths:
  - "content/**"
  - "library/**"
  - "blueprints/**"
---

# 執筆（約款本文）のルール

- 着手前に `docs/style_guide.md`（旧 §7）と `docs/blueprints.md`（旧 §4.1）を読む。
- **番号ラベルを直書きしない**：「第１条」「（２）」「①」は build が導出する。参照は `{ref:node_id}`、脚注は `{fn:n}` ＋ 条直下の `footnotes` ブロック。
- **転載禁止**：参考URLの実在約款の文章は、部分的にも語順を変えても書かない。生成文はすべてオリジナル。
- 固有名詞は架空のみ。URL は `example.jp` 系、電話は `0120-000-000` 系のゼロ埋め、実在社名は denylist で落とす。実在法令は名称のみで条番号は書かない。
- 金額・日数・等級・別表番号は文書内で矛盾させない。`meta.constants` ＋ `{const:key}` を使う。
