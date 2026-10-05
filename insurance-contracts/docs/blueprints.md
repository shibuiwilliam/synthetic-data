# blueprints.md — ジャンル別必須要素・style プリセット・blueprint YAML

> CLAUDE.md §4.1 / §4.2 / 付録A / 付録B の全文を 2026-09-21 にそのまま移設したもの（一字一句の変更なし）。
> `blueprints/*.yaml` / `styles/*.yaml` / `yakkan/scaffold.py` / `yakkan/compose.py` を触る作業、
> および新ジャンル・新スタイルの追加では、**着手前に必ず本ファイルを読む**こと。
> ジャンル一覧表（genre・目標ページ・段組・番号方式・文体）は CLAUDE.md §4 に残してある。

### 4.1 ジャンル別 必須要素（blueprint の `required_elements`）

**auto**
- 前付け：表紙、はじめに、目的別もくじ（A3）、もくじ（章直下に要約文つき A4）、約款の構成図（D1）、特約一覧表（A5・6列以上・◆凡例）
- 【用語の定義】表（C1・五十音索引列・15〜25語・セル内脚注あり）
- 第１章 賠償責任条項（補償内容／被保険者／免責／お支払いする保険金（C2＋算式 D6）／援助・解決）
- 第２章 人身傷害条項（保険金請求権者／損害額の考え方）※抜粋で可
- 第３章 車両条項（付属品の範囲を列挙表 B3 で）
- 第４章 基本条項（第１節 契約手続と義務／第２節 保険料の払込み／第３節 事故発生時の義務（義務名称×内容の2列表 C7）／第４節 保険金の請求／第５節 解除／第６節 その他）
- 特約 2〜3本（各：適用条件／用語の定義／補償／普通約款の準用）
- 別表１ 後遺障害等級表（C5・抜粋10行以上）、付表 短期率表と月割表（C4）
- 図：事故時の対応ステップ（D2）、受取りまでの流れ（D3）、等級推移タイムライン（D5）
- 欄外解説ボックス（B6）を 4 箇所以上、条末脚注（B5）を 10 箇所以上

**oneday**
- 表紙、もくじ、プラン比較マトリクス（C6 or D6）、補償内容一覧表（C2）、申込手続きの流れ（D7・スマートフォン手続き）、用語の定義、補償条項（対人・対物・車両）、基本条項（責任の始期終期を時刻まで明記）、無事故割引の説明表、保険期間タイムライン（D5）

**quake**
- 用語の定義表、補償条項、**損害の程度の認定基準表**（全損／大半損／小半損／一部損 × 建物・家財 × 損害割合 × 支払割合の結合セル表）、保険金額の制限（火災保険との関係を階層図 D1/D7）、損害認定のフロー（D2）、基本条項、別表 認定基準

**health**
- 用語の定義表、傷害条項・疾病条項、保険金の種類一覧（入院／手術／通院／死亡／後遺障害、C2）、**手術の種類と給付倍率表**（別表・C5）、後遺障害等級表（抜粋）、責任開始日・免責期間のタイムライン（D5）、告知から契約までの流れ（D7）、保険金請求時の提出書類表（C7）

**life**
- Ⅰ ご契約のしおり：しおりの読み方、**用語集（しおり冒頭。`semantic_type: definitions`）**、Q&A 形式の見出し（「保険料の払込みが遅れたときは？」等）、手続きの流れ図（D7）、保険料払込方法と猶予期間の表、失効と復活のタイムライン（D5）、税制上の取扱い表、クーリング・オフの説明枠
- **用語集は `defined_terms` の全語を載せる**（2026-10-04 追加）。損保の定義表が条文体なのに対し、しおりの用語集は**平易な敬体**で書く。`life` だけ `required` から漏れていたため `defined_terms` の過半が紙面に出ず、検索コーパスの `definition` パッセージが 17 件しか無かった（`docs/search_query_plan.md` 段 5）
- Ⅱ 約款：責任開始期、保険金・給付金の支払（名称／支払事由／支払額／受取人の表 C2）、免責、告知義務と解除、保険料の払込みと猶予期間、失効・復活、解約と返戻金、契約者貸付、指定代理請求、別表（高度障害状態の表、手術の種類表、対象となる疾病の範囲表）
- 生保特有の番号方式（項「１．」、号「(1)」、細目「①」、「（注）」）

**teikan**
- 第１章 総則（商号／目的／本店所在地／公告方法）、第２章 社員または株式、第３章 総代会または株主総会、第４章 取締役・取締役会、第５章 監査役、第６章 計算、第７章 基金（相互会社の場合）、附則
- **用語集は持たない**（実物の定款にも無い）。`defined_terms` も 0 語で、**10 ジャンルのうち `teikan` だけが検索コーパスに `definition` パッセージを出さない**。これは欠陥ではなく仕様である（`tests/unit/test_search_set.py` が固定している）
- 機関構成図（D7・組織ツリー）1点、附則の改正履歴表（C7）1点
- 常体（「…とする。」「…することができる。」）、項番号は全角数字「２」（第１項は無番号）

**travel**
- 第１章 用語の定義条項（条の形をとる定義表）、補償条項（治療・救援／賠償責任／携行品／航空機遅延 等から3つ以上）、携行品の品目別限度額表、基本条項（責任の始期・終期を「初日の午前０時／末日の午後１２時」のように時刻で明記する型）、サービス利用の流れ（D7・4ステップ）、保険期間と旅行行程のタイムライン（D5）

### 4.2 バリエーション軸（blueprint の `variants`、seed で選択）
- 章の並び順の許容範囲（現実的な範囲で入替可）、特約の本数と種類、定義語の個数、条の本数
- 会社形態（株式会社／相互会社）、商品ペットネームの有無、様式番号の形式
- 数字の全角／半角、％の全角／半角、和暦／西暦、金額表記（「1,000万円」「10,000,000円」）
- 前付けの有無（目的別もくじ・特約一覧・ペットネーム表）
- 図の複雑度（ノード数）、表の結合セル数
- スタイル側：A4/B5、1段/2段、明朝/ゴシック、罫線様式、ヘッダ・フッタ位置、欄外注の位置（条末／ページ下）

---

## 付録 A. style プリセット（初期 7 種）
| style_id | 判型 | 段 | 本文フォント/サイズ | 見出し | 表罫線 | 欄外注 | 用途 |
|---|---|---|---|---|---|---|---|
| `nl-a4-2col-mincho` | A4 | 2 | Noto Serif CJK 9.5pt | ゴシック太字 | grid | 条末 | auto/health/quake 標準 |
| `nl-a4-1col-gothic` | A4 | 1 | Noto Sans CJK 10pt | 帯付き | horizontal | ページ下 | oneday/travel |
| `nl-b5-2col-dense` | B5 | 2 | IPAex明朝 8.5pt | ゴシック | grid | 条末 | 高密度検証用 |
| `life-b5-1col-mincho` | B5 | 1 | Noto Serif CJK 10pt | 色帯・Q番号 | horizontal | 囲み | life |
| `life-a4-1col-gothic` | A4 | 1 | BIZ UDPゴシック 10.5pt | 帯付き | grid | 囲み | life 変種 |
| `teikan-a4-1col-mincho` | A4 | 1 | Noto Serif CJK 11pt | 中央揃え章題 | minimal | なし | teikan |
| `travel-a4-1col-gothic` | A4 | 1 | Noto Sans CJK 9.5pt | 帯付き・章番号色 | grid | 条末 | travel |

## 付録 B. blueprint YAML の形（抜粋）
```yaml
genre: auto
target_pages: [14, 20]
numbering_scheme: nonlife
default_style: nl-a4-2col-mincho
front_matter: { cover: true, preface: true, purpose_index: true, toc: {with_summaries: true, depth: 3}, rider_index: true, petname_table: {p: 0.5} }
skeleton:
  - { id: terms, kind: section, title_options: ["用語の定義"], required: [ {table: definitions, min_rows: 15} ] }
  - { id: ch1, kind: chapter, title_options: ["賠償責任条項", "賠償責任保険"],
      children:
        - { id: ch1_a1, kind: article, title_options: ["この条項の補償内容", "保険金を支払う場合"], required: [ {table: enumeration} ] }
        - { id: ch1_a4, kind: article, title_options: ["お支払いする保険金", "支払保険金"], required: [ {table: benefit_schedule, min_rows: 3}, {formula: inline_boxes} ] } }
  # …
riders: { count: [2, 3], pool: [rider_other_car, rider_family_bike, rider_lawyer_fee, rider_rentacar] }
figures_required: [ {kind: tree, where: front}, {kind: steps, where: guide}, {kind: flowchart, where: guide}, {kind: timeline, where: guide} ]
appendices_required: [ {id: app1, title: "後遺障害等級表", table: grade_schedule, min_rows: 10}, {id: app2, title: "短期率表", table: rate} ]
variants: { digit_style: {fullwidth: 0.7, halfwidth: 0.3}, era: {seireki: 0.8, wareki: 0.2}, issuer_kind: {stock: 0.9, mutual: 0.1} }
budget: { chars_min: 18000, chars_max: 32000 }
```

---

## 2026-09-22 に足したジャンル（参考 #9〜#14）

| genre | 参考 | default_style | 特徴 |
|---|---|---|---|
| `golf` | #11 | `nl-wide-2col-plain` | 賠償責任保険の**約款集**。202×188mm の横長小型判・2 段・完全な素組み。番号方式は nonlife のまま |
| `group` | #12〜#14 | `grp-a4-1col-mincho` | 団体保険。番号方式 `group`（項＝丸数字・号＝「１．」・細目＝(ｱ)）、`article_heading: above`、`footnote_style: remarks_box` |
| `jyusetsu` | #9・#10 | `jys-a4-1col-gothic` | 重要事項説明書。**条を持たない**（番号方式 `jyusetsu`、`article_heading: plain`）。見出しに `badges` が付く |

### blueprint に足したフィールド

- `article_heading: inline | above | plain`（既定 `inline`）：条見出しの体裁。scaffold が `meta` に写す。
- `footnote_style: inline | remarks_box`（既定 `inline`）：条末脚注の体裁。同上。
- 必須要素に `kind: badge` を追加。`subtype` にバッジの文字列、`min_count` に最低件数を書く。

### style に足したフィールド

- `page_number: plain | dashed`（既定 `plain`）：フッタのページ番号の書式。`dashed` は「− 3 −」（§3.1 E7）。

**新しい style を足したら `chars_per_page_estimate` を鵜呑みにしない。**
2 段組では較正値が同じ数字になることがある（`docs/gotchas.md`）。実際に 1 本描いてページ数を確かめる。
