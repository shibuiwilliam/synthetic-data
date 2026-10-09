# schema.md — データモデル（正解JSON）

> `keiyaku/models.py` / `build.py` / `richtext.py` / `schema/` / `content/` / `dataset/` を触る作業では、
> **着手前に必ず本ファイルを読む**こと。仕様変更は実装より先に本ファイルを直し、`docs/decisions.md` に記録する。
>
> **基底仕様＝`../insurance-contracts/docs/schema.md`。** 本ファイルはそこからの**差分だけ**を書く。
> ここに書かれていない事項（RichText の文法、表の `grid`／`records`、図 6 種の形、`layout.json` の構造、
> `qa.json`、parts 形式）は基底仕様のとおり。**基底仕様も必ず開くこと**（本ファイルだけでは実装できない）。
> 型の正本は `keiyaku/models.py`、機械可読版は `schema/*.schema.json`（`keiyaku schema export`）。
> 設計は `../structured-docs/docs/schema.md`（docsynth の contract ファミリー設計）と整合させる。

## 1. 検証対象（基底仕様と同一の 6 観点）

テキスト／条項構造／表／図／参照関係／QA。正解表現の対応表は基底仕様 §1.1。
契約書では**参照関係**に「当事者呼称」（甲＝どの法人か）と「別紙参照」が加わるのが特徴（§4・§5）。

### 1.1 基底仕様（2026-09-21 の写し）の確定後に yakkan へ入った拡張

**すべて v1 仕様の一部である。** 基底の schema.md には書かれておらず、`../insurance-contracts/docs/` の
`blueprints.md`・`decisions.md`・`remaining_issues.md` に散っているため移植時に見落としやすい。

| 拡張 | 内容 | 契約書での使いみち |
|---|---|---|
| `Node.kind: "rider"` | **番号を持たない**節点。中の条は 1 から振り直し、`{ref:}` は題名で解決 | `head_matter`・`signature` の機構の土台（§5） |
| `Node.badges` | 見出し右の分類ラベル。`<node_id>__badge<i>` の独立要素として `plain_text` と layout に載る | 様式型の「※記入必須」等（MAY） |
| `Node.kind_label` | 別表の呼び名（「別表」「付表」「別紙」）。**番号は呼び名ごとに振る** | 「別紙1」「別表1」「様式第1号」の 3 系統を混在させられる |
| `meta.article_heading` | `inline`（第1条（見出し））／ `above`（見出しを条の上に括弧書き＋条ラベルが本文へ走り込む。`LabelInfo.run_in_label`）／ `plain` | 契約書は `inline` が既定。約款型で `above` を使う variant |
| `meta.footnote_style` | `inline`（(*n)）／ `remarks_box`（❶＋「第N条　備考」枠） | 約款型の備考欄 |
| `meta.caption_numbering` | `flat`（表1）／ `chapter`（表1-1。**章に属さない表・図には番号を振らない**） | 章立てのある `sysdev` / `contracting` で `chapter` |
| 表・図への `{ref:}` | キャプションのある表・図は `{ref:tbl_x}` →「表2」。**素の「表2」直書きは禁止** | 報酬表・実施料表の参照 |
| 図・算式内トークン | `{const:}` `{term:}` `{ref:}` `{party:}` を build が解決し `derived.figures[].resolved_labels` に記録。**紙面に出るのは解決後の文字列**。一覧に無いトークンは L06 がエラーにする（生のまま SVG に出るのを防ぐ） | 検収フロー内の日数を `{const:}`、判断の主体を `{party:}` で書く |
| 図の正規化グラフ | 6 種共通の `derived.figures[].graph`（nodes / edges / role）と全種の `paths` | 図の評価の土台 |
| 構造位置 | `derived.labels[]` に `kind` / `parent_id` / `path_ids` / `citation`（「第4条 2 (1)」＝番号だけを連ねた紙面表記）。outline・toc にも同じ 4 つ | 契約書は条が通し番号なので citation に章を冠さない |
| 列挙の親子 | `derived.enumerations[]`（列挙表・号ノード・箇条書きの 3 系統を共通の形で） | 禁止事項・免責事由の列挙 |
| `answer.json` のスリム化 | `source` / `layout` を**内包しない**（`load_answer(dir)` で結合）。42MB→5.3MB の実績 | そのまま |
| `outline` の範囲 | **番号のある項も入れる**。ラベルも見出し文言も持たない節点（条の最初の項）は**外す** | そのまま（入れないと F1 が 0.58 → 0.98 になった実測） |
| `elements.jsonl` ほか評価向け成果物 | 1 行 1 要素の平索引・検索評価セット・予測スキーマ。すべて pydantic（`export_models.py`）から schema export | そのまま |
| lint L16 / L17 / L18 | 執筆 QA の配分強制／`header_cols` の宣言漏れ（0 も error）／列挙用の表への caption 禁止 | そのまま |

## 2. source.json のトップレベル差分

```ts
type Source = {
  schema_version: "2.0";           // keiyaku / docsynth 系は 2.x（yakkan は "1.0"）
  content_id: string;              // 例 "nda-0001"（<doctype>-NNNN）
  family: "contract";              // 固定値。docsynth へ切り出すときの受け皿（docs/architecture.md §6）
  doctype: string;                 // 例 "nda"。blueprints/<doctype>.yaml が存在すること（lint L00）
  seed: number;
  meta: Meta;                      // §3
  front_matter: FrontMatter;       // cover・toc はいずれも MAY（契約書は表紙も目次も持たないのが普通）
  defined_terms: TermDef[];        // 基底仕様と同一
  body: Node[];                    // preamble → （章）→ 条 … の順
  appendices: Node[];              // 別紙・別表・様式・附則（kind: appendix / supplement）
  back_matter: BackMatter;         // signature（§5）＋ colophon（disclaimer 必須）
  derived?: Derived;               // build が付与。執筆物（SourceDraft）に書くと L00 で落ちる
};
```

- 基底仕様からの改名：`genre` → `family`（固定値）＋ `doctype`。`numbering_scheme` は `meta` に残る。
- `front_matter.toc` の有無は blueprint が宣言する。**目次なしの文書では verify が目次検査を
  スキップした旨をレポートに明記する**（V-P3。黙って通さない）。

## 3. meta の差分

```ts
type Meta = {
  title: string;                   // 「業務委託契約書」「秘密保持契約書」「労働条件通知書」
  subtitle?: string;
  parties: PartyDef[];             // §4。契約書では**必須**（2 者以上）
  issuer?: Issuer;                 // 様式型で「交付者」を単独名義で示す場合のみ（MAY）
  contract_date?: string;          // 契約締結日 "2026-04-01"（記名押印欄の日付として描画）
  effective_date?: string;         // 効力発生日（締結日と異なる場合）
  term?: string;                   // 契約期間の表示用文字列。値は {const:} 由来にする
  contract_number?: string;        // 契約書番号（架空）。style により右上に描画
  form_code?: string;              // 様式番号（架空。「様式第1号」等）
  numbering_scheme: string;        // "contract-standard" | "contract-form"（numbering/*.yaml のファイル名）
  digit_style: "fullwidth" | "halfwidth";
  article_heading?: "inline" | "above" | "plain";   // §1.1（既定 inline）
  footnote_style?: "inline" | "remarks_box";        // §1.1（既定 inline）
  caption_numbering?: "flat" | "chapter";           // §1.1（既定 flat）
  copies?: number;                 // 原本の通数（後文「本書2通を作成し」の 2。build が後文へ埋める）
  stamp_duty?: boolean;            // 収入印紙欄を描くか（既定 false）
  disclaimer: string;              // 架空である旨。末尾（colophon）に必ず描画
  constants?: { [key: string]: string };   // {const:key} で参照。数値整合 L11 の土台
};
```

- **`meta.parties` は契約書では必須**（`employment` の様式型でも「事業主」「労働者」の 2 者を持つ）。
- `copies` / `stamp_duty` を `meta` に置くのは、後文と収入印紙欄の**文字列を build が導出する**ため
  （執筆者が「本書2通を作成し」と書くと `copies` と食い違いうる。§5 の `signature` 参照）。

## 4. 当事者（PartyDef と `{party:}` トークン）— 新設

契約書の「甲・乙」問題を番号ラベルと同じ発想で解決する：**執筆者は呼称を直書きせず、トークンで参照し、
build が解決する**。呼称の揺れ・取り違えを構造的に排除する。

```ts
type PartyDef = {
  key: string;                     // "client" | "vendor" | "guarantor" など英語 slug。{party:client} で参照
  alias: string;                   // 紙面上の呼称：「甲」「乙」「丙」「委託者」「借主」「事業主」…
  name: string;                    // 架空の正式名称「株式会社青葉システムズ」
  address?: string;                // 架空住所（記名押印欄・頭書で使用）
  representative?: string;         // 架空の代表者名（記名押印欄で使用）
  role_label?: string;             // 当事者表示での役割名「委託者」（alias と別に持つ場合）
};
```

| 書き方 | 解決結果 | 使える場所 |
|---|---|---|
| `{party:client}` | `alias`（「甲」） | どこでも |
| `{party:client|name}` | 正式名称（「株式会社青葉システムズ」） | 前文・当事者表示・記名押印欄・頭書 |
| `{party:client|full}` | 「株式会社青葉システムズ（以下「甲」という。）」 | **前文・当事者表示でのみ**（2 回以上使うと L19 が warn） |
| `{party:client|role}` | `role_label`（「委託者」） | 当事者表示・頭書・表の見出し |

- 解決結果は `derived.party_uses[]`（`{ element_id, key, modifier, rendered }`）に記録する。
- **`meta.parties` の順序が「甲・乙・丙」の順序**。`alias` を YAML で明示するので、
  variant で「委託者・受託者」型に切り替えても本文は 1 文字も変わらない（`{party:}` のまま）。
- lint L19：key の存在、当事者表示・前文・本文・記名押印欄での呼称と名称の一致、
  **`alias` の直書き検出**（「甲」「乙」を生文字列で書くと error。検出語は `meta.parties` から生成するので
  「甲」を含む一般語（「甲板」等）が誤検出されないよう**単独出現のみ**を対象にする）。

## 5. Node / Block の追加種別

基底仕様の kind（part / chapter / rider / section / article / paragraph / item / subitem / subsubitem /
appendix / appendix_section）に加えて：

| kind | 用途 | 番号 | 置き場所 |
|---|---|---|---|
| `preamble` | 前文（「◯◯（以下「甲」という。）と△△（以下「乙」という。）とは、…次のとおり契約を締結する。」） | 無番号 | `body` の**先頭にのみ** 1 つ（L20） |
| `head_matter` | **頭書**（冒頭の一覧表。物件の表示・契約期間・賃料・当事者を表で示す。賃貸借標準契約書型） | 無番号。`{ref:}` は「頭書」で解決（`rider` と同じ機構） | `body` の preamble の直後 |
| `signature` | 後文＋契約日＋記名押印欄（＋収入印紙欄） | 無番号 | `back_matter` に 1 つ（L20） |
| `appendix` | 別紙・別表・様式（仕様書・物件目録・料金表・記入様式） | `kind_label` ごとに独立採番（「別紙1」「別表1」「様式第1号」） | `appendices` |
| `supplement` | 附則（適用開始・経過措置）。長い契約・約款型のみ | 「附則」＋項番号 | `appendices` |

Block の追加：

| type | 用途 | 描画 |
|---|---|---|
| `parties` | 当事者表示（「委託者：株式会社◯◯／受託者：△△株式会社」）。`keys: string[]` で `meta.parties` を参照 | style の `parties_style: table | lines`。文字列はすべて `meta.parties` から導出 |
| `revision_history` | 改定履歴（`entries: { date, note }[]`）。semantic_type は `history` | 表として描画。位置は blueprint の `revision_history.position` |
| `commentary` | **逐条解説**（モデル契約書の解説枠）。`anchor`（対象条の id）必須、`text: RichText[]` | 対象条の直後に枠つきで描画。`region: "commentary"` として layout に載る（P5・§11.3） |

- `signature` の中身は**すべて `meta` から導出する**：後文（`copies` を埋める）／契約日（`contract_date`）／
  当事者ごとの記名ブロック（`name`・`address`・`representative`＋「印」）／収入印紙欄（`stamp_duty`）。
  執筆者は後文の言い回しだけを選ぶ（blueprint の `closing_options` から）。
- 記名押印欄は**枠と「印」の文字のみ**。印影画像・手書き風は作らない（CLAUDE.md §15）。
  各記名行にも id を振り、bbox を `layout.elements` に載せる（読み取り正解に含める）。
- `head_matter` の中身は `Table`（`semantic_type: head_matter`）1 つ以上。**頭書に書いた値は
  `{const:}` 経由**にし、本文の「頭書に記載の賃料」と一致させる（L11）。

### 5.10 記法サンプル（契約書の 1 条ぶん）

**この節の JSON は `tests/golden/test_schema_sample.py` が読み取って検査する。**
記法を変えたらここを直せば、テストが自動で追従する。1 条の中に、契約書で使う記法を一通り入れてある：

| 記法 | この見本での使い方 |
|---|---|
| `{party:<key>}` | 当事者の呼称。**「甲」「乙」を直書きしない**（L19） |
| `{term:<id>}` | 定義語。定義文そのものは紙面に出ないので、別に定義条か定義表を置く（L12） |
| `{const:<key>}` | 文書内で揃えたい数値。`meta.constants` に宣言する（L11） |
| `{ref:<id>}` | 条項間参照。番号は build が解決する（L03） |
| `{fn:n}` ＋ `footnotes` | 条末脚注。**ブロックは参照より後ろの項に付ける**（L02） |
| `{auto_label}` | 列挙表の自動採番。`semantic_type: exclusions` の表に付ける（L18 が caption を禁じる） |

号（`item`）は**導入する項の `children`** に入れてある。兄弟に並べると条の中で通し番号になる（L23）。

```json
{
  "id": "ch4_s1_a2",
  "kind": "article",
  "title": "秘密情報の取扱い",
  "children": [
    {
      "id": "ch4_s1_a2_p1",
      "kind": "paragraph",
      "text": "{party:receiver}は、{party:discloser}から開示された{term:confidential}を{term:purpose}のためにのみ使用し、{party:discloser}の書面による事前の承諾を得ないで第三者に開示してはならない。"
    },
    {
      "id": "ch4_s1_a2_p2",
      "kind": "paragraph",
      "text": "{ref:ch4_s1_a2_p1}の承諾を求められた{party:discloser}は、求めを受けた日から{const:notice_days}以内に諾否を回答する{fn:1}。",
      "children": [
        {
          "id": "ch4_s1_a2_p2_i1",
          "kind": "item",
          "text": "回答は書面により行う"
        },
        {
          "id": "ch4_s1_a2_p2_i2",
          "kind": "item",
          "text": "期間内に回答がないときは、承諾しなかったものとみなす"
        }
      ]
    },
    {
      "id": "ch4_s1_a2_p3",
      "kind": "paragraph",
      "text": "次に掲げる情報は、{term:confidential}に含まれない。",
      "blocks": [
        {
          "type": "table",
          "id": "tbl_exclusions_sample",
          "semantic_type": "exclusions",
          "layout": {
            "header_rows": 0,
            "header_cols": 1,
            "repeat_header": false,
            "style": "grid"
          },
          "grid": [
            [
              {
                "id": "tbl_exclusions_sample__r0c0",
                "text": "{auto_label}",
                "role": "stub"
              },
              {
                "id": "tbl_exclusions_sample__r0c1",
                "text": "開示を受けた時点で既に公知であった情報",
                "role": "body"
              }
            ],
            [
              {
                "id": "tbl_exclusions_sample__r1c0",
                "text": "{auto_label}",
                "role": "stub"
              },
              {
                "id": "tbl_exclusions_sample__r1c1",
                "text": "{party:receiver}が独自に開発した情報",
                "role": "body"
              }
            ]
          ]
        }
      ]
    },
    {
      "id": "ch4_s1_a2_p4",
      "kind": "paragraph",
      "text": "{ref:ch4_s1_a2_p1}の義務は、本契約が終了した日から{const:survival_years}存続する。{term:deliver_medium}の返還が完了するまでの間も同様とする。",
      "blocks": [
        {
          "type": "footnotes",
          "id": "fn_ch4_s1_a2_sample",
          "notes": [
            {
              "n": 1,
              "text": "回答の方法は{ref:ch4_s1_a2_p2}の号による。"
            }
          ]
        }
      ]
    }
  ]
}
```

**前文（`preamble`）・記名押印欄（`signature`）はこの見本に含めない。**
どちらも中身の大半を `meta` から導出する枠であり、執筆者が書くのは後文の言い回しだけだから
（§5 の表と `blueprints/*.yaml` の `closing_options` を見る）。


## 6. 表の semantic_type — 2 層語彙

```
コア共通語彙（models.py）:
  definitions / enumeration / exclusions / rate / plan_matrix / procedure / mapping / history / generic
契約書の登録語彙:
  fee_schedule    報酬・委託料・賃料・共益費の表
  deliverables    成果物・納入物・仕様・作業範囲の一覧
  inventory       目的物・物件・貸与品の目録（売買の目録、賃貸の物件表示）
  head_matter     頭書（§5）
  form_fields     様式の記入欄（項目 × 記載内容。労働条件通知書の本体）
  allocation      費用・修繕・責任の分担表（項目 × 当事者。○△× の凡例つき）
```

- lint L00 は「コア共通 ∪ 契約書登録語彙」以外を error にする。
- `grid`＋`records`／`header_path` の二重表現、`{auto_label}`、`blocks_side_by_side` は基底仕様のとおり。
- **`semantic_type` は正解データの一部**。blueprint の必須要素を満たすために型を偽らせない
  （必須要素は**構造で縛り、semantic_type で題材を縛らない**——yakkan D4 の教訓）。
- **列挙用の表（enumeration / exclusions）に `caption` を付けない**（L18）。付けると build が「表N」を振り、
  紙面に印字されるのに eval の採点対象から外れる矛盾が起きる（yakkan Z2 で実証）。
- `form_fields` の表は**行見出し（`role: stub`）が項目名**になる。`header_cols` の宣言を忘れると
  表セル F1 が壊れる（L17 が `header_cols == 0` を error にする）。

## 7. numbering の宣言化（`numbering/<scheme>.yaml`）

yakkan の 5 方式（Python 直書き）を宣言に置き換える。解釈器は `keiyaku/numbering.py`。

### 7.1 `contract-standard`（条文型・約款型・頭書型で共通）

```yaml
scheme: contract-standard
levels:
  chapter:    { format: "第{n}章", counter: arabic, heading: "{title}" }     # 章を持つ doctype のみ
  article:    { format: "第{n}条", counter: arabic, heading: "（{title}）" }
  paragraph:  { format: "{n}",    counter: arabic, skip_first: true }        # 第1項は無番号
  item:       { format: "({n})",  counter: arabic }                          # 号
  subitem:    { format: "{n}",    counter: katakana }                        # ア イ ウ
  subsubitem: { format: "({n})",  counter: paren_katakana }                  # (ｱ) (ｲ)
  appendix:   { format: "{kind_label}{n}", counter: arabic }                 # 別紙1 / 別表1 / 様式第1号
  supplement: { format: "附則",    counter: none }
counters_available: [arabic, circled, katakana, paren_katakana, roman]
digit_style_from_meta: true       # 全角/半角は meta.digit_style に従う
continuous_articles: true         # 条は章ごとに振り直さず全編通し（契約書の標準）
paragraph_ref_style: written      # 印字が無番号でも参照は「第1項」「第1項第4号」と書き下す
ref_resolution:
  article_with_title: true        # 他条参照は「第4条（機密情報の返還）」
  same_article_paragraph: "第{n}項"
  no_chapter_prefix: true         # 通し番号なので {ref:} に章を冠さない
```

### 7.2 `contract-form`（様式型＝労働条件通知書。**条を持たない**）

```yaml
scheme: contract-form
levels:
  chapter:    { format: "{n}",    counter: arabic, heading: "{title}" }      # 「1 労働契約の期間」
  article:    { format: "({n})",  counter: arabic, heading: "{title}" }      # 「(1) 始業・終業の時刻」
  paragraph:  { format: "{n}",    counter: circled }                         # ① ②
  item:       { format: "{n}",    counter: katakana }
  appendix:   { format: "{kind_label}{n}", counter: arabic }
continuous_articles: false
paragraph_ref_style: printed
ref_resolution: { article_with_title: true, no_chapter_prefix: false }
```

- **`kind` は紙面の記号ではなく構造の深さ**（基底仕様・評価語彙と同じ規約）。様式型でも、いちばん外の区分が
  `chapter`、本文を持つ単位が `article`、その中の列挙が `item`。yakkan の `jyusetsu` と同じ扱い。
- yakkan で判明済みの一般規則を宣言に含める：
  - `continuous_articles` では `{ref:}` に章を冠さない。
  - 第1項が無番号の方式では、項・号への参照を「第N項」「第N号」と**書き下す**
    （印字どおりに連ねると空文字に解決される。yakkan group で 18 件の実害）。
  - 附則の中を指す参照は「附則第3」のように祖先ラベルを冠する。
- L03（ラベル直書き禁止）の検出正規表現は、**導入済みスキームの `format` から自動生成**する
  （「第N条」「(N)」「①」をハードコードしない）。`{ref:}` 解決後の文字列は対象外にする除外規則を必ず引き継ぐ。
- **P2 の golden**：2 方式が全 kind × 位置で期待どおりのラベルと `{ref:}` 解決文字列を出すこと。
  加えて yakkan の `nonlife` を YAML で書き下し、yakkan の `numbering.py` と同一出力になることを確かめる
  （**解釈器の表現力の検証**。一致しなければ宣言スキーマが足りていない）。

## 8. derived / answer.json / qa.json / 評価向け成果物

基底仕様＋§1.1 のとおり。差分は次のみ：

- `derived.party_uses[]`（§4）。
- `derived.labels[].citation` は章を冠さない（「第4条 2 (1)」）。様式型は「1 (2) ①」。
- `answer.json` は `source` / `layout` を内包しない（`keiyaku.answer.load_answer(dir)` で結合）。
- `answer.json.outline` は追加 kind（preamble / head_matter / signature / appendix / supplement）も含む。
  ただし**ラベルも見出し文言も持たない節点は outline に入れない**（yakkan T7）。
- QA 種別は基底仕様の 11 種（`apply` 含む）を継承。契約書では
  `table_lookup`＝報酬表・実施料表、`crossref`＝「第10条が引用する別紙はどれか」、
  `apply`＝「納品日と検査期間から検収期限を導く」「解約通知日から契約終了日を導く」が書きやすい。
  **doctype 独自の QA 型は追加しない**（v1）。
- bbox は pt・原点左上を主とし、正規化 [0,1] を併記。

## 9. lint 規則

**yakkan の最終形 L00–L18 を番号・意味とも互換で継承し、L19–L21 を新設**する（一覧は `docs/lint_rules.md` §1、
実装位置と検査ロジックは `docs/lint_rules.md`）。基底仕様からの実装上の変更点：

- **L00**：`doctype` の存在検証（`blueprints/<doctype>.yaml` があること）、semantic_type の 2 層語彙検証。
- **L03**：検出パターンを numbering YAML から生成（§7）。**当事者 alias の直書き検出を追加**（§4）。
- **L04**：blueprint の `required` はコアの宣言ルール（`kind` / `subtype` / `min_rows` / `min_count`）として解釈。
- **L08**：denylist は `keiyaku/lint/denylist.txt`（実在企業名・実在サービス名・実在物件名・士業法人名）。
- **L09**：上限は `blueprint.page_limit`（無指定なら 12、絶対上限 20）。`chars_per_page_estimate` は
  **実コーパスから較正**する（合成較正は段落単位に量子化されて別版面が同値になる。yakkan R6）。
- **L16**：要求件数と配分を blueprint の `authored_qa` で宣言（既定 15 問・表 3・図 2・apply 2）。
- **L19（当事者整合）**：§4 のとおり。「甲がすべき義務が乙になっている」という**論理の取り違えは
  機械検出できない**——reviewer サブエージェントと目視の担当（`docs/authoring_checklist.md`）。
- **L20（契約書の骨格）**：`preamble` が body 先頭に 1 つ／`signature` が back_matter に 1 つ／記名欄が
  `meta.parties` の全当事者を覆う／収入印紙欄は `signature` の中だけ／`head_matter` は preamble の直後。
- **L21（逐条解説）**：`commentary` の `anchor` が存在し対象が実在すること（error）。
  解説文が対象条の本文と同一の文を含むこと（warn＝自己複製の検出）。

## 10. content ディレクトリ（parts 形式）

基底仕様 §5.11 のとおり（`doc.json` ＋ `parts/*.json` ＋ `source.json`）。差分は `doc.json` が
`family` / `doctype` を持つことだけ。最小実例は `tests/golden/sample_min/` に置く（P2）。
執筆ヘルパは `scripts/authoring.py`（表・列挙表・条の組み立て。**検証はしないので書いたら必ず lint**）。

## 11. 契約書固有の設計課題（P2〜P5 で確定させる。現時点は仮）

### 11.1 頭書の `{ref:}` 解決（**2026-09-27 確定**）
頭書は本文から「頭書に記載の◯◯」と参照されるが、**キャプションを持たない**ため表としては `{ref:}` の
対象にできない。`kind: head_matter` のノードを `rider` と同じ「番号を持たず呼び名で解決する種別」として
扱い、`{ref:head}` → **`kind_label`（既定「頭書」）** と解決する（`keiyaku/numbering.py`）。

- 頭書の**中**は本文と別の番号体系。`numbering/<scheme>.yaml` の `head_matter_levels` で宣言する
  （実物は条件の項目を括弧なしの算用数字で振る。`docs/reference_structures.md` §4 の #5）。
- 頭書には**2 つの型**がある。どちらも `head_matter` ノードの中身の違いで表せる：
  - **表の連なり**（`lease`）：見出しで区切った独立の表を並べる。
  - **番号付き項目の羅列**（`purchase`）：表を使わず項目を並べる。
- 行数が多いので、**結合セルをページ境界にまたがせない**こと（verify V11。`docs/gotchas.md`）。
  A4 1 段で収まる列数は **15 列まで**（実測）。

### 11.2 様式型のチェックボックス（**2026-09-27 確定**）
労働条件通知書の選択欄は、**選択状態そのものが読み取り課題**である。
記号を `form_fields` 表のセルのテキストとして持ち、`records` に
`{ 項目: "契約期間の定め", 選択: "期間の定めなし" }` の形で意味を持たせる。
図の `annotated_mock` は使わない（表として正解が取れるほうが採点しやすい）。

- **記号は `■`（選択）／`□`（未選択）**。`☑`（U+2611）は**使わない**（`docs/decisions.md` 91）。
  `scripts/probe_checkbox.py` の実測：`☑` は本文フォントに無く記号フォントへフォールバックし、
  L07 が warn を出して PDF に余分なフォントが埋め込まれる。`■` `□` `〇` は全同梱フォントにある。
- P1 の実測では、**実物の様式は記号を使わず「該当を〇で囲む」「`有・無` の一方を囲む」**
  （CT7・CT18）。`□` のチェックボックスは `consulting` の表形式にだけ現れた。
  v1 は記号方式（`■` / `□`）を採り、囲み方式は P8 の拡張とする。

### 11.3 逐条解説（commentary）の扱い
解説枠は紙面にあるので `answer.pages[].text` に**含める**が、`layout.text_lines[].region` を
`"commentary"` として本文と区別し、検索パッセージでは `kind: "commentary"` の別パッセージにする。
読み取り側には「本文と解説の分離」を求める（予測語彙に `commentary` を追加。`docs/evaluation.md` §4）。
**P5 で確定**。v1 では `license` の variant 1 本のみで試す。

### 11.4 基本契約と個別契約（**2026-09-27 確定**）
`sysdev` の「基本契約＋個別契約」は、個別契約を `kind: appendix`（`kind_label: "様式"`）として
`appendices` に置き、本文から `{ref:sch1}` で参照する形で表現する。
**入れ子の契約（契約の中の契約）という新しい機構は要らなかった**（`content/sys-0001` で実装して確認）。

- 様式の中身は `form_fields` の記入欄。本文の「注文書に記載すべき事項」の号と噛み合わせる。
- 同じ形が `outsourcing`（基本契約＋発注書）にも使える（CT14）。

### 11.5 三者以上の契約
`lease` の「貸主・借主・家賃債務保証業者」のように 3 者以上になる場合、`meta.parties` に 3 件並べ、
記名押印欄も 3 ブロックになる。**呼称は「甲・乙・丙」または役割名**（`role_label`）。
2 者の doctype でも variant で 3 者版（連帯保証人つき）を作れるようにする。
