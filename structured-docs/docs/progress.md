# progress.md — 進捗と次の一手

> セッション終了前に必ず更新する（CLAUDE.md §0.2-4）。
> 形式：フェーズごとの状態＋「次の 3 タスク」。新しい記録を上に足す。

## 現在地

- フェーズ：**P0（移植）未着手**。仕様（CLAUDE.md・docs/）のみ執筆済み。コード・`families/`・
  `content/` はまだ無い。
- 2026-10-05 に**姉妹プロジェクトが 2 本になったこと**へ仕様を追随させた。
  `../contracts/`（keiyaku-synth）がデータセット v1（10 doctype・100 文書）を完成させ、
  本プロジェクトの P1（コア汎用化）と P3（contract）の大半を契約書ドメインで先に済ませている。
  `../insurance-contracts/`（yakkan-synth）も v7（114 文書）＋検索クエリ 10 種＋データカード＋
  配布（HF / CC BY 4.0）まで到達した。
- **人間の判断待ちが 1 件ある**：コード基盤を keiyaku / yakkan のどちらから取るか（`HITL_TODO.md` D1。
  既定は keiyaku ベース。`../contracts/HITL_TODO.md` H10「docsynth 切り出し」と連動）。
  **P0 の着手自体は既定で進めてよいが、P1 に入る前に回答を得る。**
- フェーズ構成は P0〜P9（`docs/plan.md` が詳細 WBS）。lint は L00–L26 を継承（新設は L27 以降）。

## 次の 3 タスク（P0）

1. `HITL_TODO.md` D1 の回答を確認する（未回答なら既定＝keiyaku ベースで 2・3 を進める）。
2. `uv init` でプロジェクト初期化（Python 3.12・ruff・pytest・typer・pydantic v2・WeasyPrint 70.0 固定・
   pdfplumber・pypdfium2・fontTools・Jinja2・PyYAML）。Makefile（setup/check/doctor/smoke）を移植し、
   **`check` に manifest 鮮度とデータカード鮮度を入れる**。
3. `../contracts/keiyaku/` → `docsynth/` へコピー＆リネーム（挙動不変）。**評価基盤・`datacard.py`・
   tests（532 件）・scripts（24 本）・`.claude/`・`assets/fonts/`（.ttf 版＋SOURCES.md）を含む**。
   **検索まわり（クエリ 10 種・自己検査 V-S1〜V-S9・検索指標 8 種）は yakkan から取る**
   ——keiyaku にはまだ無い（`docs/architecture.md` §5）。`make check` と smoke を通し、
   smoke のテキスト層が供給元と一致することを確認する。
4. （続けて）棚卸し：モジュールごとのドメイン直書き箇所を `docs/architecture.md` §5 の表に
   実測で記入し、P1 の作業リストを確定する。

## フェーズ状態（`docs/plan.md` の WBS に対応）

| フェーズ | 状態 | メモ |
|---|---|---|
| P0 移植 | 未着手 | keiyaku ベース（既定）。評価基盤・datacard・.ttf フォントを含めて丸ごと。検索は yakkan から |
| P1 コア汎用化 | 未着手 | 固定値 `contract` をレジストリに開く。numbering YAML **8 方式**の golden が山。`iroha` counter の実装 |
| P2 同等性 | 未着手 | insurance（oneday・teikan）＋ **contract（nda・lease・employment）** の 2 ドメインで守る |
| P3 contract 完成 | 未着手 | keiyaku の 10 doctype・50 content を移すだけ（新規執筆なし） |
| P4 terms | 未着手 | 3 階層入れ子リストの probe が先 |
| P5 regulations | 未着手 | |
| P6 statute | 未着手 | **姉妹に先例が無い唯一のファミリー。** probe 2 件（条見出し 2 行・漢数字幅）を先に |
| P7 データセット v1 | 未着手 | oracle 全満点＋検索の V-S 通過＋データカードが DoD |
| P8 検証・硬化 | 未着手 | `docs/validation_plan.md` の V-A〜V-F。盲検＋HITL |
| P9 拡張・手順書検証・配布 | 未着手 | 配布は `HITL_TODO.md` D2・D3 の決定後 |

## 記録

### 2026-10-05
- `../contracts/`（keiyaku-synth）と `../insurance-contracts/`（yakkan-synth）の現況を読み直し、
  **仕様を姉妹 2 本の到達点へ追随させた**（`docs/decisions.md` 2026-10-05 に 18 件の決定）。
- 取り込んだもの：lint **L19–L26**（当事者整合・骨格・逐条解説・表図の配置・列挙の入れ子・
  置き去りの part・Markdown の名残・位置で指す言い方）／verify **V01–V11 ＋ V-P1〜V-P5**（V11＝
  結合セルのページまたぎ）／`head_matter`・`commentary`・`{party:|role}`・契約書の semantic_type 6 種／
  番号方式 3 種の宣言（条を持たない `contract-form`・漢数字 `contract-kanji`）／
  **検索クエリ 10 種・検索指標 8 種・自己検査 V-S1〜V-S9・弁別力の申告**／
  **データカード**（`dataset/data-card.md`）／`apply` QA の確定手順（機械検算 → 読み幅 → 承認）。
- contract ファミリーを **4 doctype → 10 doctype・骨格 5 類型**に拡張（keiyaku の実績をそのまま family 化）。
- P0 の基盤を **keiyaku ベース**に切り替える案を既定として仕様に反映し、
  **`HITL_TODO.md` を新設**して D1（基盤の選択）・D2（配布）・D3（コードのライセンス）・
  D4（外部送信）を起票した。
- 新設文書：`docs/lint_rules.md`・`docs/data_card.md`・`docs/authoring_checklist.md`・
  `docs/distribution.md`・`HITL_TODO.md`。
- 更新文書：`CLAUDE.md`（lint 表・ファミリー表・フェーズ・決定事項）・`README.md`・
  `docs/architecture.md`（移植方針 2 案・棚卸し・同等性 2 ドメイン）・`docs/schema.md` §1.2/§5/§7/§9/§11・
  `docs/families.md` §2/§5/§7/§9・`docs/rendering.md` §2/§4/§6/§7・`docs/evaluation.md`（全面）・
  `docs/validation_plan.md`（全面）・`docs/plan.md`（全面）・`docs/style_guide.md`・
  `docs/reference_structures.md`・`docs/repo_layout.md`・`docs/gotchas.md`。

### 2026-09-26
- yakkan-synth（`../insurance-contracts/`）の全ドキュメント・構成を読み直し、発足（2026-09-22）以降の
  進化——評価ハーネス（eval 13 指標・検索 7 指標）、elements.jsonl・検索評価セット、予測語彙の文書化、
  lint L16〜L18、規則ベース／VLM／盲検の 3 段検証、目次リーダー罫と CFF フォントの実害と修正——を
  本プロジェクトの仕様へ反映した。
- `docs/evaluation.md`（評価設計の継承）、`docs/validation_plan.md`（検証・硬化計画）、
  `docs/plan.md`（WBS）を新設。schema / families / architecture / rendering / style_guide /
  reference_structures / repo_layout を更新。
- `statute`（法令）ファミリーを追加（law / jorei）。counter kanji/iroha・promulgation・
  relation_refs・目次の条範囲を設計に追加。
- 決定 9 件を `docs/decisions.md` に記録（評価基盤の P0 移植・lint 改番 L19・.ttf フォント・
  リーダー罫規約・フェーズ再編ほか）。

### 2026-09-22
- プロジェクト発足。CLAUDE.md と docs/ 一式（architecture / schema / families / rendering /
  style_guide / reference_structures / repo_layout / decisions / progress / gotchas）を執筆。
- 初期決定 10 件を `docs/decisions.md` に記録（コピー方式・スキーマ互換・v1 ファミリー4種ほか）。
