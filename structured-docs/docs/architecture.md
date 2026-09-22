# architecture.md — コア／ファミリーの分離と yakkan-synth からの移植方針

> コアとファミリーの境界、および `../insurance-contracts/`（yakkan-synth）からのコード移植を
> 触る作業では、**着手前に必ず本ファイルを読む**。
> 境界の変更（コアに新しい概念を足す・ファミリーへ責務を移す）は `docs/decisions.md` に記録してから行う。

## 1. 全体像

```
┌──────────────────────── docsynth（コア：ドメイン非依存） ────────────────────────┐
│ models（Node/Block/Table/Figure/RichText/Layout/Answer/QA）                       │
│ richtext（トークンのパース・解決）    numbering（YAML 宣言の解釈＋フック呼出）      │
│ scaffold / compose / build（派生値）  lint（L00–L16 ＋ family lint の実行器）      │
│ render（Jinja2→HTML→WeasyPrint）     layout（bbox 抽出）  verify  qa  eval        │
│ families（レジストリ：family.yaml の読込・検証・フックのロード）  cli              │
└──────────────────────────────────────────────────────────────────────────────────┘
              ↑ 宣言（YAML）とフック（Python）だけで接続。コアはファミリー名を知らない
┌─ families/contract ─┐ ┌─ families/terms ─┐ ┌─ families/regulations ─┐ ┌─ families/insurance ─┐
│ family.yaml          │ │ …                │ │ …                      │ │ yakkan からの移植     │
│ numbering/*.yaml     │ │                  │ │                        │ │ （同等性検証を兼ねる） │
│ blueprints/*.yaml    │ │                  │ │                        │ │                      │
│ styles/*.yaml + css  │ │                  │ │                        │ │                      │
│ library/  denylist   │ │                  │ │                        │ │                      │
│ docs/  hooks.py(MAY) │ │                  │ │                        │ │                      │
└──────────────────────┘ └──────────────────┘ └────────────────────────┘ └──────────────────────┘
```

## 2. 境界の規則

コアに置いてよいもの／いけないものの判定基準。迷ったら「**新しいファミリーを追加するとき、
このコードを書き換える必要があるか？**」を問う。書き換えが必要ならコアに置いてはいけない。

| 責務 | 置き場所 | 例 |
|---|---|---|
| 文書の機構（木構造・表・図・参照・脚注） | コア | `Node`, `Table.grid`, `{ref:}` の解決アルゴリズム |
| 番号方式の**解釈器** | コア | 「counter 書式＋接頭辞＋全角化」を YAML から組み立てる |
| 番号方式の**定義** | ファミリー | 「条は『第Ｎ条』、項は 2 から表示」＝ `numbering/*.yaml` |
| 意味種別の**語彙** | 2層 | コア共通（definitions/enumeration/…）＋ファミリー登録（fee_schedule 等） |
| 必須要素・分量・文体 | ファミリー | `blueprints/<doctype>.yaml` |
| 架空化の検出語 | ファミリー | `denylist.txt`（実在保険会社／実在Webサービス…） |
| lint の**実行器** | コア | ルールの走査・報告の仕組み |
| lint の**追加規則** | ファミリー | family.yaml の `lint:` 宣言、複雑なものは hooks.py |
| CSS の基礎（ページ・段組・表・見出しの機構） | コア | `docsynth/render/templates/base/` |
| 見た目のプリセット | ファミリー | `styles/<style_id>.yaml` ＋ css |

**フック（`families/<f>/hooks.py`）は逃げ道であり、常設の置き場ではない。**
フックに書いた処理が 2 ファミリー以上で同型になったら、宣言（YAML スキーマの拡張）としてコアに吸収し、
`docs/decisions.md` に記録する。

## 3. family.yaml の形（P1 で確定させるたたき台）

```yaml
family: contract
display_name: 契約書
doctypes: [outsourcing, nda, sales, lease]        # blueprints/<doctype>.yaml が存在すること
numbering_schemes: [contract-standard]            # numbering/<scheme>.yaml
default_page_limit: 10
tone: dearu                                       # dearu（常体）| desumasu（敬体）。lint L10 が使う
semantic_types:                                   # 表のファミリー登録語彙（コア共通語彙に追加）
  - fee_schedule        # 料金・報酬表
  - deliverables        # 成果物・仕様一覧
lint:                                             # 宣言的な追加 lint（FLxx）
  - id: FL01
    rule: require_block                           # コアが提供する宣言ルールの種類
    block: parties
    severity: error
    message: 契約書には当事者表示（parties ブロック）が必須
hooks: hooks.py                                   # MAY。宣言で書けない lint・番号例外のみ
```

## 4. yakkan-synth からの移植方針（P0）

- **コピーして改名**する（`yakkan/` → `docsynth/`、CLI 名 `yakkan` → `docsynth`）。git submodule や
  ライブラリ依存にはしない。理由：yakkan-synth は完成品として凍結し、本プロジェクトで自由に
  リファクタリングするため（`docs/decisions.md` 2026-09-22）。
- P0 では**リネーム以外の挙動変更をしない**。改名後に yakkan-synth の smoke と同一出力になることを確認してから
  P1 の汎用化に入る。「移植」と「汎用化」のコミットを混ぜない。
- 移植時の棚卸し：モジュールごとに「そのまま使える／汎用化が必要（ドメイン知識が直書き）／捨てる」を
  本ファイル §5 の表に記録する。ドメイン知識の直書き箇所（genre enum、numbering の 3 方式、
  semantic_type enum、denylist パス、blueprint 必須要素の検証）が P1 の作業リストになる。
- テスト・`.claude/`（commands/agents/rules/hooks）・Makefile・フォントも同時に移植する。
- assets/fonts は同一物を同梱する（ライセンスは OFL/IPA。`assets/fonts/SOURCES.md` を必ず一緒に持ってくる）。

## 5. 棚卸し表（P0 で埋める）

| yakkan モジュール | 判定（そのまま／要汎用化／捨てる） | ドメイン直書き箇所 | 対応フェーズ |
|---|---|---|---|
| models.py | （P0 で記入） | genre enum・Node.kind・semantic_type | P1 |
| numbering.py | | nonlife/life/teikan の 3 方式 | P1 |
| richtext.py | | （おそらく無し） | — |
| lint/ | | denylist パス・L04 の blueprint 解釈 | P1 |
| render/ | | テンプレートの前付け・特約の描画 | P1–P2 |
| layout/ verify/ | | （おそらく無し） | — |
| qa/ eval/ | | 自動 QA の質問文言 | P1 |
| scaffold.py compose.py blueprints.py | | blueprint スキーマ | P1 |

## 6. insurance ファミリーの位置づけ

- 目的は 2 つ：(1) 汎用化のリグレッション検出（同等性 golden、CLAUDE.md §12 P2）、
  (2) 「既存ドメインをファミリーとして表現できるか」の実証。
- yakkan の `content/`（執筆成果）はコピーせず、`../insurance-contracts/content/` を読み取り専用の
  入力として参照する（テストからの相対パス参照。CI では存在チェックでスキップ可にする）。
- 同等性の許容差：id・テキスト・ラベル・grid・records は完全一致。bbox は 0.5pt。
  一致させられない差分が出たら「新コアのバグ」として扱うのが既定。仕様として差分を受け入れる場合は
  `docs/decisions.md` に記録する。
