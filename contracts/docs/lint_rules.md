# lint_rules.md — `keiyaku lint` の実装マップ

> CLAUDE.md §8 の一覧表に対応する実装マップと補足。ルールの重大度・一言説明は CLAUDE.md §8、
> 意味の定義は `docs/schema.md` §9 を見る。本ファイルは「**どのファイルのどの関数が検査しているか**」
> 「**実装上の注意点**」を持つ。
> 新しいルールは `keiyaku/lint/base.py` の `@rule("L##", "説明")` デコレータで登録し、
> **本ファイルと CLAUDE.md §8 の両方を更新する**。

## 実装ファイル対応表

L00〜L18 は yakkan から移植したもの（`../insurance-contracts/docs/lint_rules.md` が基底）。
「改造」列は P2 で契約書向けに手を入れる箇所。

| # | 実装ファイル | 改造（P2） | 備考 |
|---|---|---|---|
| L00 | `lint/rules.py` | `doctype` の存在検証・semantic_type の 2 層語彙 | pydantic のバリデーションエラーを Finding に変換。**実行順の先頭固定**（壊れた JSON に他ルールを走らせると誤検出するので、L00 失敗時は後続をスキップ） |
| L01 | `lint/rules.py` | `{party:}` の key を参照検査に追加 | `{ref:}` / `anchor` / `evidence` の参照先 id が `all_ids` に存在するか。`margin_note` は anchor 必須。**空文字に解決される参照も error** |
| L02 | `lint/rules.py` | **配置検査を追加（2026-09-27）** | `{fn:n}` と `footnotes.n` の双方向対応・番号の重複・未参照脚注・**脚注ブロックが `{fn:n}` より前に描かれていないか**（`_footnote_placement`）。条（祖先）に付いた脚注は条末に描かれるので見逃す |
| L03 | `lint/rules.py` | **検出パターンを numbering YAML から生成**＋**当事者 alias の直書き検出** | `{ref:}` 解決後の文字列は対象外（除外規則を必ず引き継ぐ）。alias は**単独出現のみ**を見る（「甲板」「乙種」の誤検出を避ける） |
| L04 | `lint/structure.py` | blueprint の `required` スキーマを契約書用に（`kind: node/table/figure/enumeration/ref/term`） | 種類と最小件数を集計して不足を報告。**構造で縛り semantic_type で題材を縛らない** |
| L05 | `lint/structure.py` | — | 結合展開後の列数一致、`header_rows/cols` の範囲、`records` の値が `grid` に出現 |
| L06 | `lint/rules.py` | — | 図の種別ごとに分岐（`_check_diagram`）。端点存在・格子座標重複・最小複雑度・`alt`/`facts` 非空・トークン解決 |
| L07 | `lint/rules.py` | **☑ □ ㎡ ○△× を検査対象に含める** | fontTools で `assets/fonts/` の cmap を読む。`quick=False`（`--quick` では skip）だが、**render 前には必ず走らせる** |
| L08 | `lint/rules.py` | denylist を契約書用に差し替え（実在企業・サービス・士業法人・物件名） | `example.*` 以外のドメイン、ゼロ埋め以外の電話番号も検出 |
| L09 | `lint/structure.py` | 上限を `blueprint.page_limit`（既定 12・絶対上限 20）に | 推定ページ数は `chars_per_page_estimate`（**実コーパス較正**）と `budget.chars_min/max` |
| L10 | `lint/quality.py` | tone は全 doctype `dearu`（常体）。**様式型は体言止めが多いので判定を緩める** | 文末形の統計で判定。`digit_style` の全角半角混在も見る |
| L11 | `lint/quality.py` | 頭書・別紙の値も対象に含める | `meta.constants` の宣言と `{const:key}` 参照の食い違い |
| L12 | `lint/quality.py` | **定義文の在処を追加（2026-09-27）** | `defined_terms` に無い `{term:}`、定義されたが未使用の語、**定義文が紙面のどこにも現れない語**（`_definitions_on_paper`）。照合はトークンを両側で解いてから、末尾の「〜をいう。」を落とした前方 70% で行う |
| L13 | `lint/rules.py` | meta 必須項目を契約書用に（`parties` 必須・`issuer` は任意） | 奥付 disclaimer の有無 |
| L14 | `qa/validate.py` | — | `answer_type` と `type` の対応、evidence の id・`page_hint` の整合、extract 系の answer が evidence テキストに含まれるか、`figure_path` の答えが図に実在するか |
| L15 | `lint/similarity.py` | — | `quick=False`。既存 content との文単位重複率（`--similarity` 指定時のみ） |
| L16 | `lint/qa_authored.py` | 既定を **15 問・表 3・図 2・apply 2** に。blueprint の `authored_qa` で上書き可 | 件数・観点配分・`evidence`/`question` の非空 |
| L17 | `lint/table_headers.py` | — | `header_cols`（`role: stub` の列）が行見出しを覆っているか。**`header_cols == 0` そのものを error**（yakkan で宣言漏れ 25 表が表セル F1 を壊した） |
| L18 | `lint/table_headers.py` | — | `semantic_type` が `enumeration` / `exclusions`（`build.AUTO_LABEL_TYPES`）の表に `caption` が付いていないか。付くと build が「表N」を振り、紙面に印字されるのに eval の採点対象から外れる矛盾が起きる |
| **L19** | `lint/parties.py` | 実装済み（2026-09-26） | 当事者整合。下記 §L19 |
| **L20** | `lint/parties.py`（`l20_skeleton`） | 実装済み（2026-09-26） | 契約書の骨格。下記 §L20。※ structure.py ではなく parties.py に置いた（当事者との結びつきが強く、記名欄の検査を共有するため） |
| **L21** | `lint/parties.py`（`l21_commentary`） | 実装済み（2026-09-26） | 逐条解説。下記 §L21 |
| **L22** | `lint/structure.py`（`l22_block_placement`） | 実装済み（2026-09-26） | 表・図の配置。下記 §L22 |
| **L23** | `lint/structure.py`（`l23_enumeration_nesting`） | 実装済み（2026-09-27） | 列挙の入れ子。下記 §L23 |
| **L24** | `lint/structure.py`（`l24_orphan_parts`） | 実装済み（2026-10-02） | `parts/*.json` が `doc.json` の `parts` から参照されているか。下記 §L24 |
| **L25** | `lint/quality.py`（`l25_markdown_residue`） | 実装済み（2026-10-02） | 本文に Markdown の名残（`**` `__` 等）が無いか。下記 §L25 |
| **L26** | `lint/structure.py`（`l26_positional_reference`） | 実装済み（2026-10-03） | 番号を持つ表・図を「下表」「下図」で指していないか。下記 §L26 |

## L19 当事者整合（新規・error）

`keiyaku/lint/parties.py`。検査するもの：

1. `{party:<key>}` の `key` が `meta.parties` に存在する（modifier は `name` / `full` / `role` のみ）。
2. `meta.parties` の `key` が一意、`alias` が一意、`name` が一意。
3. `parties` ブロックの `keys` が `meta.parties` の部分集合。
4. **`signature` の記名ブロックが `meta.parties` の全当事者を覆う**（漏れ・余りの両方を error）。
5. `role_label` を使う `{party:...|role}` があるなら、その当事者に `role_label` が宣言されている。
6. `{party:...|full}` が同一当事者につき **2 回以上使われていたら warn**（導入は 1 回であるべき）。
7. `alias` の**直書き**を検出（L03 と共用のパターン生成。**単独出現のみ**：
   前後が文字でない位置の「甲」「乙」「丙」など。`{ref:}` 解決後の文字列は対象外）。

**検出できないもの**：
- 甲乙の**論理の取り違え**（乙が負うべき義務を甲に書いた）。呼称が揃っていても意味は見られない。
- 呼称 1 文字＋漢字の複合（「甲側」「乙宛」）。ここを厳しくすると「甲板」「乙種」を誤検出する。
いずれも reviewer サブエージェントと目視の担当（`docs/authoring_checklist.md` §5）。

## L20 契約書の骨格（新規・error）

`keiyaku/lint/structure.py` に追加。blueprint の `skeleton_kind` に応じて検査する：

| 検査 | 対象 |
|---|---|
| `preamble` が `body` の先頭に**ちょうど 1 つ** | `skeleton_kind != "form"` の全 doctype |
| `head_matter` は `preamble` の直後にのみ置ける（0 か 1 つ） | 全 doctype |
| `signature` が `back_matter` に**ちょうど 1 つ** | 全 doctype |
| 収入印紙欄は `signature` の中にのみ置ける | `meta.stamp_duty == true` の文書 |
| `schedule` は `appendices` にのみ、`supplement` は `appendices` の末尾にのみ | 全 doctype |
| `meta.copies` が宣言されていること（後文が通数を埋めるため） | `signature` を持つ全 doctype |

## L21 逐条解説（新規・error / warn）

`keiyaku/lint/rules.py` に追加。

- `commentary` ブロックの `anchor`（対象条の id）が**存在し、`kind: article` のノードを指す**（error）。
- 同一の条に `commentary` が 2 つ以上付いていない（error）。
- 解説文が対象条の本文と**同一の文を含む**（句点区切りで完全一致する文が 1 つ以上ある）なら warn
  ——解説が本文のコピーになっている兆候。

## 実行順・実行モードの注意

- `lint/runner.py` がルールを集約する。`--quick` は `quick=False` を付けたルール（**L07・L15**）を飛ばす。
  hooks（`.claude/settings.json`）から `*.json` 保存後に自動実行されるのは quick 版。
  **L07（フォント被覆）は quick で飛ぶので、render 前に必ずフル lint を通す。**
- 新ルールは `Finding("L##", severity, message, element_id=..., path=...)` の形で yield する。
  `element_id` は id 一意なノード／ブロック、`path` はファイル内の位置（`meta.xxx` 等）。
- **error 0 / warn 0 にしてから build へ進む**（warn を残したまま進めた文書が後で作り直しになる）。

## L22 表・図の配置（新規・error）

`table` / `figure` / `formula` を**子を持つ容れ物**（`chapter` / `section` / `article` / `schedule` /
`supplement`）の `blocks` に付けると、その節の**第1項より前**に描かれる。
「下表のとおり」と書いた項が表の 2 段落あとに来るので、読み順・アンカーの QA が総崩れになる。

- 検査対象の kind は `structure._CONTAINER_KINDS`。`preamble` / `signature` は本文を持たない枠なので外す。
- **子を持たない条は見逃す**（表だけで構成する条は導入文の置きようがない）。
- `footnotes` / `box` / `parties` / `commentary` は検査しない。条の末尾に置くのが正しい位置だから。
- 直し方は「その表・図を導入する項の `blocks` へ移す」。`docs/style_guide.md` §4 に同じことが書いてある。

## L23 列挙の入れ子（新規・error）

号（`item`）を導入文と**兄弟**に並べると、numbering は同じ親の下の号を通しで数える。
条の中に列挙が 2 組あると、2 組目が `(1)` ではなく **`(7)` から**始まる。
実物の契約書は、項が変われば号を `(1)` に戻す。

- 判定：ノードの直下の子を走査し、`item` の**連なり**が 2 組以上あれば error。
- **列挙が 1 組だけなら兄弟に並べてよい**（通し番号にならないため）。
- 直し方：号を、それを導入する項の `children` に移す。numbering が親ごとに数え直す。
- `lint` も `verify` も通ったまま**目視でだけ**見つかった種類の欠陥（CLAUDE.md §0.4-7）。


## L24 置き去りの part（新規・error）

`content/<cid>/parts/*.json` は、すべて `doc.json` の `parts` から参照されていること。

- 参照されていないファイルは**書き直しの置き去り**。lint・build・render のどこにも現れないので、
  未執筆のスケルトン（`_todo` つき）が残っていても気づけない。
- 実害：`emp-0002` に scaffold 直後の 8 ファイルが残っていた（2026-10-02 に発見）。
  L04（`_todo` の残り）は**参照されている part しか見ない**ので素通りしていた。
- 直し方：消すか、`doc.json` の `parts` に入れるか。

## L25 Markdown の名残（新規・error）

本文（RichText）に `**` `__` `` ` `` が含まれていないこと。

- RichText の強調は `{b:}` `{u:}` だけで、`**強調**` は**そのまま紙面に印字される**。
  文字としては正しいので lint も verify も通り、**PNG を見るまで気づけない**。
- 実害：`sys-0002` の第3条第2項に `**みなし承諾の定めは置かない。**` が印字されていた（2026-10-02）。
- 検査対象は `rich=True` の文字列だけ（図の中の文字や `meta` は対象外）。


## L26 位置で指す言い方（新規・warn）

キャプション（＝番号）を持つ表・図は、`{ref:<block_id>}` で指す。「下表」「下図」「次の表」は使わない。

- **版面が変われば嘘になる**：実際に別紙の表が次ページへ送られ、「下表」が前ページに取り残された。
- **同じものの呼び方が揺れる**：同じ表を一方では「下表」、他方では `{ref:}`（＝「表1」）と呼ぶ状態が
  20 content のうち 15 content にあった（2026-10-02 の盲検で読み手が指摘）。
- **キャプションを持たない表は対象外**：列挙用に組んだ表（`semantic_type: enumeration` ほか。L18 が
  caption を禁じる）は番号が無いので「下表」でよい。`{ref:}` は解決できない。
