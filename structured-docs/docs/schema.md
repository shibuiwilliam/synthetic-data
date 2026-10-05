# schema.md — データモデル（正解JSON）

> `docsynth/models.py` / `build.py` / `richtext.py` / `schema/` / `content/` / `dataset/` を触る作業では、
> **着手前に必ず本ファイルを読む**こと。仕様変更は実装より先に本ファイルを直し、`docs/decisions.md` に記録する。
>
> 本ファイルは **yakkan-synth の `../insurance-contracts/docs/schema.md` を基底仕様**とし、
> 汎用化に伴う**差分だけ**を書く。ここに書かれていない事項（RichText の文法、表の grid/records、
> 図 6 種、layout.json、qa.json、parts 形式）は基底仕様のとおり。
> 型の正本は `docsynth/models.py`、機械可読版は `schema/*.schema.json`（`docsynth schema export`）。
>
> **2026-09-26 更新**：基底仕様の確定（2026-09-21）後に yakkan-synth へ入った拡張（§1.1）を
> 本プロジェクトの初期仕様に取り込み、`statute`（法令）ファミリーの差分（§11）と
> lint 番号の再整理（§9）を追記した。
>
> **2026-10-05 更新**：keiyaku-synth が契約書で**実装・実証済み**の拡張（§1.2）を初期仕様に加えた——
> `head_matter`（頭書）・`commentary`（逐条解説）・`{party:|role}`・契約書の semantic_type 6 種・
> 番号方式 3 種（うち `contract-form` は条を持たない／`contract-kanji` は漢数字）。
> lint を **L00–L26**（新設枠は L27 以降）に拡張し、§11 の statute 設計課題に
> 「keiyaku で同種の課題がどう解けたか」を注記した。

## 1. 検証対象（基底仕様と同一）

テキスト／章条項構造／表／図／参照関係／QA の 6 観点。正解表現の対応表は基底仕様 §1.1。

### 1.1 基底仕様の確定後に yakkan-synth へ入った拡張（本プロジェクトでは最初から仕様に含める）

基底の `docs/schema.md` は 2026-09-21 時点の写しであり、その後の拡張は yakkan の
yakkan の `../insurance-contracts/docs/` の `blueprints.md`・`decisions.md`・`eval_dataset_plan.md` に散っている。
**移植時に見落としやすいので、ここに列挙する。すべて v1 仕様の一部である。**

| 拡張 | 内容 | yakkan 側の記録 |
|---|---|---|
| `Node.kind: "rider"` | 特約。**番号を持たず**、中の条は特約ごとに第1条から。`{ref:}` は題名で解決 | decisions 2026-09-22 |
| `Node.badges` | 見出し右の分類ラベル（「契約概要」「注意喚起情報」）。`<node_id>__badge<i>` の独立要素として plain_text と layout に載る | decisions 2026-09-22 |
| `Node.kind_label` | 別表の呼び名（「別表」「付表」「別紙」）。番号は**呼び名ごとに**振る | decisions 2026-09-22 |
| `meta.article_heading` | 条見出しの体裁 `inline`（第1条（見出し））/ `above`（見出しを条の上に括弧書き＋条ラベルが本文へ走り込み。`LabelInfo.run_in_label`）/ `plain`（丸数字小見出し） | blueprints.md |
| `meta.footnote_style` | 条末脚注の体裁 `inline`（(*n)）/ `remarks_box`（❶＋「第N条　備考」枠） | blueprints.md |
| `meta.caption_numbering` | 表・図番号 `flat`（表1）/ `chapter`（表1-1。**章に属さない表・図には番号を振らない**） | remaining_issues R4/S2 |
| 表・図への `{ref:}` | キャプションのある表・図は `{ref:tbl_x}` →「表２」。**素の「表２」直書きは禁止**（番号は build が振る） | decisions 2026-09-22 |
| 図・算式内トークン | `{const:}` `{term:}` `{ref:}` を build が解決し `derived.figures[].resolved_labels` に記録。**紙面に出るのは解決後の文字列** | decisions 2026-09-22 |
| 図の正規化グラフ | 6 種共通の `derived.figures[].graph`（nodes/edges/role）と全種の `paths`。図 F1 評価の土台 | eval_dataset_plan P1 |
| 構造位置 | `derived.labels[]` に `kind` / `parent_id` / `path_ids` / `citation`（「第2章 第1条 (1)」＝番号だけを連ねた紙面表記）。outline・toc にも同じ 4 つ | eval_dataset_plan P2/P3 |
| 列挙の親子 | `derived.enumerations[]`（列挙表・号ノード・箇条書きの 3 系統を共通の形で） | eval_dataset_plan P4 |
| `answer.json` のスリム化 | `source` / `layout` を**内包しない**（同じディレクトリの実体を `load_answer(dir)` で結合）。42MB→5.3MB の実績 | remaining_issues R3 |
| `outline` の範囲 | **番号のある項も入れる**。ラベルも見出し文言も持たない節点（条の最初の項）は**外す** | remaining_issues T7 / X3-2 |
| `elements.jsonl` ほか評価向け成果物 | 1 行 1 要素の平索引・検索評価セット（passages/queries/qrels）・予測スキーマ。すべて pydantic モデル（`export_models.py`）から schema export | eval_dataset_plan P5–P9、S9 |
| lint L16 / L17 / L18 | 執筆 QA の配分強制／`header_cols` の宣言漏れ／列挙用の表への caption 禁止 | S1 / X3-4・Y1 / Z2 |

### 1.2 keiyaku-synth が契約書で実装・実証した拡張（本プロジェクトでは最初から仕様に含める）

`../contracts/docs/schema.md` の §2〜§11 が正本。**100 文書で成立済み**であり、設計をやり直さない。

| 拡張 | 内容 | keiyaku 側の記録 |
|---|---|---|
| `family` + `doctype` | `genre` の置換。`schema_version: "2.0"`。keiyaku は `family` を固定値 `contract` で持つ（P1 でレジストリに開く） | schema.md §2 |
| `Node.kind: "head_matter"` | 頭書（冒頭の当事者・目的物・金額の一覧）。**番号を持たず呼び名で解決**し `{ref:head}` → `kind_label`（既定「頭書」）。中は `head_matter_levels` で別番号体系。型は「表の連なり」と「番号付き項目の羅列」の 2 つ | schema.md §11.1（2026-09-27 確定） |
| `Node.kind: "signature"` の実装 | 後文＋契約日＋記名押印欄。欄の中身は `meta.parties` から build が導出。`signature_layout: vertical \| horizontal` | rendering.md §4.4 |
| `Block.commentary` | 逐条解説。対象条の `anchor` を持つ（L21）。`layout.text_lines[].region = "commentary"` で本文と区別し、検索パッセージは `kind: "commentary"` | schema.md §11.3 |
| `Block.parties` / `revision_history` | 当事者表示・改定履歴（`semantic_type: history`） | schema.md §5 |
| `{party:<key>}` の 3 修飾 | `\|name`（正式名称）`\|full`（「株式会社◯◯（以下「甲」という。）」型）`\|role`（役割名）。解決結果は `derived.party_uses[]`。**紙面一致は verify V-P5 が検査** | schema.md §4 |
| 契約書の semantic_type | `fee_schedule` `deliverables` `inventory` `head_matter` `form_fields` `allocation`（ファミリー登録語彙として `family.yaml` へ移す） | schema.md §6 |
| 様式型の記入欄 | 記号は **`■`（選択）/`□`（未選択）**。`records` に `{ 項目, 選択 }` の意味を持たせる。`☑`（U+2611）は使わない | schema.md §11.2（decisions 91） |
| 基本契約＋個別契約 | 個別契約は `kind: appendix`（`kind_label: "様式"`）として `appendices` に置き本文から `{ref:}`。**入れ子の契約という新機構は要らなかった** | schema.md §11.4（2026-09-27 確定） |
| 三者以上の当事者 | `meta.parties` に 3 件並べ記名欄も 3 ブロック。呼称は「甲・乙・丙」または `role_label` | schema.md §11.5 |
| 番号方式 3 種の宣言 | `contract-standard`（条は全編通し・第1項無番号・号「(1)」・細目「ア」）／**`contract-form`（条を持たない。項目 `1` →（1）→（ア）の 3 階層）**／**`contract-kanji`（条番号が漢数字「第一条」）** | schema.md §7 |
| lint L19–L26 | 当事者整合／骨格／逐条解説／表・図の配置／列挙の入れ子／置き去りの part／Markdown の名残／位置で指す言い方（§9） | lint_rules.md |
| verify V11・V-P5 | 結合セルのページまたぎ／`{party:}` の紙面一致（`docs/rendering.md` §6） | rendering.md §6 |

## 2. source.json のトップレベル差分

```ts
type Source = {
  schema_version: "2.0";           // docsynth 系は 2.x
  content_id: string;              // 例 "nda-0001"
  family: string;                  // 例 "contract"。導入済みファミリーであること（lint L00）
  doctype: string;                 // 例 "nda"。family の doctypes に含まれること
  seed: number;
  meta: Meta;                      // §3
  front_matter: FrontMatter;       // cover は MAY に変更（契約書・規約は表紙を持たないことが多い）
  defined_terms: TermDef[];        // 基底仕様と同一
  body: Node[];
  appendices: Node[];              // 別紙・別表・附則（kind: schedule / appendix / supplement）
  back_matter: BackMatter;         // colophon（disclaimer 必須）＋ signature（§5）
  derived?: Derived;               // build が付与。執筆物（SourceDraft）に書くと L00 で落ちる
};
```

- 基底仕様からの改名：`genre` → `family` + `doctype`。`numbering_scheme` は meta に残る
  （値はファミリーの `numbering/` にあるスキーム名）。
- `front_matter.toc` は blueprint で有無を宣言（契約書は目次なしが普通、規程・約款・法令はあり）。

## 3. meta の差分

```ts
type Meta = {
  title: string;                   // 「業務委託契約書」「〇〇サービス利用規約」「〇〇景観条例」
  subtitle?: string;
  issuer?: Issuer;                 // 単独名義の文書（terms / regulations / statute / insurance）で使用
  parties?: PartyDef[];            // 複数当事者の文書（contract）で使用。§4
  effective_date?: string;         // 施行日・制定日（"2026-04-01"）
  edition_date?: string;
  form_code?: string;
  promulgation?: Promulgation;     // 法令の公布情報（statute のみ。§11）
  numbering_scheme: string;
  digit_style: "fullwidth" | "halfwidth";
  article_heading?: "inline" | "above" | "plain";   // §1.1（既定 inline。scaffold が blueprint から写す）
  footnote_style?: "inline" | "remarks_box";        // §1.1（既定 inline）
  caption_numbering?: "flat" | "chapter";           // §1.1（既定 flat）
  disclaimer: string;              // 架空である旨。末尾（colophon）に必ず描画
  constants?: { [key: string]: string };   // {const:key} で参照。数値整合 L11 の土台
  family_ext?: object;             // ファミリー固有のメタ（スキーマは family.yaml で宣言・L00 で検証）
};
```

- `issuer` と `parties` は**どちらか一方以上が必須**（blueprint が宣言）。

## 4. 当事者（PartyDef と `{party:}` トークン）— 新設

契約書の「甲・乙」問題を、番号ラベルと同じ発想で解決する：**執筆者は呼称を直書きせず、
トークンで参照し、build が解決する**。呼称の揺れ・取り違えを構造的に排除する。

```ts
type PartyDef = {
  key: string;                     // "client" | "vendor" など英語 slug。{party:client} で参照
  alias: string;                   // 紙面上の呼称：「甲」「乙」「丙」「委託者」「借主」…
  name: string;                    // 架空の正式名称「株式会社青葉システムズ」
  address?: string;                // 架空住所
  representative?: string;         // 架空の代表者名（署名欄で使用）
};
```

- RichText 追加トークン `{party:<key>}`：本文中では `alias`（「甲」）に解決される。
  `{party:<key>|name}` で正式名称、`{party:<key>|full}` で「株式会社青葉システムズ（以下「甲」という。）」
  相当の導入形（当事者表示・前文でのみ使用可）、`{party:<key>|role}` で役割名（「委託者」。
  `role_label` を宣言した当事者のみ）。
- 三者以上の当事者に対応する（`meta.parties` に 3 件並べ、記名押印欄も 3 ブロックになる。keiyaku `lease`）。
- 解決結果が**紙面に出ていること**を verify V-P5 が検査する（トークンの未解決・解決漏れの検出）。
- 解決結果は `derived.party_uses[]`（`{ block_id, key, rendered }`）に記録する。
- lint L19（§9）：`{party:}` の key が `meta.parties` に存在すること。当事者表示（parties ブロック）・
  署名欄（signature ノード）・`meta.parties` の呼称と名称が相互に一致すること。
  「甲」「乙」等の呼称の直書きは L03（ラベル直書き禁止）の検出対象に加える
  （検出パターンは numbering YAML と family.yaml から生成。定義済み alias の直書きのみ検出）。

## 5. Node / Block の追加種別

基底仕様の kind（part/chapter/rider/section/article/paragraph/item/subitem/subsubitem/appendix/appendix_section）
に加えて：

| kind | 用途 | 番号 | 備考 |
|---|---|---|---|
| `preamble` | 前文（契約書の「〇〇（以下「甲」という。）と…は、以下のとおり契約を締結する。」／規程・規約・法令の前文） | 無番号 | body の先頭にのみ置ける（L20） |
| `head_matter` | 頭書（冒頭の当事者・目的物・金額の一覧。賃貸借・売買） | **番号を持たない**（呼び名で解決：`{ref:head}` → `kind_label` 既定「頭書」） | body の先頭（preamble の次）。中は `head_matter_levels` の別番号体系。結合セルをページ境界にまたがせない（V11） |
| `signature` | 後文＋記名押印欄（「本契約の成立を証するため、本書2通を作成し…」＋日付＋甲乙の記名欄） | 無番号 | back_matter に置く。欄の中身は `meta.parties` から build が導出 |
| `schedule` | 別紙（仕様書・料金表・物件目録）。契約本文から `{ref:}` で参照される | 「別紙１」等の独立体系 | appendices に置く |
| `supplement` | 附則（規程・定款・規約・法令の施行日・経過措置） | 「附則」＋項番号 | appendices に置く。複数置ける（法令の改正附則。§11） |

Block の追加：

| type | 用途 | 描画 |
|---|---|---|
| `parties` | 当事者表示（文書冒頭の「委託者：株式会社… 受託者：…」）。`keys: string[]` で meta.parties を参照 | 表または段落（style が選ぶ）。文字列はすべて meta.parties から導出 |
| `revision_history` | 改定履歴（利用規約の「2026年4月1日 改定」、規程の改正履歴、法令の改正沿革） | 表として描画。`entries: { date, note }[]`。semantic_type は `history` |
| `commentary` | 逐条解説（モデル契約の解説枠）。対象条の `anchor` を必須（L21） | 枠として条文の直後。`layout.text_lines[].region = "commentary"` で本文と区別。検索パッセージは `kind: "commentary"` |
| `form_fields` | 様式型の記入欄（表として持つ。選択欄の記号は `■`/`□`） | 罫線表。`records` に `{ 項目, 選択 }` の意味を付ける |

- `signature` の描画は**枠と「印」の文字のみ**。印影画像・手書き風は作らない（CLAUDE.md §15）。
- 押印欄の bbox・記名文字列も他要素と同様に `layout.elements` に載せる（読み取り正解に含める）。
- `rider` / `badges` / `kind_label` / `number_override(+reason)` は基底仕様＋§1.1 のとおり全ファミリーで使える
  （例：terms の「〇〇に関する特則」を rider で、jyusetsu 型のバッジを他ファミリーが使うことも可）。

## 6. 表の semantic_type — 2 層語彙

```
コア共通語彙（models.py に定義）:
  definitions / enumeration / exclusions / rate / plan_matrix / procedure /
  mapping / history / generic / purpose_index
ファミリー登録語彙（family.yaml の semantic_types）:
  例）contract:    fee_schedule, deliverables, inventory, head_matter, form_fields, allocation
      insurance:   benefit_schedule, grade_schedule, surgery_schedule, coefficient, rider_index
      regulations: wage_table, allowance_table
      statute:     reading_replacement（読替え表）, penalty_schedule（罰則一覧）
      terms:       plan_matrix（共通語彙で足りる想定。必要なら登録）
```

- lint L00 は「コア共通 ∪ 当該ファミリーの登録語彙」以外を error にする。
- `grid`＋`records`／`header_path` の二重表現、`{auto_label}`、`blocks_side_by_side` は基底仕様のとおり。
- **`semantic_type` は正解データの一部**。blueprint の必須要素を満たすために型を偽らせない
  （yakkan decisions 2026-09-22「別表の要件は構造だけを error にする」を継承）。
- **列挙用の表（enumeration / exclusions）に caption を付けない**（L18）。caption の有無で
  「表N」を振る build と、semantic_type で採点対象を分ける eval の基準が独立しているため、
  両方に該当すると「紙面に表Nと印字されるのに採点されない」矛盾が起きる（yakkan Z2 で実証）。

## 7. numbering の宣言化（`families/<f>/numbering/<scheme>.yaml`）

yakkan の nonlife/life/teikan/group/jyusetsu（Python 直書き）を宣言に置き換える。
解釈器はコア（`docsynth/numbering.py`）。**keiyaku が 3 方式（`contract-standard` / `contract-form` /
`contract-kanji`）を宣言で書き切っており、解釈器としては完成している**（`iroha` counter のみ未実装）。
残る作業は「探索パスを `families/<f>/numbering/` に移すこと」と「insurance の 5 方式を YAML に落とすこと」。

宣言で書けることが実証済みの難所：**条を持たない方式**（`contract-form`＝様式型。項目 `1` →（1）→（ア）の
3 階層。yakkan の jyusetsu も同型）、**漢数字の条番号**（`contract-kanji`＝約款型。第一条）、
**頭書の中の別番号体系**（`head_matter_levels`）。

```yaml
scheme: contract-standard
levels:                         # kind ごとのラベル生成規則
  article:    { format: "第{n}条", counter: arabic, heading: "（{title}）" }
  paragraph:  { format: "{n}",    counter: arabic, skip_first: true }   # 第1項は無番号
  item:       { format: "（{n}）", counter: arabic }
  subitem:    { format: "{n}",    counter: katakana }                    # ア イ ウ
  schedule:   { format: "別紙{n}", counter: arabic }
  supplement: { format: "附則",    counter: none }
counters_available: [arabic, circled, katakana, paren_katakana, roman, kanji, iroha]
digit_style_from_meta: true     # 全角/半角は meta.digit_style に従う
continuous_articles: true       # 条を章ごとに振り直さず全編通し（契約書・定款・法令）
paragraph_ref_style: written    # 印字が無番号でも参照は「第1項」「第1項第4号」と書き下す
ref_resolution:                 # {ref:} の相対表記規則（基底仕様 §6.4 の最小共通祖先方式）
  article_with_title: true      # 他条参照は「第４条（機密情報の返還）」
  same_article_paragraph: "第{n}項"   # 同一条内の項参照の書式
```

- **counter に `kanji`（一・二・三…第十二条）と `iroha`（イ・ロ・ハ）を追加する**（statute で必須。§11）。
  丸数字の上限フォールバック（⑳超は括弧数字＋警告）と同様に、イロハは「ヰヱ を飛ばして 47 音、
  超過は (1) にフォールバック」の規則をコアが持つ。
- 宣言で表現できない例外（定款の附則だけ項番号が変わる等）は family の `hooks.py` に
  `numbering_override(node, context) -> str | None` を実装して逃がす。フックの利用は
  `docs/decisions.md` に理由つきで記録する（`docs/architecture.md`「宣言優先、コード逃げ道」）。
- yakkan で判明済みの一般規則を宣言に含める：
  - `continuous_articles` の方式では `{ref:}` に章を冠さない（「第１４条（決議）」）。
  - 第1項が無番号の方式では、項・号への参照を「第N項」「第N号」と**書き下す**
    （印字どおりに連ねると空文字に解決される。yakkan group で 18 件の実害）。
  - 附則の中を指す参照は「附則第３」のように祖先ラベルを冠する。
- **P1 の golden**：**8 スキーム**（contract 3 ＋ insurance 5）が、姉妹の実装と全 kind × 位置で
  同一のラベル・同一の `{ref:}` 解決文字列を出すこと。contract 3 方式は keiyaku の
  `tests/golden/`（`numbering_legacy.json` を持ち込むかは P0 で判断）、insurance 5 方式は
  yakkan の `numbering.py` を基準にする。
- L03（ラベル直書き禁止）の検出正規表現は、導入済みスキームの `format` から自動生成する
  （「第N条」「（N）」「①」「第十二条」「イ」等をハードコードしない）。

## 8. derived / answer.json / qa.json / 評価向け成果物

基底仕様＋§1.1 のとおり。差分は次のみ：

- `derived.party_uses[]`（§4）。
- `answer.json` は `source` / `layout` を内包しない（`docsynth.answer.load_answer(dir)` で結合）。
- `answer.json.outline` は kind の追加種別（preamble/signature/schedule/supplement）も含む。
  ただし基底仕様と同じく**ラベルも見出し文言も持たない節点は outline に入れない**（yakkan T7）。
- `layout.text_lines[].region`：本文／ヘッダ／フッタ／**`commentary`**（逐条解説枠）を区別する。
- QA 種別は基底仕様の 11 種（`apply` 含む）を継承。**`apply` の答えは「機械検算 → 読み幅の明示 →
  人間の承認」で確定する**（`docs/validation_plan.md` §5.1）。契約書・規約・法令でも同じ型で書ける
  （例：table_lookup=料金表、crossref=「第10条が引用する別紙はどれか」、apply=「解約通知を
  ○月○日に発した場合の契約終了日」「第◯条の罰則を◯◯の場面に当てはめると科されるのはどれか」）。
  ファミリー独自の QA 型は追加しない（v1）。
- 評価向け成果物（`elements.jsonl`・`passages.jsonl`・`queries.jsonl`・`qrels.jsonl`・
  `prediction` / `search_run` スキーマ）は yakkan の `export_models.py` を移植し、
  **全ファミリー共通の形**で出す。詳細は `docs/evaluation.md`。

## 9. lint 規則（番号の再整理）

**姉妹の最終形 L00–L26 を番号・意味とも互換で継承する**（yakkan L00–L18 ＋ keiyaku L19–L26）。
移植コード・テスト・docs・3 プロジェクト間の会話の突合を崩さないことを優先する。
**本プロジェクトの新設は L27 以降**、ファミリー内で済むものは FLxx。
実装位置と検査ロジックは `docs/lint_rules.md`。
（旧版の本ファイルが「当事者整合＝L16」としていたのを L19 に改番したのが 2026-09-26、
L20〜L26 を取り込んだのが 2026-10-05。`docs/decisions.md`）。

| # | ルール（汎用化後の要点） | 重大度 |
|---|---|---|
| L00–L03 | スキーマ検証（derived 混入・family/doctype・family_ext）／id・参照の存在（**空文字に解決される参照も error**）／脚注対応／番号ラベル直書き禁止（検出パターンは numbering YAML＋party alias から生成） | error |
| L04–L06 | blueprint 必須要素（**構造のみを縛る。semantic_type で題材を縛らない**）／表の格子整合（幅は格子の位置数で数える）・records 整合／図の端点・座標・最小複雑度・alt/facts・resolved_labels | error |
| L07–L09 | フォント被覆／denylist・ドメイン・電話番号／推定ページ数（上限は blueprint、較正は実コーパス基準） | error（L09 目標超過は warn） |
| L10–L12 | 文体（敬体/常体・digit_style）／数値整合（`{const:}`）／定義語の未定義使用・未使用定義 | warn |
| L13–L15 | disclaimer・meta 必須／QA 整合（evidence 存在・answer 包含・**図の答えが実在ラベルか**）／類似度 >30% | error / error / warn |
| L16 | 執筆 QA の件数と観点の配分（件数・表 3 問・図 3 問・apply 1 問以上。**文章で書いただけでは守られない**：yakkan で 13/30 content が違反していた） | error |
| L17 | 表の `header_cols` が行見出し（stub 列）を覆っている。**`header_cols == 0` そのものを error**（yakkan X3-4/Y1：宣言漏れ 23＋2 表で表セル F1 が壊れた） | error |
| L18 | 列挙用の表（enumeration / exclusions）に `caption` を付けない（§6） | error |
| **L19** | **当事者整合**：`{party:}` の key が `meta.parties` に存在し、当事者表示・前文・本文・記名押印欄で呼称と名称が一致 | error |
| **L20** | **文書の骨格**：`preamble` が body 先頭に 1 つ、`signature` が back_matter に 1 つ、記名欄が全当事者を覆う、収入印紙欄は `signature` の中だけ。**何を要求するかは family.yaml の `skeleton:` が宣言する**（様式型は preamble・signature を持たない） | error |
| **L21** | **逐条解説**：`commentary` は対象条の `anchor` を持ち、対象が実在する（anchor 欠落は error／本文との文の重複は warn） | error/warn |
| **L22** | **表・図の配置**：`table` / `figure` / `formula` は**導入文を持つ項**の `blocks` に付ける（`article` や `chapter` の直下に置くと第1項より前に描画される） | error |
| **L23** | **列挙の入れ子**：同じ親の下に号（`item`）の並びが 2 組以上あるなら、号は**導入する項の `children`** に入れる（兄弟に並べると条の中で通し番号になる） | error |
| **L24** | **置き去りの part**：`parts/*.json` はすべて `doc.json` の `parts` から参照されていること（書き直しの置き去りは未執筆のまま誰にも見えない） | error |
| **L25** | **Markdown の名残**：本文に `**` `__` `` ` `` を書かない（強調は `{b:}` `{u:}`。`**` はそのまま紙面に印字される） | error |
| **L26** | **位置で指す言い方**：番号を持つ表・図は `{ref:}` で指す（「下表」は版面が変われば嘘になる。番号の無い列挙表は対象外） | warn |
| **L27–** | **本プロジェクトの新設枠**（空）。姉妹と番号が衝突しないようここから採番する | — |
| FLxx | ファミリー定義の追加 lint（family.yaml の `lint:` で宣言、またはフックで実装）。id は `FL`+2 桁でファミリー内一意 | family 定義 |

基底仕様からの実装上の変更点：

- L00：family/doctype の存在検証、`meta.family_ext` のファミリー宣言スキーマ検証を追加。
- L03：検出パターンを numbering YAML から生成（§7）。当事者 alias の直書き検出を追加（§4）。
- L04：blueprint の `required_elements` はコアの宣言ルール（require_block / min_rows / min_count 等）
  として解釈する。ファミリー固有の複雑な必須条件は FLxx へ。
- L08：denylist は `families/<f>/denylist.txt` ＋ コア共通 `docsynth/lint/denylist_common.txt`。
  URL・電話番号の規則はコア共通。
- L09：上限は `blueprint.page_limit`（無指定なら family.yaml の `default_page_limit`、それも無ければ 20）。
  `chars_per_page_estimate` は**実コーパスから較正**する（yakkan R6：合成較正は段落単位で量子化されて
  別版面が同値になる）。
- L16：`qa_authored.json` の要求件数・観点配分は family.yaml で宣言する（既定は 15 問・表 3・図 3・apply 1。
  **contract は図が少ないので「図 2・apply 2」**＝keiyaku の実績値を使う）。
- L10：tone の既定はファミリー宣言から読む。**様式型（条を持たない doctype）は体言止めが多いので判定を緩める**。
- L20：骨格の要件は family.yaml の `skeleton:` から読む（`docs/architecture.md` §3）。
- L22〜L26 は**目視でしか見つからなかった欠陥の機械化**である（keiyaku）。無効化しない。

## 10. content ディレクトリ（parts 形式）

基底仕様 §5.11 のとおり（doc.json + parts/*.json + source.json）。`doc.json` に
`family` / `doctype` を持つことだけが差分。最小実例は `tests/golden/sample_min/` に置く（P1）。
執筆ヘルパは yakkan の `scripts/authoring.py`（表・列挙表・条の組み立て。**検証はしないので
書いたら必ず lint**）を移植して使う。

## 11. statute（法令）ファミリーの差分 — 新設（2026-09-26）

法令（法律・条例の体裁）はコアの機構でほぼ表現できるが、次の差分を要する。
ファミリーのカタログは `docs/families.md` §6。

**statute は姉妹に先例が無い唯一のファミリーである。** 借りられるのは次の 2 点だけで、残りは
P6 で probe してから確定する（`docs/plan.md` P6・`docs/rendering.md` §7）：

- **漢数字の条番号**：keiyaku の `contract-kanji`（約款型）で実証済み。`kanji` counter は実装されている。
- **条見出しが条番号の上に来る体裁**：keiyaku の約款型が同形（条見出しが条番号の上）。
  ただし **citation に run-in ラベルを含めない**という教訓つきで継承する
  （keiyaku V-D：「第三条 第三条 (1)」という外から再現できない正解ができていた。`docs/evaluation.md` §3-6）。

借りられないもの（未実証）：`iroha` counter・条の枝番・目次の条範囲・別表の関係条注記・
`meta.promulgation`・読替え表。

### 11.1 公布情報（meta.promulgation）

```ts
type Promulgation = {
  law_number: string;    // 「令和◯年法律第◯◯号」「◯◯市条例第◯号」。架空（§11.4）
  date: string;          // 公布日 "2026-04-01"
  statement?: string;    // 公布文（「〇〇法をここに公布する。」相当のオリジナル文）。MAY
};
```

題名の下（または表紙相当位置）に描画される。文字列は他要素と同様 `layout.elements` に載せる。

### 11.2 番号方式 `horei`

| kind | ラベル | counter |
|---|---|---|
| part / chapter / section / subsection… | 第一編 / 第一章 / 第一節 / 第一款 / 第一目 | `kanji`（variant で `arabic`） |
| article | 第一条（**条見出しは条の上に括弧書き**＝`article_heading: above` 相当。ただし run-in ラベルではなく「（定義）」の行 → 「第二条　本文…」の 2 行構成） | `kanji` |
| paragraph | ２ ３（第1項無番号・全角） | arabic |
| item | 一 二 三 | `kanji` |
| subitem | イ ロ ハ | `iroha` |
| subsubitem | （１）（２） | arabic |
| appendix | 別表第一（第三条関係） | `kanji` ＋ 関係条注記（§11.3） |
| supplement | 附　則（複数可。改正附則には公布番号を冠する） | none |

- 目次は「第一章　総則（第一条―第五条）」のように**章名＋条範囲**を持つ。条範囲は build が導出する
  （`derived.toc[].article_range`）。手書き禁止。
- 条の**枝番**（第二条の二。改正で挿入された条）は `Node.number_override`（＋reason 必須）で表現する。
  v1 では宣言的な branch 機構は作らない（`docs/decisions.md` 仮決め）。
- 漢数字カウンタは「十・百」を用いる位取り（第十二条・第百三条）。`digit_style` の影響を受けない
  （法令の漢数字は表記が固定のため）。variant で算用数字体（第12条。デジタル原本の体裁）も選べる。

### 11.3 別表の関係条注記

法令の別表見出しは「別表第一（第三条関係）」のように**参照元の条**を冠する。
`Node.relation_refs: string[]`（ノード id 配列）を新設し、build が「（第三条関係）」を
`heading_text` に含めて導出する。手書きの「（第◯条関係）」は L03 で落とす。
複数条は「（第三条、第五条関係）」。実装は P6（statute フェーズ）で確定し、
`derived.labels` の heading_text に含める形をとる。

### 11.4 架空性（statute 固有）

- 題名は架空（「特定荷役機械安全確保法」風のオリジナル）。**実在法令と紛らわしい題名は denylist で検出**
  （`families/statute/denylist.txt` に主要法令名を収載）。
- 条例は**架空の自治体名**（「青葉川市」等）を使う。実在自治体名は denylist。
- `law_number` は実在の様式（「令和◯年法律第◯号」）を使うが、**番号は架空**。実在法令の番号と
  偶然一致しうる点は HITL レビュー項目とする（`docs/validation_plan.md` §HITL）。
- 「実在法令は名称のみ引用・条番号は書かない」の全体ルール（CLAUDE.md §0.4-2）は
  statute の**生成文書の中でも**適用する（架空法令の本文が実在法令を名指しで引くのは名称まで）。

### 11.5 読み取り課題として狙うもの

漢数字カウンタ（第十二条 ↔ 12 の正規化）、イロハ細目、条の枝番、目次の条範囲、
別表の「（第◯条関係）」、読替え表（`reading_replacement`）、附則の多層化（制定附則＋改正附則）、
定義条の深い入れ子（号 → イロハ → （１））。`docs/families.md` §6 に blueprint への写像を書く。
