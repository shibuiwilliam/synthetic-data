# lint_rules.md — 整合性ルール（`yakkan lint`）の実装詳細

> CLAUDE.md §8 の一覧表に対応する実装マップと補足。ルールの重大度・一言説明は CLAUDE.md §8 を見る。
> 本ファイルは「どのファイルのどの関数が検査しているか」「実装上の注意点」を持つ。
> 新しい lint ルールを足すときは `yakkan/lint/base.py` の `@rule("L##", "説明")` デコレータで登録し、
> この表と CLAUDE.md §8 の両方を更新する。

## 実装ファイル対応表

| # | 実装ファイル | 備考 |
|---|---|---|
| L00 | `yakkan/lint/rules.py`（スキーマ検証） | pydantic のバリデーションエラーをそのまま Finding に変換。実行順の先頭固定（`runner.py` の `only=["L00"]` は最速のスキーマだけ流す用途） |
| L01 | `yakkan/lint/rules.py` | `{ref:}`／`anchor`／`evidence` の参照先 id が文書内の `all_ids` に存在するかを走査。`margin_note` は anchor 必須 |
| L02 | `yakkan/lint/rules.py` | `{fn:n}` と `footnotes.n` の双方向対応。脚注番号の重複、未参照脚注も検出 |
| L03 | `yakkan/lint/rules.py` | 番号ラベル直書きの正規表現検査。`{ref:}` 解決後の文字列は対象外 |
| L04 | `yakkan/lint/structure.py` | `blueprints/<genre>.yaml` の `required_elements` を読み、種類と最小件数を集計して不足を報告 |
| L05 | `yakkan/lint/structure.py` | 表の結合展開後の列数一致、`header_rows/cols` の範囲、`records` の値が `grid` に出現するか |
| L06 | `yakkan/lint/rules.py` | 図：diagram 種別ごとに分岐（`_check_diagram`）。edges の端点存在、格子座標重複、最小複雑度、alt/facts 非空、バッジ番号の重複・凡例対応 |
| L07 | `yakkan/lint/rules.py` | fontTools で `assets/fonts/` の cmap を読み、使用文字が被覆されているか（`quick=False`：時間がかかるので `--quick` では skip） |
| L08 | `yakkan/lint/rules.py` | `denylist.txt` の語句、`example.*` 以外のドメイン、`0120-000-000` 形式でない電話番号を検出 |
| L09 | `yakkan/lint/structure.py` | 推定ページ数（`chars_per_page_estimate`。実コーパスから較正済み、`docs/gotchas.md`）と blueprint の `budget.chars_min/max` |
| L10 | `yakkan/lint/quality.py` | genre の敬体/常体を文末形の統計で判定。`digit_style`（全角/半角）の混在を検出 |
| L11 | `yakkan/lint/quality.py` | `meta.constants` に宣言された値と `{const:key}` 参照の食い違いを検出 |
| L12 | `yakkan/lint/quality.py` | `defined_terms` に無い `{term:}`、定義されたが未使用の語 |
| L13 | `yakkan/lint/rules.py` | 奥付 disclaimer の有無、`meta.issuer` 等の必須項目 |
| L14 | `yakkan/qa/validate.py` | QA 個別の型検証（`answer_type` と `type` の対応、evidence の id・page_hint の整合、extract 系の answer が evidence テキストに含まれるか） |
| L15 | `yakkan/lint/quality.py` | `quick=False`。既存 content との文単位重複率を計算（`--similarity` 指定時のみ実行） |
| L16 | `yakkan/lint/qa_authored.py` | 執筆 QA（`docs/authoring_checklist.md` 由来）の件数・観点配分・evidence 有無 |
| L17 | `yakkan/lint/table_headers.py` | `header_cols`（`role: stub` の列）が行見出しを覆っているかを検査 |

## 実行順・実行モードの注意
- `runner.py` がルールを集約する。`--quick` は `quick=False` を付けたルール（L07・L15）を飛ばす。フック（`.claude/settings.json`）から `*.json` 保存後に自動実行されるのはこの quick 版。
- L00（スキーマ検証）は他ルールの前提。壊れた JSON に対して他ルールを走らせると誤検出するため、`runner.py` は L00 失敗時に後続をスキップする経路を持つ（`only=["L00"]` 相当）。
- 新ルールは `Finding("L##", severity, message, element_id=..., path=...)` の形で yield する。`element_id` は id 一意なノード/ブロック、`path` はファイル内の位置（`meta.xxx` 等）を指す。
