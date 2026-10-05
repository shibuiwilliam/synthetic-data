# docs/m0_survey.md — M0 調査の所見（T0.1〜T0.3）

- 日付: 2026-10-03
- 方法: 本体（`contracts/`）のコードと生成物を読むだけで照合（CLAUDE.md 規則11 遵守）
- 読んだもの: `docs/schema.md`（全文）、`keiyaku/cli.py`（コマンド群）、`keiyaku/models.py`（図の種別）、
  `content/ots-0001/source.json`（条文型の実物・derived 込み）、`content/` 一覧（20 content）、
  `dataset/` 一覧、`HITL_apply_review.md`、`specs/apply_notes.yaml`、`content/*/qa_authored.json`（apply 47 問）

## 1. DESIGN.md §3.1 の前提 7 件の照合

| # | 前提 | 判定 | 根拠と注記 |
|---|---|---|---|
| 1 | 種類と seed から契約書JSONを作る | **一部不成立** | 本体は `scaffold`（骨組み生成）＋ **Claude が執筆** ＋ `build` の工程。seed だけから完成文書を量産する機能は**ない**。既定の契約書は `content/` の **20 件（10 doctype × 2）が全量**。→ §15 の `generate --genre --seeds 1-100` 型は成立せず、**`--base` 型（既存 content を入力に取る）だけが成立**。影響節: §5・§15・§16 |
| 2 | 内容＋計算される索引 | 成立 | `source.json` = 執筆物 + `derived`（labels/refs/term_uses/party_uses/plain_text/tables/figures/formulas/enumerations/toc）。`derived` は `keiyaku build` が付与 |
| 3 | 条・項・号の木構造と安定ID | 成立 | `body: Node[]`、id は `a1`・`a1_p2`・`a4_p3_i1`・表セル `tbl_x__r0c1` の形。`derived.labels[id].citation` が「第1条 2」形の紙面表記 |
| 4 | 表を持てる。図は未確認 | 成立（図もある） | 表は `grid`＋`records` の二重表現。図は **6 種**（flowchart / tree / steps / timeline / annotated_mock / matrix）＋正規化グラフ。算式ブロック（formulas）もある |
| 5 | 数値の持ち方 | **dictionary 型で成立** | `meta.constants`（例 `{"accept_days": "10日", "liability_cap": "300万円"}`）＋本文の `{const:key}`。lint L11 が数値整合を検査 |
| 6 | 当事者・定義語の参照機構 | 成立 | `meta.parties`（key/alias/name）＋ `{party:key}`・`{party:key|name|full|role}`。定義語は `defined_terms`＋`{term:id}`。alias 直書きは L19 が error |
| 7 | 索引の再計算と描画を外から呼べる | 成立 | `uv run keiyaku build <content_dir>`／`uv run keiyaku render <content_dir> --style <sid> --out <root>`。**どちらも任意パスを受ける**（content_dir は doc.json＋parts、out_root も指定可）。Python からは `keiyaku.build.build_content(dir)` |

## 2. DESIGN.md §17 確認事項 1〜9 の結論

| # | 事項 | 結論 |
|---|---|---|
| 1 | 契約書JSONの実物とスキーマ | `docs/schema.md`（＋基底 `../insurance-contracts/docs/schema.md`）と `schema/*.schema.json`。`source.json` 実物で確認済み。schema_version "2.0"、`family: "contract"` 固定＋`doctype` |
| 2 | 種類の一覧と条の構成 | 10 doctype（nda/outsourcing/delegation/consulting/purchase/lease/license/sysdev/contracting/employment）× 各 2 content。**DESIGN の「genre」は本体の「doctype」**。content_id は `ots-0001` 形（短縮形：con/csl/dlg/emp/lea/lic/nda/ots/pur/sys） |
| 3 | 数値の持ち方 | **dictionary**（`meta.constants`＋`{const:}`）。値は「10日」「300万円」「翌月末日」のような**日本語表記の文字列**。数値の往復には `numbers_ja` の読取が必須 |
| 4 | 頭書と別紙 | ある。`head_matter`（lease 系、`{ref:head}`→「頭書」解決）、`appendix`（`kind_label` ごとに「別紙1」「別表1」「様式第1号」採番）。表の semantic_type に `fee_schedule`/`head_matter`/`form_fields`/`allocation` 等の契約書語彙 |
| 5 | 図 | 描画できる。6 種（上記）。図中トークン `{const:}` `{term:}` `{ref:}` `{party:}` は build が解決 |
| 6 | 条項テンプレートの識別子 | **ない**。content は手執筆で、clause テンプレート ID は残らない。→ 付与モードの照合は**見出し＋文型＋`{const:}` 名**で行う（DESIGN §6.1 の `heading`/`text_patterns` 方式。`template_id` 方式は使えない） |
| 7 | 再計算と描画の呼び出し | CLI（`uv run keiyaku build/render/verify/lint`）。親リポジトリのルートで `uv run` 実行。**content_dir・出力先とも任意パス可**なので、コピー→パッチ→build→render の 2 段実行が成立 |
| 8 | 読取評価が ID・定数名を照合に使うか | 使う。`evidence` は単位 ID（`a4_p2` 等）、`elements.jsonl`・`answer.json` は ID ベース。→ 追加ノードの ID は本体の命名規則（`a<n>`・`a<n>_p<m>`・`sch<n>`…）に従い、**既存 ID と衝突させない**。定数名も `meta.constants` の既存 key と衝突禁止（snake_case 日本語なし） |
| 9 | 当事者の呼称と文体 | `meta.parties`＋`{party:}`。文体は常体「…ものとする。」が既定（license/purchase/employment は敬体もあり得る。blueprint の `tone`）。数字は `meta.digit_style`（halfwidth/fullwidth）に従う |

## 3. MH5 の材料の所在（TH5.1 の下見）

- `HITL_apply_review.md`：47 問の検算シート（自動生成。問い・答え・根拠の紙面文字列・AI 検算・読み幅）。
- `specs/apply_notes.yaml`：検算の導出各段と caution の正本。`<cid> → questions → <qa_id> → {derivation, caution}`。
- `content/<cid>/qa_authored.json`：`{id, type: "apply", answer_type, question, answer, evidence[]}`。
  apply は全 content 合計 **47 問**（機械で数えて一致）。
- 答えの形式は文字列（「10日目」「２０２７年９月１４日」「5470万円」「１割」等。全角・単位付きが混在）
  → 突合には `numbers_ja` の読取（日付・金額・割合・日数）が必須。

## 4. 設計への影響（T0.5 で DESIGN.md に反映すべき点）

1. **§15・§5**：`generate --genre X --seeds 1-100` は成立しない。入力は常に既存 content
   （`--base content/<cid>` またはその一覧）。1 つの base から複数 seed で別版を作ることは可能。
2. **§6.1**：バインディングの `match.template_id` は使えない。見出し・文型・定数名での照合に一本化。
3. **§12.1 ほか**：「genre」→「doctype」。content_id 例も実物（`ots-0001`）に合わせる。
4. **数値は日本語表記の文字列**（`meta.constants` の値）。CalcSpec の `surface` と `numbers_ja` の往復が
   数値の往復検査（G4）の実体になる。
5. **出力の置き場所**：親の `dataset/` には書けない（規則11）。本サブプロジェクト配下
   （例 `contracts-calculation/data/`）に出す。※ §17-10 の決定待ち。
6. 単位 ID の実例：節点 `a9_p3`、表セル `tbl_part__r1c2`、前文 `pre_p1`。DESIGN の例（`art12_p1`）を置換。
