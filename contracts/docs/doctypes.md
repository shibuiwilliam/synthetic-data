# doctypes.md — 10 doctype のカタログ・番号方式・style プリセット

> `blueprints/` `numbering/` `styles/` `keiyaku/scaffold.py` `compose.py` を触る作業、
> および新 doctype・新 style の追加では、**着手前に必ず本ファイルを読む**こと。
> doctype 一覧の要約（名称・骨格・目標ページ）は CLAUDE.md §4 にある。本ファイルは
> 「**何を必ず入れるか**」（必須要素・variants・分量）を定める。
> blueprint YAML の形の基底は `../insurance-contracts/docs/blueprints.md` 付録B。
>
> **必須要素は「構造」で縛り、「題材」で縛らない。** 「`fee_schedule` の表が 1 つ」ではなく
> 「報酬・対価に関する表が 1 つ（最低 3 行）」のように、**執筆者が semantic_type を偽らずに
> 満たせる形**で書く（yakkan D4：型を偽らせる誘因になった）。

## 1. blueprint YAML の形

```yaml
doctype: nda
family: contract
description: 取引検討に伴う秘密保持契約書。最小構成の条文型
target_pages: [3, 6]
page_limit: 8                      # lint L09 / verify V-P2 の上限（既定 12・絶対上限 20）
numbering_scheme: contract-standard
default_style: ct-a4-1col-mincho
skeleton_kind: articles            # articles（条文型）| head_matter（頭書型）| form（様式型）| chaptered（章立て）
tone: dearu                        # dearu（常体・既定）| desumasu（敬体）。L10 がこれに従って判定する
                                   # P1 の実測で敬体の実物が 5 件あった（docs/decisions.md 63）
front_matter: { cover: false, toc: false }
parties:
  count: [2, 2]                    # 当事者の数の範囲
  presets:                         # variant で選ばれる呼称の組（alias と role_label）
    - [{ key: discloser, alias: 甲, role_label: 開示者 }, { key: receiver, alias: 乙, role_label: 受領者 }]
    - [{ key: partyA, alias: 甲, role_label: 甲 },        { key: partyB, alias: 乙, role_label: 乙 }]
required:                          # L04。構造で縛る
  - { kind: node, subtype: preamble, min_count: 1 }
  - { kind: node, subtype: signature, min_count: 1 }
  - { kind: table, min_count: 1, min_rows: 4, note: "定義または例外の表（semantic_type は執筆者が決める）" }
  - { kind: enumeration, min_count: 2, min_items: 4, note: "秘密情報の例外・禁止行為の列挙" }
  - { kind: figure, min_count: 1, note: "有効期間か情報の流れ（種別は執筆者が決める）" }
  - { kind: ref, min_count: 5 }    # 条項間参照
  - { kind: term, min_count: 5 }   # 定義語
skeleton:                          # scaffold が出す執筆スケルトン
  - { id: pre,  kind: preamble, chars: 200, todo: "{party:...|full} で両当事者を導入する" }
  - { id: a1,   kind: article, title_options: ["目的"], chars: 300 }
  - { id: a2,   kind: article, title_options: ["秘密情報", "秘密情報の定義"], chars: 700,
      required: [{ kind: table, min_rows: 4 }] }
  # …
appendices: []
authored_qa: { count: 15, table_min: 3, figure_min: 2, apply_min: 2 }   # L16
variants:
  digit_style: { fullwidth: 0.4, halfwidth: 0.6 }
  era:         { seireki: 0.8, wareki: 0.2 }
  parties_preset: [0, 1]
  copies:      { 2: 0.8, 1: 0.2 }
  stamp_duty:  { true: 0.2, false: 0.8 }
  styles: [ct-a4-1col-mincho, ct-a4-1col-gothic]
budget: { chars_min: 3000, chars_max: 7000, footnotes_min: 0 }
closing_options:                   # 後文の言い回し（build が copies を埋める）
  - "本契約の成立を証するため、本書{copies}通を作成し、{parties}記名押印のうえ、各1通を保有する。"
```

## 2. 全 doctype 共通の必須要素

- `preamble`（前文。`{party:...|full}` による当事者の導入を含む）——**様式型を除く**
- `signature`（後文＋契約日＋記名押印欄）——**全 doctype 必須**
- `parties` ブロック（当事者表示）または前文内の導入（blueprint がどちらかを選ぶ）
- 一般条項（協議・合意管轄・通知・存続）から **2 条以上**
- 条項間参照 `{ref:}` **5 箇所以上**、定義語 `{term:}` **5 語以上**
- 表 **1 つ以上**（`employment` は多数）、図 **1 つ以上**
- 末尾の disclaimer（`meta.disclaimer` → colophon。L13）

**P1（2026-09-27）で確定した共通の観察**（`docs/reference_structures.md` §4）：
- **条文型の契約書本体に表も図も無いのが普通**（39 件中、本体の図は 0 件）。
  読み取り課題としては要るので、`required` には置くが**最低限の件数にとどめ**、
  図は逐条解説つき variant を主な供給源にする（`docs/decisions.md` 64）。
- 項ラベルは**第1項に番号を振る流儀と振らない流儀が両方ある**。`contract-standard` は振らない側。
  振る側は variant（`paragraph_first_label`）で持つ。
- 号の括弧は**全角 `（1）` と半角 `(1)` が割れる**。`digit_style` の variant で吸収する。

## 3. 条文型（P3）

### 3.1 `nda` 秘密保持契約書
参考 `samples/nda/`（中小企業庁ひな型・経産省ハンドブック参考例・特許庁モデル契約・法律事務所サンプル）。
最小構成で、**構造が浅く列挙が深い**のが特徴。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 3–6 ／ 8 ページ |
| 固有の必須要素 | 秘密情報の定義（定義条または `definitions` 表）／**例外の列挙**（公知・独自開発・第三者取得 等を 4 項目以上）／目的外使用の禁止／複製・開示範囲／返還・廃棄／有効期間と**存続期間**（契約終了後 N 年）／損害賠償・差止 |
| 図 | 有効期間のタイムライン（`timeline`）または情報の授受の流れ（`flowchart`） |
| 読み取りの狙い | 深い列挙（号 →「ア イ ウ」）／「契約期間」と「秘密保持義務の存続期間」の**似て非なる 2 つの期間**の弁別（`apply` QA の題材） |
| variants | 一方向／双方向（`parties_preset` で開示者・受領者 or 甲乙）／目的の題材（業務提携検討・システム導入検討・共同研究）／存続期間（3・5・10 年） |

### 3.2 `outsourcing` 業務委託契約書
参考 `samples/outsourcing/`（厚労省在宅ワーク参考例・公取委フリーランス法ひな型・法律事務所サンプル）。
**別紙で業務内容と報酬を定める**型。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 5–10 ／ 12 ページ |
| 固有の必須要素 | 委託業務の内容（**別紙**参照）／委託料と支払方法（表。3 行以上）／検査・検収の手続き／再委託の可否／知的財産権の帰属／秘密保持／個人情報の取扱い／反社条項／解除・中途解約 |
| 別紙 | 「別紙1 委託業務の内容」（`deliverables`）＋「別紙2 委託料」（`fee_schedule`）の 2 点以上 |
| 図 | 検収フロー（`flowchart`。差戻しの分岐を持たせる）または月次の業務サイクル（`steps`） |
| 読み取りの狙い | 別紙参照（`{ref:sch1}`）と本文の対応／検収期限の期間計算（`apply`）／再委託の条件の入れ子 |
| variants | 請負型／準委任型（「成果物の完成」か「業務の遂行」か——**条文の書き分けが変わる**）／継続（月額）か単発（一括）／フリーランス相手か法人相手（明示義務の条が増える） |

### 3.3 `delegation` 準委任・作業委任契約書
参考 `samples/work_delegation/`（経産省モデル契約書の保守運用編・中小機構の委嘱型・法律事務所サンプル）。
`outsourcing` と近いが、**「成果物の完成を約さない」ことを明記する**点が骨格上の違い。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 4–8 ／ 10 ページ |
| 固有の必須要素 | 準委任であることの明記／作業の範囲と場所・時間／報告義務（頻度を明記）／指揮命令関係の否定（偽装請負の回避条項）／費用の負担区分（表）／善管注意義務／再委任 |
| 表 | 費用の負担区分（`allocation`。項目 × 当事者、○△× の凡例つき） |
| 図 | 報告・承認のサイクル（`steps` または `flowchart`） |
| 読み取りの狙い | `allocation` 表の意味座標（どの費用がどちらの負担か）／報告頻度と期限の数値整合 |
| variants | 常駐／非常駐／時間単価精算（上限時間つき）／定額 |

### 3.4 `consulting` コンサルティング・顧問契約書
参考 `samples/consulting/`（中小機構・法律事務所の経営顧問契約・不動産コンサル）。
**月額固定報酬＋成功報酬**の構造と、助言の性質（結果を保証しない）が特徴。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 4–8 ／ 10 ページ |
| 固有の必須要素 | 業務の範囲（助言事項の列挙 5 項目以上）／報酬（月額・時間外・成功報酬の**3 段構成の表**）／成果の非保証条項／利益相反・競業の制限／資料の提供と返還／秘密保持／契約期間と自動更新（更新拒絶の通知期間を明記） |
| 図 | 契約期間と自動更新・通知期限のタイムライン（`timeline`） |
| 読み取りの狙い | 3 段報酬表の意味座標／**自動更新の通知期限の逆算**（`apply`：「◯月◯日に終了させるには通知はいつまでか」） |
| variants | 月額のみ／月額＋成功報酬／顧問（名義貸しを含まない旨を明記）／業種（IT・不動産・人事） |

## 4. 別紙・目録型（P4）

### 4.1 `purchase` 売買・物品購入契約書
参考 `samples/purchase/`（国交省物品購入様式・日本サッシ協会の商取引基本契約・AMED 物品売買・法律事務所）。
**目的物の目録**と、継続的取引（基本契約）か単発かの二型を持つ。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 3–8 ／ 10 ページ |
| 固有の必須要素 | 目的物の表示（**目録**。`inventory`。品名 × 規格 × 数量 × 単価 × 金額。4 行以上）／代金と支払条件／引渡しの時期・場所・方法／検査と不合格品の処理／**所有権移転と危険負担の時期**（別々に定める）／契約不適合責任（期間を明記）／遅延損害金（利率） |
| 図 | 発注から検収・支払までの流れ（`steps` 4 段以上） |
| 読み取りの狙い | 目録表の合計値と本文の代金の整合（L11・`apply`）／所有権移転と危険負担の**時期の違い**の弁別／遅延損害金の日割計算（`apply`） |
| variants | 単発売買／継続的取引の基本契約（個別契約は別紙）／**頭書型**（冒頭に `1`〜`5` の番号付き項目で条件をまとめ、本文が「頭書の…」で参照する。CT4）／官公庁様式風（**A3 横 1 枚**・`ct-a3-landscape-form`。P8）／検査の有無 |

### 4.2 `lease` 建物賃貸借契約書（**頭書型**）
参考 `samples/lease/`（国交省 賃貸住宅標準契約書・定期賃貸住宅標準契約書・法律事務所の建物賃貸借）。
**冒頭の頭書に当事者・物件・期間・賃料をすべて表で置き、条文は頭書を参照する**という、
他 doctype に無い構造を持つ。**本プロジェクトで最も読み取り課題の密度が高い doctype。**

| 項目 | 内容 |
|---|---|
| 目標／上限 | 8–14 ／ 16 ページ |
| 固有の必須要素 | **頭書**（`head_matter`：物件の表示／契約期間／賃料・共益費／敷金／当事者・仲介業者。`{const:}` 経由で本文と一致）／賃料の支払（期日・方法）／敷金の充当と返還／**修繕の分担表**（`allocation`：部位 × 貸主/借主。8 行以上）／禁止行為の列挙／契約の解除／明渡しと原状回復／連帯保証人または家賃債務保証業者の条 |
| 別紙 | 「別表 修繕費用の負担区分」または「別紙 物件の間取り・付属設備」1 点以上 |
| 図 | 明渡しまでの手続きの流れ（`steps`）または契約期間・更新・解約通知のタイムライン（`timeline`） |
| 読み取りの狙い | **頭書の値 ↔ 条文の参照**（「頭書に記載の賃料」）／修繕分担表の意味座標／日割賃料の計算（`apply`）／定期借家の場合の「更新がない旨の説明」の別紙 |
| variants | 普通借家／**定期借家**（更新がない旨の事前説明書面を別紙に持つ）／居住用／事業用（消費税の扱いが変わる）／当事者 2 者（連帯保証人なし）／**3 者**（家賃債務保証業者つき） |

### 4.3 `license` ライセンス契約書
参考 `samples/license/`（INPIT 特許実施許諾・特許ノウハウ・商標使用許諾、特許庁モデル契約 新素材・M&A版）。
**実施料の算定と報告義務**が中心。参考文書の多くが**逐条解説つき**なので、
`commentary` の試験台にする（P5）。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 6–12 ／ 14 ページ |
| 固有の必須要素 | 対象権利の表示（**別表**。登録番号（架空）× 名称 × 出願日 等。3 行以上）／許諾の範囲（地域・期間・態様・独占/非独占）／**実施料**（一時金＋ランニング。料率表 `fee_schedule`）／報告と監査（頻度・方法）／改良発明の取扱い／保証と非保証（第三者権利の不侵害を保証しない旨）／権利の不争義務／契約終了後の在庫処理 |
| 図 | 実施料の算定・報告・支払のサイクル（`steps` または `flowchart`） |
| 読み取りの狙い | 料率表の階層（売上区分 × 料率）の意味座標／実施料の算出（`apply`：「売上が◯円のときの実施料」）／**逐条解説と本文の分離**（variant） |
| variants | 特許／商標／ノウハウ併存（**対象権利の表が変わる**）／独占／非独占／逐条解説あり（`commentary`・P5）／サブライセンス可否 |

## 5. 様式型・長文型（P5）

### 5.1 `employment` 雇用契約書・労働条件通知書（**様式型**）
参考 `samples/employment/`（厚労省モデル労働条件通知書 常用/有期・日雇型、労働局の記載例、
ハローワークの雇入通知書）。**条を 1 つも持たない。** 項目番号 → (1) → ① の 3 階層で、
本体は**記入欄の表**。yakkan の `jyusetsu`（重要事項説明書）の機構をそのまま使う。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 2–6 ／ 8 ページ |
| 番号方式 | **`contract-form`**（条なし。`docs/schema.md` §7.2） |
| 固有の必須要素 | 交付者・受領者の表示／契約期間（**有期／無期の選択欄**）／就業の場所・従事すべき業務／始業終業時刻・休憩・所定外労働／休日・休暇／**賃金**（基本賃金・諸手当・割増率・支払方法・控除。`form_fields` の表で 10 行以上）／退職に関する事項／社会保険・雇用保険の適用／相談窓口 |
| 表 | `form_fields` を 3 つ以上（労働時間・賃金・休暇）。**選択欄は ☑ □ をセルのテキストで表し `records` に選択結果を持たせる**（`docs/schema.md` §11.2） |
| 図 | 1 日の勤務時間帯（`timeline`）または所定労働時間の内訳（`matrix`） |
| 読み取りの狙い | **チェックボックスの選択状態**／罫線の多い表の `header_cols` 宣言／項目名（行見出し）と記載内容の対応／割増賃金の計算（`apply`） |
| variants | 常用（無期）／有期／日雇型／短時間労働者（所定労働時間の記載が増える）／変形労働時間制の有無 |
| 注意 | **実在の厚労省様式の項目の並びと語形をそのまま写さない**（§0.4-1 の「列挙の順序」が指紋になる典型）。項目の順序を変え、語形を言い換える |
| P1 の実測 | 本体は**2 列の巨大表**（左＝項目名・右＝記載内容）。右列の中の階層は `1` → `(1)` → `・` で `①` は出ない。**選択は `☑` ではなく「該当を `〇` で囲む」「`有・無` の一方を囲む」**（CT7・CT18）。`□` は `consulting` の表形式にだけ現れた。当事者は表の行として導入し、**記名押印欄を持たない**（L20 の骨格検査を様式型では緩める必要がある） |

### 5.2 `contracting` 工事・製造請負契約書（**約款型**）
参考 `samples/contracting/`（公共工事標準請負契約約款・建設工事標準下請契約約款・関東地方整備局 工事請負契約書様式・製造委託契約書）。
**章を持たない長文**で、条文が細かく、約款としての体裁を持つ。
**P1 の実測（2026-09-27）：約款型 3 件とも `第N章` が 0 件**。条は章を挟まず通し番号で 100〜233 件並び、
**条番号は漢数字**（`第一条`）。1 つの条に 12 項まで付く。章立ては `sysdev` にだけ現れた
（`docs/reference_structures.md` §4 の #9・#10）。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 10–18 ／ 20 ページ |
| 固有の必須要素 | **章を使わず条 40 本以上の通し番号**（総則／施工（製造）／請負代金／完成・引渡し／担保責任／解除 の主題を順に並べる）／工事（製造）の内容と工期（**別紙の仕様書・工程表**）／請負代金額と**支払方法**（前払金・部分払・精算の 3 段。表）／設計変更と代金の増減／monitoring（監督・検査）／**危険負担と不可抗力**／瑕疵（契約不適合）の担保期間／遅延違約金（率）／下請の制限／紛争の解決（協議・あっせん） |
| 別紙 | 「別紙1 仕様書」「別紙2 工程表」＋「別表 部分払の割合」1 点以上 |
| 図 | 工程と支払時期のタイムライン（`timeline`。工期・部分払・引渡しを重ねる）＋検査・引渡しのフロー（`flowchart`） |
| 目次 | **なし**（実物 3 件とも目次を持たない。長文でのヘッダ章名は `sysdev` で試す） |
| 番号方式 | **`contract-kanji`**（漢数字の条番号・枝番。CT23・CT24。P5 で `numbering/contract-kanji.yaml` を起こす） |
| 読み取りの狙い | **章の無い 200 本近い条の通し番号**／条 → 項 → 号の outline／部分払の割合表と本文の整合／漢数字ラベルの読み取り |
| variants | 公共工事風／民間工事／製造委託（建設以外）／`article_heading: above`（実物はこちらが主）／`footnote_style: remarks_box` |

### 5.3 `sysdev` システム開発（基本）契約書
参考 `samples/system_development/`（経産省 情報システム・モデル取引契約書、IPA アジャイル開発版、
JISA ソフトウェア開発委託基本モデル契約）。**基本契約＋個別契約**の二層構造と、
多段階の工程（要件定義・設計・開発・テスト）が特徴。

| 項目 | 内容 |
|---|---|
| 目標／上限 | 8–16 ／ 18 ページ |
| 固有の必須要素 | 基本契約と**個別契約**の関係（優先順位を明記）／個別契約の成立要件（注文書・請書）／工程と成果物の一覧（`deliverables`。工程 × 成果物 × 期限。5 行以上）／**検収の手続きとみなし検収**／変更管理の手続き（協議・書面合意）／知的財産権（著作権・特許・OSS の扱い）／再委託／秘密保持と個人情報／**責任の制限**（上限額を明記）／契約不適合責任の期間 |
| 別紙 | 「個別契約書（様式）」（`kind_label: 様式`）＋「別紙 作業分担表」（`allocation`：工程 × 甲/乙の役割） |
| 図 | 開発工程と成果物・検収のフロー（`flowchart`。差戻しの分岐つき）または工程のタイムライン |
| 目次 | あり（章立ての variant のみ） |
| 読み取りの狙い | **基本契約 ↔ 個別契約の参照**（`{ref:}` が様式へ飛ぶ）／工程表の意味座標／みなし検収の期間計算（`apply`）／責任上限額の数値整合 |
| variants | ウォーターフォール（工程ごとの請負・準委任の切り分け）／アジャイル（準委任・スプリント）／章立てあり／なし |

## 6. 番号方式の割当

| doctype | scheme | 章を使うか | `article_heading` | `caption_numbering` |
|---|---|---|---|---|
| `nda` `delegation` `consulting` | contract-standard | 使わない | inline | flat |
| `outsourcing` `purchase` `license` | contract-standard | variant で使う | inline | flat（章ありなら chapter） |
| `lease` | contract-standard | 使わない | inline | flat |
| `contracting` | **contract-kanji** | **使わない**（実測） | above | flat |
| `sysdev` | contract-standard | **使う**（章 → 節 → 条） | inline | chapter |
| `employment` | **contract-form** | （最上位が項目番号） | plain | flat |

## 7. style プリセット（初期 3 種＋拡張 1 種）

| style_id | 判型 | 段 | 本文 | 見出し | 表罫線 | フッタ | 主な用途 |
|---|---|---|---|---|---|---|---|
| `ct-a4-1col-mincho` | A4 | 1 | Noto Serif JP 10.5pt | 無装飾・条見出し太字 | grid | `- 1 -`（`page_number: dashed`） | 既定。条文型・頭書型 |
| `ct-a4-1col-gothic` | A4 | 1 | Noto Sans JP 10pt | 下線 | horizontal | プレーン数字 | 法律事務所サンプル風・短い契約 |
| `ct-a4-1col-form` | A4 | 1 | Noto Sans JP 9pt | 帯なし・項目番号太字 | grid（太め） | プレーン数字＋様式番号 | **様式型**（`employment`・官公庁様式風） |
| `ct-a3-landscape-form` | **A3 横**（1191×842pt） | **2** | Noto Sans JP 9pt | 同上 | grid（太め） | プレーン数字＋様式番号 | **実装済み**（2026-10-03）。`purchase` の官公庁様式（1 枚を**左右 2 面**に使う＝2 段で表す） |

- style YAML の形は yakkan と同じ（`page` / `columns` / `fonts` / `sizes` / `palette` / `headings` /
  `table` / `margin_note` / `page_number` / `chars_per_page_estimate`）。契約書では
  `parties_style: table | lines` と `signature_layout: vertical | horizontal` を追加する。
- **ヘッダは既定なし**（実物の契約書はヘッダを持たないものが多い）。`contract_number` を持つ variant では
  右上に契約書番号を置く。約款型・長文型は「題名＋章名」のヘッダを使う。
- **新しい style を足したら `chars_per_page_estimate` を鵜呑みにしない。**
  1 本描いて実ページ数で較正する（yakkan R6：別版面が同じ較正値になった実例がある）。
  手順：`keiyaku render <content> --style <新 style> --out <一時ディレクトリ>` →
  出力を `dataset/` へ一時的に置く → `uv run python scripts/calibrate_styles.py --write` →
  一時ディレクトリを消す（`dataset/` を汚さない）。`ct-a3-landscape-form` は 2600 → **2638** になった。
- **style ごとの CSS テンプレートが要る**（`styles/css/<style_id>.css.j2`）。無いと
  `TemplateNotFound` で render が落ちる。差分だけ書き、近い style を `{% include %}` する。
- **2 段を使う style では段またぎ要素（`column-span: all`）を置かない。**
  WeasyPrint は段に収まらない段またぎ要素があると**以降の内容を黙って捨てる**（CLAUDE.md §14）。
  `render` の内容欠落検出が最後の砦なので、2 段の style を足したら必ず PNG も見ること。
- 1 content は 1〜2 style で描画する。**2 style 目は「版面が最も遠いもの」を選ぶ**
  （明朝 1 段 ↔ 様式型のような差。同系の style を重ねてもレイアウト頑健性の検証にならない）。

## 8. 新 doctype を足す手順

1. `docs/reference_structures.md` の手順で参考文書を**構造だけ**分析し、課題カタログに追記する。
2. `blueprints/<doctype>.yaml` を書く（§1 の形。`required` は**構造で縛る**）。
3. 既存の numbering で足りるか確かめる。足りなければ `numbering/<scheme>.yaml` を足し、
   `tests/unit` にラベルと `{ref:}` 解決の golden を足す。
4. 既存 style で描けるか確かめる。新 style を作るなら較正を実測でやる（§7）。
5. `keiyaku scaffold` → 1 本執筆 → `lint` / `build` / `render` / `verify` → **全ページ PNG を目視**。
6. `keiyaku doctypes` で doctype 名の衝突と参照先（scheme・style）の存在を検査する。
7. 執筆 QA 15 問を書き、`keiyaku qa --validate`（L14）と `lint`（L16）を通す。
8. 最後にその doctype の 1 本を**盲検読み取り**（`docs/validation_plan.md` §4）に通す。
   **内部構造を知らない読み手でしか見つからない契約の穴がある。**
