# decisions.md — 設計変更履歴

> フェーズをまたぐ設計変更・仮決め・probe の結論はここに追記する（CLAUDE.md §0.2-3）。
> 形式：日付／変更（決定）／理由／影響／状態（確定・仮決め）。新しいものを上に足す。

## 2026-09-22 プロジェクト発足時の初期決定

| 日付 | 決定 | 理由 | 影響 | 状態 |
|---|---|---|---|---|
| 2026-09-22 | プロジェクト名 `structured-docs`、パッケージ・CLI 名 `docsynth` | yakkan（約款）はドメイン名なので汎用側では使わない | 全体 | 確定 |
| 2026-09-22 | yakkan のコードは**コピーして改名**し、本リポジトリで発展させる。`insurance-contracts/` は凍結参照 | submodule/ライブラリ依存にすると、汎用化リファクタリングのたびに凍結側へ変更が波及する。二重メンテを避け、同等性テストで整合を守る方が安い | P0 の作業内容、`docs/architecture.md` §4 | 仮決め（P2 完了時に再評価） |
| 2026-09-22 | 正解スキーマは yakkan 互換＋差分（`genre`→`family`+`doctype`、`{party:}`、kind/Block 追加、schema_version 2.0） | 読み取り側が両データセットを同じローダで扱えるようにする | `docs/schema.md` | 仮決め |
| 2026-09-22 | renderer は WeasyPrint 70.0 固定。probe 実測 22 項目（yakkan-synth `docs/decisions.md` 付録）を再実測せず継承 | 同一版・同一機構なら結果は変わらない。再検証はコストのみ | `docs/rendering.md` | 確定（版を上げるときに要再probe） |
| 2026-09-22 | 番号方式は宣言的 YAML＋family フックの2段構え | ファミリー追加のたびにコアの numbering.py を書き換えないため。yakkan の3方式が YAML で表現できることを P1 golden で確認する | `docs/schema.md` §7 | 仮決め |
| 2026-09-22 | v1 ファミリーは contract / terms / regulations / insurance（移植）の4つ。insurance は同等性検証を兼ねる | 「契約書・利用規約・法的文書」という要望を、番号方式・当事者・文体が互いに異なる3ドメインで最小カバーし、汎用化のリグレッションは insurance で守る | CLAUDE.md §4、`docs/families.md` | 確定 |
| 2026-09-22 | ページ上限はファミリー既定（contract 10 / terms 10 / regulations 16 / insurance 20）、blueprint で上書き可 | 契約書に 20 ページ上限は緩すぎ、実物の分布に合わせる | lint L09、verify | 仮決め |
| 2026-09-22 | 法令・裁判所は名称のみ引用、法令の条番号は書かない（yakkan 踏襲） | 誤った条番号を生成するリスクと検証コストを避ける。契約書で著しく不自然になったら doctype 単位で再検討 | `docs/style_guide.md` §2 | 仮決め |
| 2026-09-22 | 印影・手書き署名は描画しない。「印」の文字＋丸枠のみ | 読み取り検証の焦点はテキスト・構造・表・図であり、画像要素は決定論と正解表現を複雑にする | `docs/rendering.md` §3.2 | 仮決め |
| 2026-09-22 | 縦書き・ルビ・スキャン劣化画像は v1 対象外（yakkan 踏襲） | yakkan-synth と同じ判断。需要が出たら拡張フェーズで | CLAUDE.md §1.4 | 確定 |
| 2026-09-22 | v1 規模：4ファミリー・10 doctype × 2–3 content × 1–2 style ≈ 40–60 文書 | yakkan v1（約30文書）と同程度の密度をファミリー横断で | specs/、P6 | 仮決め |

## 未決事項（既定値で進める前提。決まったら上の表へ）

- `terms` の HTML 的装飾（リンク下線・アンカー風）をどこまで再現するか → 既定：再現しない（印刷風のみ）。
- `regulations` の別表（賃金表）の実額をどう作るか → 既定：`meta.constants` で等級×号俸の基礎値を持ち矛盾なく展開。
- insurance の残り 5 genre をいつ移植するか → 既定：P6 のバッチ設計時に判断。
