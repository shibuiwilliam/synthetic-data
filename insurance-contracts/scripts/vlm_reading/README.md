# VLM が読んだ予測の実例（docs/remaining_issues.md W1）

`jyusetsu-0001--jys-a4-1col-gothic.json` は、**`dataset/jyusetsu-0001--jys-a4-1col-gothic/pages/*.png`
を画像として読んで作った予測**である。作ったのは、この開発をしている Claude 自身（VLM）。
正解ファイル（`source.json` / `layout.json` / `answer.json` / `qa.json`）は一切開いていない。
外部 API は使っていない（CLAUDE.md §1.3）。

目的は読み取りモデルの評価ではなく、**ハーネスの契約検査**——
「内部 id を持たない読み手が、docs/evaluation.md の形で予測を出せるか」を確かめること。

    uv run yakkan eval dataset/jyusetsu-0001--jys-a4-1col-gothic \
      --pred scripts/vlm_reading/jyusetsu-0001--jys-a4-1col-gothic.json

## 測った結果（2026-09-23）

| 指標 | 値 |
|---|---|
| 本文 CER | **0.0004**（8 ページ中 7 ページが 0.0000、最悪 0.0032） |
| 見出し F1 | 0.7945（precision 1.0 / recall 0.659） |
| 見出しの page 正解率 | 1.0 |
| 見出しの citation 正解率 | 1.0 |
| 見出しの kind 正解率 | 1.0 |
| 構造位置 coverage / citation 正解率 | 0.808 / 1.0 |
| 表 TEDS | 1.0 |
| 表セル F1 | 0.0（`cells` を出していない） |
| 図 ノード / エッジ / 経路 F1 | 0.5 / 0.429 / 1.0 |
| 列挙の順番一致 | 1.0 |
| 読み順 τ | 1.0 |
| bbox IoU | 0.0（bbox を出していない） |

## この 1 回で見つかった欠陥

1. **W6：目次のリーダー罫**が PDF のテキスト層に「.」として入り、
   2 ページ目の CER が 0.775 になっていた。**正解データ側の欠陥**で、
   点線罫に替えて直した（CER 0.0973 → 0.0004）。
2. **W5：予測に使う語彙が未定義**。`kind` を `subsection` と出して種別正解率 0.0。
   `docs/evaluation.md` §3 に語彙を書き、同じ予測を出し直したら 1.0 になった。
   `yakkan eval --pred` は形の違いを警告として出すようにした。

**この JSON は当時の版面に対する読み取りである。** データセットを作り直すと本文が変わり、
点が下がることがある。テストからは参照していない（版面の変更で落ちるのは正しくないため）。
