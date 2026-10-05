---
paths:
  - "content/**"
  - "library/**"
  - "blueprints/**"
---

# 執筆（契約書本文）のルール

- 着手前に `docs/style_guide.md` と `docs/authoring_checklist.md`、`docs/doctypes.md` を読む。
- **番号ラベルを直書きしない**：「第1条」「(1)」「①」「ア」は build が導出する。参照は `{ref:node_id}`、脚注は `{fn:n}` ＋ 条直下の `footnotes` ブロック。
- **当事者呼称を直書きしない**：「甲」「乙」「委託者」は `{party:<key>}` で書き、build が `meta.parties` から解決する（lint L19）。表・図・別紙の番号も `{ref:}` で書く。
- **転載禁止**：`samples/` の実在ひな型の文章は、部分的にも語順を変えても書かない。生成文はすべてオリジナル。**条の並び順・列挙の順序・数値の列・様式の項目の並びも指紋になる**（`docs/style_guide.md` §2.1）。
- 固有名詞は架空のみ。URL は `example.jp` 系、電話はゼロ埋め、実在名は denylist で落とす。実在法令は名称のみで条番号は書かない。制度上の代表値（下請法の 60 日・遅延損害金 14.6% 等）は使わず架空の値にする。
- 金額・日数・期間・別紙番号は文書内で矛盾させない。`meta.constants` ＋ `{const:key}` を使う。
