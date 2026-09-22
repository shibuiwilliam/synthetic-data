# schema.md — データモデル（正解JSON）

> `docsynth/models.py` / `build.py` / `richtext.py` / `schema/` / `content/` / `dataset/` を触る作業では、
> **着手前に必ず本ファイルを読む**こと。仕様変更は実装より先に本ファイルを直し、`docs/decisions.md` に記録する。
>
> 本ファイルは **yakkan-synth の `../insurance-contracts/docs/schema.md` を基底仕様**とし、
> 汎用化に伴う**差分だけ**を書く。ここに書かれていない事項（RichText の文法、表の grid/records、
> 図 6 種、layout.json、answer.json、qa.json、parts 形式）は基底仕様のとおり。
> 型の正本は `docsynth/models.py`、機械可読版は `schema/*.schema.json`（`docsynth schema export`）。

## 1. 検証対象（基底仕様と同一）

テキスト／章条項構造／表／図／参照関係／QA の 6 観点。正解表現の対応表は基底仕様 §1.1。

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
- `front_matter.toc` は blueprint で有無を宣言（契約書は目次なしが普通、規程・約款はあり）。

## 3. meta の差分

```ts
type Meta = {
  title: string;                   // 「業務委託契約書」「〇〇サービス利用規約」
  subtitle?: string;
  issuer?: Issuer;                 // 単独名義の文書（terms / regulations / insurance）で使用
  parties?: PartyDef[];            // 複数当事者の文書（contract）で使用。§4
  effective_date?: string;         // 施行日・制定日（"2026-04-01"）
  edition_date?: string;
  form_code?: string;
  numbering_scheme: string;
  digit_style: "fullwidth" | "halfwidth";
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
  相当の導入形（当事者表示・前文でのみ使用可）。
- 解決結果は `derived.party_uses[]`（`{ block_id, key, rendered }`）に記録する。
- lint L16：`{party:}` の key が `meta.parties` に存在すること。当事者表示（parties ブロック）・
  署名欄（signature ノード）・`meta.parties` の呼称と名称が相互に一致すること。
  「甲」「乙」等の呼称の直書きは L03（ラベル直書き禁止）の検出対象に加える
  （検出パターンは numbering YAML と family.yaml から生成。定義済み alias の直書きのみ検出）。

## 5. Node / Block の追加種別

基底仕様の kind（part/chapter/rider/section/article/paragraph/item/subitem/subsubitem/appendix/appendix_section）
に加えて：

| kind | 用途 | 番号 | 備考 |
|---|---|---|---|
| `preamble` | 前文（契約書の「〇〇（以下「甲」という。）と…は、以下のとおり契約を締結する。」／規程・規約の前文） | 無番号 | body の先頭にのみ置ける |
| `signature` | 後文＋記名押印欄（「本契約の成立を証するため、本書2通を作成し…」＋日付＋甲乙の記名欄） | 無番号 | back_matter に置く。欄の中身は `meta.parties` から build が導出 |
| `schedule` | 別紙（仕様書・料金表・物件目録）。契約本文から `{ref:}` で参照される | 「別紙１」等の独立体系 | appendices に置く |
| `supplement` | 附則（規程・定款・規約の施行日・経過措置） | 「附則」＋項番号 | appendices に置く |

Block の追加：

| type | 用途 | 描画 |
|---|---|---|
| `parties` | 当事者表示（文書冒頭の「委託者：株式会社… 受託者：…」）。`keys: string[]` で meta.parties を参照 | 表または段落（style が選ぶ）。文字列はすべて meta.parties から導出 |
| `revision_history` | 改定履歴（利用規約の「2026年4月1日 改定」、規程の改正履歴） | 表として描画。`entries: { date, note }[]`。semantic_type は `history` |

- `signature` の描画は**枠と「印」の文字のみ**。印影画像・手書き風は作らない（CLAUDE.md §15）。
- 押印欄の bbox・記名文字列も他要素と同様に `layout.elements` に載せる（読み取り正解に含める）。

## 6. 表の semantic_type — 2 層語彙

```
コア共通語彙（models.py に定義）:
  definitions / enumeration / exclusions / rate / plan_matrix / procedure /
  mapping / history / generic / purpose_index
ファミリー登録語彙（family.yaml の semantic_types）:
  例）contract: fee_schedule, deliverables
      insurance: benefit_schedule, grade_schedule, surgery_schedule, coefficient, rider_index
      regulations: wage_table, allowance_table
      terms: plan_matrix（共通語彙で足りる想定。必要なら登録）
```

- lint L00 は「コア共通 ∪ 当該ファミリーの登録語彙」以外を error にする。
- `grid`＋`records`／`header_path` の二重表現、`{auto_label}`、`blocks_side_by_side` は基底仕様のとおり。

## 7. numbering の宣言化（`families/<f>/numbering/<scheme>.yaml`）

yakkan の nonlife/life/teikan（Python 直書き）を宣言に置き換える。解釈器はコア（`docsynth/numbering.py`）。

```yaml
scheme: contract-standard
levels:                         # kind ごとのラベル生成規則
  article:    { format: "第{n}条", counter: arabic, heading: "（{title}）" }
  paragraph:  { format: "{n}",    counter: arabic, skip_first: true }   # 第1項は無番号
  item:       { format: "（{n}）", counter: arabic }
  subitem:    { format: "{n}",    counter: katakana }                    # ア イ ウ
  schedule:   { format: "別紙{n}", counter: arabic }
  supplement: { format: "附則",    counter: none }
digit_style_from_meta: true     # 全角/半角は meta.digit_style に従う
ref_resolution:                 # {ref:} の相対表記規則（基底仕様 §6.4 の最小共通祖先方式）
  article_with_title: true      # 他条参照は「第４条（機密情報の返還）」
  same_article_paragraph: "第{n}項"   # 同一条内の項参照の書式
```

- 宣言で表現できない例外（定款の附則だけ項番号が変わる等）は family の `hooks.py` に
  `numbering_override(node, context) -> str | None` を実装して逃がす。フックの利用は
  `docs/decisions.md` に理由つきで記録する（§architecture.md「宣言優先、コード逃げ道」）。
- **P1 の golden**：insurance ファミリーの 3 スキーム YAML が、yakkan の `numbering.py` と
  全 kind × 位置で同一のラベル・同一の `{ref:}` 解決文字列を出すこと。
- L03（ラベル直書き禁止）の検出正規表現は、導入済みスキームの `format` から自動生成する
  （「第N条」「（N）」「①」等をハードコードしない）。

## 8. derived / answer.json / qa.json

基底仕様のとおり。追加は次のみ：

- `derived.party_uses[]`（§4）。
- `answer.json.outline` は kind の追加種別（preamble/signature/schedule/supplement）も含む
  （label が空文字列になり得る。depth は木の位置から）。
- QA 種別は基底仕様の 11 種を継承。契約書・規約でも同じ型で書ける
  （例：table_lookup=料金表、crossref=「第10条が引用する別紙はどれか」、apply=「解約通知を
  ○月○日に発した場合の契約終了日」）。ファミリー独自の QA 型は追加しない（v1）。

## 9. lint 規則の詳細差分

CLAUDE.md §8 の一覧が正。基底仕様からの変更点だけ列挙する。

- L00：family/doctype の存在検証、`meta.family_ext` のファミリー宣言スキーマ検証を追加。
- L03：検出パターンを numbering YAML から生成（§7）。当事者 alias の直書き検出を追加（§4）。
- L04：blueprint の `required_elements` はコアの宣言ルール（require_block / min_rows / min_count 等）
  として解釈する。ファミリー固有の複雑な必須条件は FLxx（family lint）へ。
- L08：denylist は `families/<f>/denylist.txt`。URL・電話番号の規則はコア共通。
- L09：上限は `blueprint.page_limit`（無指定なら family.yaml の `default_page_limit`、それも無ければ 20）。
- L16（新設）：当事者整合（§4）。
- FLxx：family.yaml の `lint:` 宣言（rule 種別はコアが提供）または hooks.py の
  `lint_extra(source) -> list[Finding]`。id は `FL` + 2 桁でファミリー内一意。

## 10. content ディレクトリ（parts 形式）

基底仕様 §5.11 のとおり（doc.json + parts/*.json + source.json）。`doc.json` に
`family` / `doctype` を持つことだけが差分。最小実例は `tests/golden/sample_min/` に置く（P1）。
