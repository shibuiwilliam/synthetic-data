# lint_rules.md — `docsynth lint` の実装マップ

> CLAUDE.md §8 の一覧表に対応する実装マップ。ルールの重大度・一言説明は CLAUDE.md §8、
> 意味の定義は `docs/schema.md` §9 を見る。本ファイルは「**どのファイルのどの関数が検査しているか**」
> 「**実装上の注意点**」「**コアとファミリーの分担**」を持つ。
>
> 新しいルールは `docsynth/lint/base.py` の `@rule("L##", "説明")` デコレータで登録し、
> **本ファイルと CLAUDE.md §8 の両方を更新する**。
> **新設は L27 以降**（L00–L26 は姉妹と番号・意味を互換に保つ）。ファミリー内で済むものは FLxx。
> 基底：`../insurance-contracts/docs/lint_rules.md`（L00–L18）＋`../contracts/docs/lint_rules.md`（L19–L26）。
>
> - 版: 1.0（2026-10-05 新設）

## 0. 設計の原則

1. **文章で書いた基準は守られない。** 執筆・正解の要件は可能な限りここに落とす
   （yakkan S1：30 content のうち 13 が執筆 QA 基準に違反していた。keiyaku の L22〜L26 はすべて
   「目視でしか見つからなかった欠陥」の機械化である）。
2. **規則はコア、要件値はファミリー。** 「`preamble` が body 先頭に 1 つ」という**検査**はコアが持ち、
   「このファミリーは preamble を要求するか」という**要件**は `family.yaml` が宣言する（L04・L10・L13・L16・L20）。
3. **構造で縛り、題材で縛らない。** `required_elements` は構造（ノード種別・件数）で書く。
   `semantic_type` を必須にすると**執筆者が型を偽る誘因**になる（yakkan D4）。
4. **過検出は害。** L03 の自動生成パターンは `{ref:}` 解決後の文字列を対象外にし、
   当事者 alias は**単独出現のみ**を見る（「甲板」「乙種」で誤検出しない）。
5. `--quick`（保存フック用）では重い検査（L07 フォント被覆・L15 類似度）を飛ばすが、
   **render の前には必ず全部走らせる**。

## 1. 実装ファイル対応表

「ファミリー依存」列が ✓ のものは、要件値を `family.yaml` から読む（P1 の作業）。

| # | 実装 | ファミリー依存 | 実装上の注意 |
|---|---|---|---|
| L00 | `lint/rules.py` | ✓（family / doctype / semantic_type / family_ext） | pydantic のバリデーションエラーを Finding に変換。**実行順の先頭固定**（壊れた JSON に他ルールを走らせると誤検出するので、L00 失敗時は後続をスキップ）。執筆物への `derived` 混入もここ |
| L01 | `lint/rules.py` | — | `{ref:}` / `anchor` / `evidence` / `{party:}` の参照先が `all_ids`・`meta.parties` に存在するか。`margin_note` は anchor 必須。**空文字に解決される参照も error** |
| L02 | `lint/rules.py` | — | `{fn:n}` と同一条の `footnotes.n` の双方向対応・番号重複・未参照脚注・**脚注ブロックが `{fn:n}` より前に描かれていないか**。条（祖先）に付いた脚注は条末に描かれるので見逃しやすい |
| L03 | `lint/rules.py` | ✓（検出パターンの生成元） | **numbering YAML の `format` から検出正規表現を自動生成**（「第N条」「（N）」「①」「第十二条」「イ」をハードコードしない）＋**当事者 alias の直書き検出**。`{ref:}` 解決後の文字列は対象外。alias は単独出現のみ |
| L04 | `lint/structure.py` | ✓（`required_elements`） | 宣言ルール（`require_block` / `min_count` / `min_rows` / `kind: node\|table\|figure\|enumeration\|ref\|term`）として解釈。**構造で縛り semantic_type で題材を縛らない** |
| L05 | `lint/structure.py` | — | 結合展開後の列数一致、`header_rows/cols` の範囲、`records` の値が `grid` に出現。幅は格子の位置数で数える |
| L06 | `lint/rules.py` | — | 図の種別ごとに分岐。端点存在・格子座標重複・最小複雑度・`alt`/`facts` 非空・トークン解決（`resolved_labels`） |
| L07 | `lint/rules.py` | ✓（記号の追加） | fontTools で `assets/fonts/` の cmap を読む。**`■ □ ㎡ ○ △ ×` と丸数字を含める**。`--quick` では skip だが **render 前には必ず走らせる** |
| L08 | `lint/rules.py` | ✓（denylist） | コア共通 `lint/denylist_common.txt` ＋ `families/<f>/denylist.txt`。`example.*` 以外のドメイン、ゼロ埋め以外の電話番号も検出 |
| L09 | `lint/budget.py` / `structure.py` | ✓（`page_limit`） | 上限は blueprint → family.yaml の `default_page_limit` → 20（絶対）。推定は `chars_per_page_estimate`（**実コーパス較正**）と `budget.chars_min/max`。目標超過は warn・絶対上限超過は error |
| L10 | `lint/quality.py` | ✓（tone） | 文末形の統計で敬体／常体を判定。`digit_style` の全角半角混在も見る。**条を持たない様式型は体言止めが多いので判定を緩める** |
| L11 | `lint/quality.py` | — | `meta.constants` の宣言と `{const:key}` 参照の食い違い。**頭書・別紙・図・算式の値も対象** |
| L12 | `lint/quality.py` | — | `defined_terms` に無い `{term:}`、定義されたが未使用の語、**定義文が紙面のどこにも現れない語**。照合はトークンを両側で解いてから、末尾の「〜をいう。」を落とした前方 70% で行う |
| L13 | `lint/rules.py` | ✓（meta 必須項目） | 奥付 disclaimer の有無＋ファミリーごとの meta 必須（contract は `parties` 必須・`issuer` 任意、terms/statute は逆） |
| L14 | `qa/validate.py` | — | `answer_type` と `type` の対応、evidence の id・`page_hint` の整合、extract 系の answer が evidence テキストに含まれるか、`figure_path` の答えが図に実在するか。**`apply` の算出値は検査できない**（`docs/validation_plan.md` §5.1） |
| L15 | `lint/similarity.py` | — | 既存 content との文単位重複率（`--similarity` 指定時のみ）。30% 超で warn |
| L16 | `lint/qa_authored.py` | ✓（`authored_qa`） | 件数・観点配分・`evidence`/`question` の非空。既定 15 問・表 3・図 3・apply 1。**contract は図 2・apply 2** |
| L17 | `lint/table_headers.py` | — | `header_cols`（`role: stub` の列）が行見出しを覆っているか。**`header_cols == 0` そのものを error**（yakkan で宣言漏れ 25 表が表セル F1 を壊した） |
| L18 | `lint/table_headers.py` | — | `semantic_type` が `enumeration` / `exclusions`（`build.AUTO_LABEL_TYPES`）の表に `caption` が付いていないか。付くと build が「表N」を振り、紙面に印字されるのに eval の採点対象から外れる矛盾が起きる |
| **L19** | `lint/parties.py` | — | 当事者整合。§2 |
| **L20** | `lint/parties.py` | ✓（`skeleton:`） | 文書の骨格。§3 |
| **L21** | `lint/parties.py` | — | 逐条解説。§4 |
| **L22** | `lint/structure.py` | — | 表・図の配置。§5 |
| **L23** | `lint/structure.py` | — | 列挙の入れ子。§6 |
| **L24** | `lint/structure.py` | — | 置き去りの part。§7 |
| **L25** | `lint/quality.py` | — | Markdown の名残。§8 |
| **L26** | `lint/structure.py` | — | 位置で指す言い方。§9 |
| **L27–** | （空） | — | 本プロジェクトの新設枠 |
| FLxx | `lint/runner.py` が family 宣言を解釈 / `families/<f>/hooks.py` | ファミリー定義 | 宣言ルールで書けるものは `family.yaml` の `lint:` に、書けないものだけフックに。**フックを使ったら理由を decisions に記録** |

## 2. L19 当事者整合（error）

- `{party:<key>}` の key がすべて `meta.parties` に存在する（L01 と重複して検査する。壊れた参照は両方で落ちる）。
- **当事者表示（`parties` ブロック）・前文・本文・記名押印欄（`signature`）で呼称と名称が一致**する。
  `meta.parties` を唯一の出所とし、どれか 1 つでも独自の文字列を持っていたら error。
- `|full` 形（「株式会社◯◯（以下「甲」という。）」）は**当事者表示と前文でのみ**使える。
  本文で使うと同じ導入が 2 回現れる。
- **検出できないもの**：論理の取り違え（甲がすべき義務が乙になっている）。
  これは reviewer サブエージェントと目視の担当（`docs/authoring_checklist.md` §5）。

## 3. L20 文書の骨格（error）

検査はコア、**要件は `family.yaml` の `skeleton:` が宣言**する（`docs/architecture.md` §3）。

- `preamble` が body 先頭に 1 つ（`except_doctypes` に挙げた doctype は持たない＝持つと error）。
- `signature` が back_matter に 1 つ、記名欄が `meta.parties` の全当事者を覆う。
- 収入印紙欄・契約日は `signature` の中だけに置ける。
- `head_matter` は body の先頭（`preamble` の次）に 1 つまで。

## 4. L21 逐条解説（error / warn）

- `commentary` ブロックは対象条の `anchor` を持ち、その id が実在する（欠落・切れは error）。
- **本文との文の重複が閾値を超えたら warn**（解説が条文の言い換えになっていると、
  検索の gold が二重になり評価が壊れる）。

## 5. L22 表・図の配置（error）

`table` / `figure` / `formula` は**導入文を持つ項（`paragraph`）の `blocks`** に付ける。
`article` や `chapter` の直下に置くと**第1項より前に描画され**、読み順・アンカーの QA が壊れる。

## 6. L23 列挙の入れ子（error）

同じ親の下に号（`item`）の並びが 2 組以上あるなら、号は**それを導入する項の `children`** に入れる。
兄弟に平らに並べると、条の中で号が通し番号になり「(1)〜(5) と (1)〜(3)」が「(1)〜(8)」になる。

## 7. L24 置き去りの part（error）

`content/<cid>/parts/*.json` はすべて `doc.json` の `parts` から参照されていること。
書き直しの置き去りは**未執筆のまま誰にも見えない**（紙面にも出ず lint も通る）。

## 8. L25 Markdown の名残（error）

本文の RichText に `**` `__` `` ` `` を書かない（強調は `{b:}` `{u:}`）。
**`**` はそのまま紙面に印字される**（keiyaku で実際に印字されていた）。
コードブロックや URL の中の記号は対象外にする（過検出を避ける）。

## 9. L26 位置で指す言い方（warn）

番号を持つ表・図を「下表」「下図」「上表」「次の表」で指さない（`{ref:}` を使う）。
**版面が変われば嘘になる**（1 content を複数 style で描くのが本プロジェクトの前提なので致命的）。
番号の無い列挙表（L18 で caption を付けないもの）は対象外。

## 10. 実行順・実行モード

```
L00（失敗したら打ち切り） → L01〜L09 → L10〜L13 → L14（qa/validate） → L16〜L26
                                        └ L15・L07 は --quick で skip
```

- `docsynth lint content/<cid>` は執筆物（SourceDraft）を見る。`derived` を前提にする検査
  （L11 の一部・L12 の紙面照合）は build 後の `source.json` を読む。
- **保存フック**（`.claude/settings.json`）は `--quick`。**執筆プロトコルの `lint` は全部**。
- lint が error 0 でも通らない欠陥がある（`docs/authoring_checklist.md`）。
