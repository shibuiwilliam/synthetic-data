# families.md — ファミリー定義仕様と初期4ファミリーのカタログ

> `families/` 配下（family.yaml・numbering/・blueprints/・styles/・library/・denylist・hooks.py）を
> 触る作業、および新ファミリー・新 doctype の追加では、**着手前に必ず本ファイルを読む**こと。
> family.yaml の形は `docs/architecture.md` §3、numbering YAML の形は `docs/schema.md` §7。
> 本ファイルは「何を作るか」（各ファミリーの必須要素・バリエーション・様式）を定める。

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
（`genre:` → `family:`+`doctype:`、`page_limit` 追加）。

## 2. contract（契約書）

当事者が 2 者以上あり、前文 → 条文 → 後文・記名押印欄 → 別紙、という骨格を持つ。
番号方式 `contract-standard`（条「第1条（見出し）」／項は算用数字・第1項無番号／号「(1)」／細目「ア」）。
常体（「〜とする。」「〜しなければならない。」）。表紙・目次なしが既定。1 段組。

| doctype | 題材 | 目標ページ | 固有の必須要素 |
|---|---|---|---|
| `outsourcing` 業務委託 | システム開発・運用委託 等 | 5–10 | 委託業務の別紙（deliverables 表）、報酬表（fee_schedule）、検収フロー図（flowchart または steps）、再委託・知財・損害賠償の条 |
| `nda` 秘密保持 | 取引検討に伴う NDA | 3–6 | 秘密情報の定義（定義条または definitions 表）、例外列挙（enumeration）、返還・破棄、有効期間のタイムライン（timeline、MAY） |
| `sales` 売買 | 動産・機器の売買 | 4–8 | 目的物の別紙（目録表）、代金・支払方法表、危険負担・所有権移転、瑕疵担保／契約不適合の条 |
| `lease` 賃貸借 | 建物（事務所）賃貸借 | 5–10 | 物件目録（別紙）、賃料・共益費表（fee_schedule）、修繕分担表（mapping：貸主/借主 × 項目）、契約終了時の流れ（steps） |

全 doctype 共通の必須要素：
- `preamble`（前文。当事者の導入＝`{party:key|full}` を含む）
- `parties` ブロック（当事者表示）または前文内の導入（blueprint が選ぶ）
- `signature`（後文＋記名押印欄。日付・双方の名称/住所/代表者・「印」）
- 一般条項（合意管轄・協議・通知）から 2 条以上
- 条項間参照 `{ref:}` 5 箇所以上、別紙参照 1 箇所以上、定義語 `{term:}` 5 語以上

バリエーション軸（variants、seed で選択）：当事者の呼称（甲乙／委託者・受託者 等）、会社形態、
条の本数、別紙の有無と数、数字全角/半角、和暦/西暦、金額表記、反社条項・存続条項の有無、
署名欄の並び（縦並び/横並び）。

style プリセット（初期 2 種）：`ct-a4-1col-mincho`（明朝 10.5pt・罫線なし見出し）、
`ct-a4-1col-gothic`（ゴシック 10pt・下線見出し）。

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
番号方式 `kitei-standard`（章「第1章」／条「第1条（見出し）」／項は算用数字・第1項無番号／号「(1)」、
附則は独立体系）。

| doctype | 題材 | 目標ページ | 固有の必須要素 |
|---|---|---|---|
| `shugyo` 就業規則 | 中小企業の就業規則 | 8–16 | 章立て（総則/採用/勤務/休暇/服務/賃金/退職/表彰懲戒 から 6 章以上）、労働時間・休憩の表、休暇一覧表、懲戒事由の列挙、賃金体系の別表（wage_table）、手続きフロー図 1 点以上、附則（施行日）＋改正履歴表 |
| `kitei` 一般規程 | 文書管理規程・経費精算規程 等 | 4–10 | 総則（目的/適用範囲/用語）、主要手続きの条、承認フロー図（flowchart）、権限表（mapping：事項 × 決裁者）、様式への参照（「様式第1号」＝架空）、附則＋改正履歴 |

バリエーション軸：会社規模・業種（語彙が変わる）、章構成、別表の数、
改正履歴の行数（1〜8 行）、条数、様式参照の有無。

style プリセット（初期 2 種）：`rg-a4-1col-mincho`（規程集風・明朝）、`rg-b5-1col-mincho`（冊子風・B5）。

## 5. insurance（保険約款）— yakkan からの移植

目的と位置づけは `docs/architecture.md` §6（同等性検証）。v1 では `oneday` と `teikan` を移植し、
残り 5 genre は P2 の同等性が安定してから順次移す。blueprint・styles・library・denylist は
yakkan-synth からコピーし、`genre:` → `doctype:` の読み替えだけを行う。
numbering は nonlife/life/teikan を YAML 化する（`docs/schema.md` §7 の golden 対象）。

## 6. 新ファミリー追加の手順（P7 でこの手順書自体を検証する）

1. `docs/reference_structures.md` の手順で実在文書の構造分析を行い、`families/<f>/docs/structures.md` に
   読み取り課題カタログと分析ログを書く（**文章は 1 文も写さない**）。
2. `family.yaml` を書く（doctypes・numbering_schemes・semantic_types・page_limit・tone・lint）。
3. `numbering/<scheme>.yaml` を書き、`tests/unit` にラベル・`{ref:}` 解決の golden を足す。
4. `blueprints/<doctype>.yaml` を書く（骨組み・required_elements・variants・budget）。
5. `styles/` を 1 種作り、`docsynth scaffold` → 最小サンプルを執筆 → `lint/build/render/verify` を通す。
6. **全ページ PNG を目視**（`docsynth review`）。新ファミリー初回は CLAUDE.md §0.4-7 のとおり必須。
7. `families/<f>/docs/style.md` に文体・語彙を書き、denylist を整備してから本執筆に入る。
8. ここまでで hooks.py が必要になった場合は、その理由を `docs/decisions.md` に記録する。

## 7. ファミリー横断の禁止事項

- ファミリーをまたぐ import（`families/contract/` から `families/terms/` を参照）は禁止。
  共有したい語彙・規則が出たらコアへ昇格させる。
- `library/` の文はファミリー内でもコピペ増殖させない（L15 類似度検査の対象）。
- denylist の共通部分（大手企業名等の汎用実在名）はコアの `docsynth/lint/denylist_common.txt` に置き、
  ファミリー側は業界固有名だけを持つ。
