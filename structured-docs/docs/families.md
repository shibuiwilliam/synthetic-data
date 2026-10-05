# families.md — ファミリー定義仕様と初期5ファミリーのカタログ

> `families/` 配下（family.yaml・numbering/・blueprints/・styles/・library/・denylist・hooks.py）を
> 触る作業、および新ファミリー・新 doctype の追加では、**着手前に必ず本ファイルを読む**こと。
> family.yaml の形は `docs/architecture.md` §3、numbering YAML の形は `docs/schema.md` §7。
> 本ファイルは「何を作るか」（各ファミリーの必須要素・バリエーション・様式）を定める。
>
> **2026-10-05 更新**：`contract` を keiyaku-synth の実績（10 doctype・骨格 5 類型・番号方式 3 種・
> style 4 種・50 content）に置き換えた（§2）。insurance は yakkan の v7（10 genre）に追随（§5）。
> **§9「既に実装のあるドメインをファミリーとして取り込む手順」を新設**した。

## 1. ファミリーの構成要素（ディレクトリ規約）

```
families/<family>/
  family.yaml            # 宣言の親玉（doctypes・schemes・semantic_types・lint・page_limit・tone）
  numbering/<scheme>.yaml
  blueprints/<doctype>.yaml
  styles/<style_id>.yaml + styles/css/<style_id>.css
  library/               # 条文ライブラリ（オリジナル文のみ。転載厳禁）
  denylist.txt           # 実在名の検出語（1行1語。部分一致）
  docs/
    structures.md        # 実在文書の構造分析カタログ＋分析ログ（docs/reference_structures.md の手順で作る）
    style.md             # ファミリー固有の文体・語彙・言い回し集
  hooks.py               # MAY。宣言で書けない numbering 例外・lint のみ
```

blueprint YAML の形は yakkan-synth の `../insurance-contracts/docs/blueprints.md` 付録B を踏襲する
（`genre:` → `family:`+`doctype:`、`page_limit` 追加。`article_heading` / `footnote_style` /
`caption_numbering` / `kind: badge` 要件など 2026-09-22 以降の追加フィールドを含む）。

## 2. contract（契約書）

**参照実装は `../contracts/`（keiyaku-synth）。** 10 doctype × 5 content ＝ 100 文書で成立済みであり、
本プロジェクトは**その資産を family 化する**（新規設計ではない。P3。取り込み手順は §9）。
当事者が 2 者以上あり、前文 → 条文 → 後文・記名押印欄 → 別紙、という骨格を持つ。常体が既定
（`license` `purchase` `employment` は敬体も実在する）。表紙なし・目次は長文型のみ。1 段組。

### 2.1 骨格 5 類型（**読み取り課題の幅そのもの**。keiyaku P1 の実測で確定）

| 類型 | 中身 | doctype |
|---|---|---|
| **条文型** | 前文 → 第1条… → 後文・記名押印欄。実在契約書の大多数 | nda / outsourcing / delegation / consulting / purchase / license / sysdev |
| **頭書型** | 冒頭に当事者・目的物・金額の一覧（頭書）を置き、本文が「頭書に記載の◯◯」と参照する | lease（purchase の variant） |
| **様式型** | **条を持たない**。記入欄が本体（労働条件通知書）。記名押印欄なし・選択欄あり | employment |
| **約款型** | **章を持たず**長文・**条番号が漢数字**（第一条）・条見出しが条番号の上 | contracting |
| **逐条解説型** | 条文＋解説枠が交互（`commentary`） | license の variant（v1 は 1〜2 本） |

### 2.2 doctype（10 種）

| doctype | 題材 | 目標ページ | 番号方式 | 固有の必須要素 |
|---|---|---|---|---|
| `nda` 秘密保持 | 取引検討に伴う NDA | 3–6 | contract-standard | 秘密情報の定義、例外列挙（enumeration）、返還・破棄、有効期間 |
| `outsourcing` 業務委託 | システム開発・運用委託 等 | 5–10 | contract-standard | 委託業務の別紙（deliverables）、報酬表（fee_schedule）、検収フロー図、再委託・知財・損害賠償 |
| `delegation` 準委任・作業委任 | 常駐・準委任 | 4–8 | contract-standard | 作業範囲・工数の表、報告義務、指揮命令関係の条 |
| `consulting` コンサルティング・顧問 | 顧問契約 | 4–8 | contract-standard | 報酬（月額・成功報酬）の表、成果物の帰属、competition 条項 |
| `purchase` 売買・物品購入 | 動産・機器の売買 | 3–8 | contract-standard | 目的物の目録（inventory）、代金・支払条件、危険負担・契約不適合（**頭書** variant・A3 横様式は P9） |
| `lease` 建物賃貸借 | 事務所賃貸借 | 8–14 | contract-standard | **頭書**（物件・賃料・期間）、賃料・共益費表、修繕分担表（allocation）、契約終了時の流れ |
| `license` ライセンス | 特許・商標・ノウハウ | 6–12 | contract-standard | 実施料表（fee_schedule）、許諾範囲、改良発明、（**逐条解説** variant） |
| `sysdev` システム開発（基本） | 基本契約＋個別契約 | 8–16 | contract-standard | **章立て＋目次**、個別契約を `schedule`（様式）として置く、検収・瑕疵・変更管理 |
| `contracting` 工事・製造請負 | 公共工事風の請負約款 | 10–18 | **contract-kanji** | **章なし**・長文・漢数字の条番号、前払金・部分払、工期変更、紛争処理 |
| `employment` 雇用・労働条件通知書 | 様式型 | 2–6 | **contract-form** | **条を持たない**（項目 1 →（1）→（ア）の 3 階層）、記入欄（form_fields）、選択欄 `■`/`□`、**記名押印欄なし** |

### 2.3 全 doctype 共通の必須要素

- `preamble`（前文。`{party:key|full}` による当事者の導入を含む）——**様式型を除く**
- `signature`（後文＋契約日＋記名押印欄）——**様式型を除く全 doctype 必須**。L20 が検査する
- `parties` ブロック（当事者表示）または前文内の導入（blueprint がどちらかを選ぶ）
- 一般条項（協議・合意管轄・通知・存続）から **2 条以上**
- 条項間参照 `{ref:}` **5 箇所以上**、定義語 `{term:}` **5 語以上**、別紙参照 1 箇所以上
- 表 **1 つ以上**・図 **1 つ以上**（keiyaku の実測：**実在の条文型契約書の本体には表も図も無いのが普通**
  ——39 件中、本体の図は 0 件。読み取り課題として要るので `required` には置くが**最低限にとどめ**、
  図は逐条解説つき variant を主な供給源にする）
- 末尾の disclaimer（L13）

keiyaku P1 で確定した観察：**項ラベルは第1項に番号を振る流儀と振らない流儀が両方ある**
（`contract-standard` は振らない側。振る側は variant）。**号の括弧は全角 `（1）` と半角 `(1)` が割れる**
（`digit_style` の variant で吸収）。

### 2.4 バリエーション軸

当事者の呼称（甲乙／委託者・受託者／役割名）、**三者契約**（連帯保証人・家賃債務保証業者。
`meta.parties` に 3 件並べ記名欄も 3 ブロック）、会社形態、条の本数、別紙の有無と数、
数字全角/半角、和暦/西暦、金額表記、反社条項・存続条項の有無、記名押印欄の並び
（`signature_layout: vertical | horizontal`）、頭書の型（表の連なり／番号付き項目の羅列）。

### 2.5 style プリセット（keiyaku から 4 種）

`ct-a4-1col-mincho`（明朝 10.5pt・既定）、`ct-a4-1col-gothic`（ゴシック 10pt・下線見出し）、
`ct-a4-1col-form`（**様式型**・ゴシック 9pt・太罫）、`ct-a3-landscape-form`（A3 横・2 段・官公庁様式。
**使う文書は v1 で 1 本まで**）。1 content は 1〜2 style、**2 style 目は版面が最も遠いものを選ぶ**。

## 3. terms（Webサービス利用規約・プライバシーポリシー）

単独名義（運営者）で、条または番号見出しの列＋箇条書きが主体。表は少なく、リストが深い。
敬体（「〜ものとします。」「〜ください。」）。改定条項と改定履歴を持つ。1 段組。
番号方式 `web-terms`（条「第1条（見出し）」型）と `web-numbered`（「1. 2. 3.」の数字見出し型）の 2 種を
用意し、doctype ごとに blueprint が選ぶ（実在の規約に両方の流儀があるため）。

| doctype | 題材 | 目標ページ | 固有の必須要素 |
|---|---|---|---|
| `tos` 利用規約 | SaaS／会員制Webサービス | 4–10 | 定義、アカウント・ID管理、禁止事項の列挙（enumeration・15項目以上・入れ子リスト）、料金プラン比較表（plan_matrix、有料サービスの場合）、免責、解約手続きの流れ（steps または flowchart）、改定条項＋改定履歴（revision_history） |
| `privacy` プライバシーポリシー | 同上の個人情報保護方針 | 3–8 | 取得する情報の項目表（mapping：情報の種類 × 取得方法 × 利用目的）、第三者提供・委託の列挙、Cookie 等の説明、開示請求手続きの流れ（steps）、問い合わせ窓口（架空）、改定履歴 |

共通の必須要素：運営者表示（issuer）、適用範囲の条、準拠法・管轄の条、
文末 disclaimer。深い入れ子リスト（3 階層）を 2 箇所以上（読み取り課題として重要）。

バリエーション軸：番号方式（web-terms / web-numbered）、サービスの種別（SaaS/EC/コミュニティ）、
禁止事項の項目数、料金表の有無、改定履歴の行数、見出しの装飾（帯/下線/無地）。

style プリセット（初期 2 種）：`tm-a4-1col-gothic`（Web 風・ゴシック・帯見出し）、
`tm-a4-1col-plain`（印刷配布風・明朝・無地見出し）。

## 4. regulations（社内規程・就業規則）

章-条-項-号の階層＋附則＋別表。制定・改正履歴を持つ。常体。目次あり。1 段組（B5/A4）。
番号方式 `kitei-standard`（章「第1章」／条「第1条（見出し）」・全編通し番号／項は算用数字・
第1項無番号／号「(1)」、附則は独立体系）。

| doctype | 題材 | 目標ページ | 固有の必須要素 |
|---|---|---|---|
| `shugyo` 就業規則 | 中小企業の就業規則 | 8–16 | 章立て（総則/採用/勤務/休暇/服務/賃金/退職/表彰懲戒 から 6 章以上）、労働時間・休憩の表、休暇一覧表、懲戒事由の列挙、賃金体系の別表（wage_table）、手続きフロー図 1 点以上、附則（施行日）＋改正履歴表 |
| `kitei` 一般規程 | 文書管理規程・経費精算規程 等 | 4–10 | 総則（目的/適用範囲/用語）、主要手続きの条、承認フロー図（flowchart）、権限表（mapping：事項 × 決裁者）、様式への参照（「様式第1号」＝架空）、附則＋改正履歴 |

バリエーション軸：会社規模・業種（語彙が変わる）、章構成、別表の数、
改正履歴の行数（1〜8 行）、条数、様式参照の有無。

style プリセット（初期 2 種）：`rg-a4-1col-mincho`（規程集風・明朝）、`rg-b5-1col-mincho`（冊子風・B5）。

## 5. insurance（保険約款）— yakkan からの移植

目的と位置づけは `docs/architecture.md` §6（同等性検証）。yakkan の最終形（`dataset_version: v7`）は
**10 genre**（auto / oneday / quake / health / life / teikan / travel / golf / group / jyusetsu）・
**100 content・114 文書**・番号方式 5 種（nonlife / life / teikan / group / jyusetsu）・style 13 種である。

- **P2（同等性）ではまず `oneday` と `teikan`** を移植する（小型で、nonlife と teikan の
  2 方式・素組みと標準の 2 体裁をカバーする）。各 3 本。
- 残り 8 genre は P2 の同等性 golden が安定してから順次移す（P7 のバッチ設計時に判断）。
  移すときは blueprint・styles・library・denylist をコピーし、`genre:` → `doctype:` の読み替えだけを行う。
- numbering は 5 方式を YAML 化する（`docs/schema.md` §7 の golden 対象。**group の
  「第1項無番号＋参照は書き下し」、jyusetsu の「条を持たない」もここで宣言に落ちることを確認する**。
  宣言で書けなければ hooks へ——それ自体が「宣言スキーマの表現力」の実地検証になる）。
- yakkan の `content/`（執筆成果）はコピーせず読み取り専用参照（`docs/architecture.md` §6）。
- insurance 固有の機構（`rider`＝特約・`badges`＝見出し右の分類ラベル・`kind_label`＝別表の呼び名・
  `article_heading: above` の run-in ラベル・`footnote_style: remarks_box`）は**コアの機構として継承**し、
  他ファミリーからも使えるようにする（`docs/schema.md` §1.1）。

## 6. statute（法令）— 新設（2026-09-26）

法律・条例の体裁を持つ文書。**完全に架空の法令**（実在法令の再現ではない）。
編・章・節・款・目・条・項・号・イロハの深い階層、漢数字カウンタ、条見出しが条の上の行に
括弧書きで置かれる体裁、目次の条範囲、附則の多層化、別表の「（第◯条関係）」という、
他ファミリーに無い読み取り課題を提供する。スキーマ差分は `docs/schema.md` §11。

番号方式 `horei`（条「第一条」漢数字・全編通し／条見出しは条の上に「（定義）」／
項「２」全角・第1項無番号／号「一 二 三」／細目「イ ロ ハ」／別表「別表第一（第◯条関係）」）。
variant で算用数字体（第1条。デジタル原本の体裁）を選べる。常体（「〜とする。」「〜してはならない。」）。
1 段組。目次あり（章名＋条範囲）。

| doctype | 題材 | 目標ページ | 固有の必須要素 |
|---|---|---|---|
| `law` 法律風 | 架空の業規制法・安全確保法 等 | 6–14 | 目次（章名＋条範囲）、総則章（目的・定義。定義の号が 8 個以上・イロハの細目 1 箇所以上）、義務・禁止の章、監督（報告・立入検査）の章、罰則の章（罰則一覧 penalty_schedule または条の列挙）、附則（施行期日・経過措置）、別表 1 点以上（（第◯条関係）つき）、条の枝番 1 箇所以上（number_override） |
| `jorei` 条例 | 架空自治体の生活環境・景観条例 等 | 4–10 | 公布情報（「◯◯市条例第◯号」）、総則（目的・定義）、規制・手続きの章（許可申請の flowchart または steps）、雑則・罰則（過料）、附則、別表（mapping または rate） |

共通の必須要素：
- `meta.promulgation`（公布番号・公布日。§11.1）
- 前文は MAY（基本条例型の variant でのみ使う）
- 条項間参照 `{ref:}` 10 箇所以上（「前条」「第◯条第◯項」相当はすべてトークンで）、
  別表参照 1 箇所以上、みなし・準用の条 1 箇所以上
- 読替え表（reading_replacement・2 列「読み替えられる字句／読み替える字句」）は law の variant

バリエーション軸：漢数字/算用数字、章の数（節・款を使うか）、枝番の有無と数、
改正附則の有無（附則が 2 つ以上になる）、罰則の体裁（条の列挙 or 一覧表）、
読替え表の有無、定義の置き方（第2条一括 or 各章冒頭）。

style プリセット（初期 2 種）：`st-a4-1col-mincho`（法令集風・明朝 10.5pt・見出し無装飾）、
`st-b5-1col-mincho`（例規集冊子風・B5・高密度）。

statute 固有の注意：

- **転載リスクの注意点が他ファミリーと逆向き**になる。法令の条文自体は著作権の対象外だが、
  本プロジェクトの生成文書は**実在法令の文章を写さずオリジナルに書く**（CLAUDE.md §0.4-1 は
  参考文書の別を問わず適用する）。「〜の許可を受けなければならない」級の法令定型句は
  業界共通表現として許容し、**特定の実在法令に固有の定義列挙・数値基準・別表の構成**を写さない
  （yakkan の教訓：模倣は文章より「数値の列」「列挙の順序」「別表特有の語形」に出る）。
- 題名・自治体名は denylist で検出（実在法令名・実在自治体名を収載）。
- `law_number` が実在法令の番号と偶然一致しうる点は HITL レビュー項目
  （`docs/validation_plan.md`）。

## 7. 新ファミリー追加の手順（P9 でこの手順書自体を検証する）

1. `docs/reference_structures.md` の手順で実在文書の構造分析を行い、`families/<f>/docs/structures.md` に
   読み取り課題カタログと分析ログを書く（**文章は 1 文も写さない**）。
2. `family.yaml` を書く（doctypes・numbering_schemes・semantic_types・page_limit・tone・lint）。
3. `numbering/<scheme>.yaml` を書き、`tests/unit` にラベル・`{ref:}` 解決の golden を足す。
4. `blueprints/<doctype>.yaml` を書く（骨組み・required_elements・variants・budget）。
   **必須要素は構造で縛り、semantic_type で題材を縛らない**（yakkan D4：型を偽らせる誘因になる）。
5. `styles/` を 1 種作り、`docsynth scaffold` → 最小サンプルを執筆 → `lint/build/render/verify` を通す。
   **新 style の `chars_per_page_estimate` を鵜呑みにしない**——1 本描いて実ページ数で較正する
   （yakkan R6：2 段組で別版面が同じ較正値になった実例）。
6. **全ページ PNG を目視**（`docsynth review`）。新ファミリー初回は CLAUDE.md §0.4-7 のとおり必須。
   verify が通っても目視でしか見つからない欠陥がある（yakkan X4：図の辺ラベルの重なり）。
7. `families/<f>/docs/style.md` に文体・語彙を書き、denylist を整備してから本執筆に入る。
8. 執筆 QA を書いたら `docsynth qa --validate`（L14）と lint（L16）を通す。
9. ここまでで hooks.py が必要になった場合は、その理由を `docs/decisions.md` に記録する。
10. **目視でしか見つからなかった欠陥は lint / verify に落とす。** 新設の番号は L27 以降
    （ファミリー内で済むものは FLxx）。`docs/lint_rules.md` と CLAUDE.md §8 の両方を更新する。
11. `docsynth export` → **`docsynth datacard update`** を回し、データカードの
    「母数の小さい観点」欄にそのファミリーの観点が出ていないかを見る（`docs/data_card.md` §4.3）。
12. 最後に、そのファミリーの文書 1 本を**盲検読み取り**（`docs/validation_plan.md` §4）に通し、
    契約（evaluation.md の語彙）で採点まで到達することを確かめる。**内部構造を知らない読み手で
    しか見つからない契約の穴がある**（yakkan Z2：3 ジャンルの盲検で 2 ジャンルから欠陥が出た）。
    実例は `docsynth eval --oracle --dump-pred` で正解から出す（手書きの実例は仕様とずれる）。

## 8. ファミリー横断の禁止事項

- ファミリーをまたぐ import（`families/contract/` から `families/terms/` を参照）は禁止。
  共有したい語彙・規則が出たらコアへ昇格させる。
- `library/` の文はファミリー内でもコピペ増殖させない（L15 類似度検査の対象）。
- denylist の共通部分（大手企業名等の汎用実在名）はコアの `docsynth/lint/denylist_common.txt` に置き、
  ファミリー側は業界固有名（保険会社・実在サービス・実在法令・実在自治体）だけを持つ。
- doctype 名はファミリーをまたいで一意にする（`docsynth families` が衝突を検査）。

## 9. 既に実装のあるドメインをファミリーとして取り込む手順（P2〜P3 の contract / insurance）

新規に設計する §7 とは別に、**姉妹プロジェクトで完成しているドメインを family 化する**手順を持つ。
新規設計との違いは「**構造分析と執筆をやり直さない**」ことである。

1. 供給元の宣言（`blueprints/` `numbering/` `styles/` `library/` `denylist.txt`）を
   `families/<f>/` 配下へ**そのままコピー**する。`genre:` / 固定値の `family:` を読み替えるだけで、
   **数値・文章・順序を触らない**（触ると同等性 golden が壊れ、転載の指紋の判断もやり直しになる）。
2. `family.yaml` を書く。**供給元でコードに直書きされていた既定値**（tone・page_limit・QA 配分・
   骨格要件・semantic_type の語彙）をここに移す。何を移したかを `docs/decisions.md` に列挙する。
3. 供給元の `docs/` から、ファミリー固有の知識だけを `families/<f>/docs/` に移す
   （`structures.md` ＝課題カタログと分析ログ、`style.md` ＝文体・語彙）。
   **コア横断の知識（gotchas・評価・lint の仕組み）は本リポジトリの `docs/` 側に統合する。**
4. 供給元の `content/` を**読み取り専用参照**として同等性テストに掛け（`docs/architecture.md` §6）、
   一致を確認してから `content/` へ移す。一致しない差分は「新コアのバグ」が既定。
5. `docsynth export` → `datacard update` を回し、**供給元の実測値と規模が一致する**ことを確かめる
   （ページ数・表・図・QA 件数。カードは実ファイルから測るので、ずれていれば移植漏れである）。
6. 供給元の `authoring_checklist` に固有項目があれば `docs/authoring_checklist.md` に統合する。
