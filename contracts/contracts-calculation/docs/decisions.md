# docs/decisions.md — 決定の記録（contracts-calculation）

TASK.md の進捗ログ（現 §5）・DESIGN.md §17・各調査ノートに散在していた決定をここに集約する。
以後、設計に影響する決定はこの表に 1 行足す（経緯の詳細は「出典」の文書にある）。

| 日付 | 決定 | 決め手 | 反映先／出典 |
|---|---|---|---|
| 2026-10-05 | Hugging Face 公開形は `dataset/` を読むだけで別ディレクトリへ**許可リスト方式**で組み立てる（`publish`）。`render.html` 全 102 ファイルにローカルの絶対パスとユーザー名が入るため、除外をアップロード時の指定に頼らない。出題 `inputs/` と正解 `answers/` を構造で分け、`load_dataset()` 用の平索引を `data/*.jsonl` に出す。正解の同梱は `--no-answers` で切替。**ライセンスは未決のまま**（HC-3）組み立てる | ユーザー指示（HF で公開し提供したい）。個人情報の漏洩を構造的に防ぐ（既定は「出さない」） | `export/hf.py`、`cli.py publish`、`docs/hf_publish.md`、`tests/test_hf_publish.py`、DESIGN §15・§15.1、TASK.md TH1〜TH4 |
| 2026-10-05 | 公開準備：`README.md` を新設し、実装とずれていた文書（DESIGN §7 の構成木・§15 のコマンド・実行できないテストコマンド）を**実装ではなく文書側**を直して合わせた。`.gitignore` はサブツリー単体で正しく効くよう自己完結させる。**コミットは行わない**（HC-1 を再確認） | ユーザー指示（公開可能な状態にする）。実装と文書が食い違ったら文書を先に直す原則 | `README.md`、DESIGN §7・§15、`CLAUDE.md`、`PROMPT.md`、`verify/gates.py`、`HITL.md`、`.gitignore`、TASK.md TR9 |
| 2026-10-05 | `dataset/` の全文レビューで5パターンの意味・文言を修正し、生成器0.8.3で100件を全量再生成。challengeのラベル付き難所12件は評価目的のため維持する。親 content の増加から固定回帰を隔離するため、v1の20基準契約を明示的な集合として固定 | ユーザー指示（日本語・内容整合・実在名称の全量レビュー）と境界ケース監査 | `docs/dataset_review.md`、`patterns/`、`base_adapter.py`、`tests/`、`dataset/` |
| 2026-10-04 | `<data>/data-card.md`（データカード）を新設。**実測だけから生成し手で書かない**。仕様は `docs/data_card.md`、`generate`/`bind`/`datasheet` の出口で README と対で更新、鮮度は `datacard check`、測り方は `scripts/verify_data_card.py` で別経路検算。PDF の実測は標準ライブラリ（re＋zlib）で行う | ユーザー指示（親 `dataset/data-card.md` を下敷きに、計算データセットの素性を書く） | `export/datacard.py`、`tests/test_datacard.py`、`docs/data_card.md`、TASK.md TD1〜TD8 |
| 2026-10-04 | 生成前に既知の実在名称との衝突を合成名称へ置換し、データセット全体を回帰検査する | 契約本文は架空名称のみとする。親 content は読取り専用のためコピー後に処理 | `packs/fictional_names.json`、`fictionalize.py`、`test_fictionalize.py` |
| 2026-10-04 | 親 content 改稿後、起算・分母・端数処理が全て明示された遅延損害金8件を include 化。起算が「遅延の日数」のみの2件は除外を維持 | 一義に計算できる条項だけを付与する原則 | `bindings/engine.py`、`tests/test_bindings.py`、`docs/m4_bindings.md` |
| 2026-10-03 | 入力は常に既存 content（`--base` 型）。種類＋seed からの量産（旧 §15 案）は本体に機能が無く不成立 | M0 実物照合 | DESIGN §3.1・§15、`docs/m0_survey.md` |
| 2026-10-03 | 新 content_id は別番号帯 `base + 100×calc_seed`（例 ots-0001→ots-0101）。出力は自前の `data/` 配下（親の `dataset/` に書かない） | ユーザー決定（§17-10） | `generate.py`、DESIGN §17 |
| 2026-10-03 | 祝日は実在ベースの固定版（2026〜2033、`packs/calendar/holidays_jp.json`。生成時に再取得しない） | ユーザー決定（§17-11） | `scripts/make_calendar.py` |
| 2026-10-03 | 不明値（unknown）ケースを評価に含める（None=不明の意味論を採点対象にする） | ユーザー決定（§17-12) | `testgen/cases.py`、evalkit |
| 2026-10-03 | v1 規模は 20 content × 3〜6 ルール | ユーザー決定（§17-13） | `config.py` PROFILES |
| 2026-10-03 | packs は YAML でなく JSON で持つ（実行時依存を標準ライブラリに保つ。規則12 と両立） | 実装時判断 | `packs/`、DESIGN §7 注記 |
| 2026-10-03 | WeasyPrint 70.0 の既知不具合で破綻する文書は別 style へ**決定的に**フォールバックし、manifest に注記を残す | 実測（4/20 文書で破綻） | `base_adapter.py`、`docs/m2_review.md` |
| 2026-10-03 | 演算 `set_day` を閉じた演算語彙（§12.2）に追加（P-OP-ADD の手順で interp・validate・codegen・schema・DESIGN を同時改定） | emp-0002:qa_auth_010 の形式化に必要 | `spec/`・`codegen/`、`docs/h5_handoff.md` 補足 |
| 2026-10-04 | H5：読み幅あり 15 問の採用した読みをすべて承認（応当日基準・「前まで」は当日を含む・「以内」は翌日起算 等） | ユーザー決定 | `docs/h5_handoff.md`、`bindings/engine.py`（更新通知を include 化） |
| 2026-10-04 | 親の遅延損害金条項 10 件は**記録つき除外を維持**（日割の分母・端数処理の明示性欠落。親の執筆改善の材料として記録を残す） | ユーザー決定 | `docs/m4_bindings.md`、manifest・lint-base |
| 2026-10-04 | G13（外部読取システムでの実測）は見送り。評価対象が現れたら eval CLI で測る | ユーザー決定 | TASK.md |
| 2026-10-04 | bool 出力または分岐（if/case/coalesce）を含むルールは **None 伝播モード**で codegen する（入力ガード方式は三値の意味論と食い違う） | オラクル検査の不一致（96/100） | `codegen/python.py`、`tests/test_codegen.py` |
| 2026-10-04 | patch 操作 `add_term`（定義語の追加）は利用パターンが現存しないため**必要になるまで未実装** | 実装時判断 | TASK.md、DESIGN §15 |
| 2026-10-04 | 文書群の整理：`notes/`・`h5/HANDOFF.md` を `docs/` に集約（`h5/` は検算コードと生成物のみ）。決定の記録は本ファイルに一元化 | ユーザー指示 | `docs/README.md` |
| 2026-10-04 | `h5/` を解体：検算コードを `src/contracts_calculation/h5/`（specs.py・verify.py）へ、生成物を `docs/h5_report.md`・`docs/h5_inventory.json` へ移設（sys.path ハックを廃止し通常の import に） | ユーザー指示 | `tests/test_h5.py`、`docs/README.md` |
| 2026-10-04 | タスク管理の再編：TASK.md を残作業管理（0.2 版）に書き直し、完了タスク詳細は `docs/milestones_archive.md` へ。人間判断の台帳として `HITL.md` を新設（依頼中：HC-1 コミット・HC-2 データセット構成／親側：HP-1） | ユーザー指示 | TASK.md、HITL.md |
| 2026-10-04 | コミットはしない。Git の操作は全て人間が行う（AI は `.gitignore` の整備まで） | ユーザー決定（HITL HC-1） | `.gitignore`、TASK.md TR3 |
| 2026-10-04 | データセット v1 ＝ 4 プロファイル × 20 base × calc_seed 1（80 文書）＋ `data_bind/` 20 件。配置は `data/<profile>/<cid>/`（プロファイル間で content_id が同一のためディレクトリで分離＝仮決め） | ユーザー決定（HITL HC-2）＋実装時判断 | `data/`、TASK.md TR2 |
| 2026-10-04 | `dataset/` 50 件の構成＝standard×seed1×20＋hard×seed2×20＋challenge×seed3×各 doctype 1 本（content_id は seed 帯で一意のためフラット配置）。**仮決め**（ユーザー指示は「50 件」のみ） | 実装時判断 | `dataset/`、TASK.md ログ |
| 2026-10-04 | K06 の case_hints にクランプ帯内側の割り切れない売上高を必ず 1 件入れる（丸め変異の検出を乱数に依存させない）。生成器 0.8.1 | seed2 で G7 不合格（実バグ） | `patterns/k06_rate_on_base.py` |
| 2026-10-04 | `dataset/` を 100 件に拡張。構成＝standard29／hard29／challenge20／basic22（seed1〜6、content_id は seed 帯で一意）。**仮決め**（指示は「合計 100 件」のみ）。sys base 2 件は親の改稿中（lint 不通過）のため seed3 以降は安定 base で代替 | 実装時判断 | `dataset/`、TASK.md ログ |
