"""配布パッケージの組み立て（S10-6・`HITL.md` H4 (c)）。

`HITL.md` H4 で「**正解も含めて配る**」と決まった（将来 GitHub と Hugging Face）。
`export_public()`（軸 A）は「採点のときに評価対象システムへ渡すもの」を分ける仕掛けで、
こちらは「**データセットとして外部に置くもの**」を組む。2 つは別の軸である
（`DESIGN.md` §10.3）。混同すると、評価の最中に正解を渡すことになる。

**このモジュールは配布物を作るだけで、配布はしない。** push とアップロードは人が行う
（`HITL.md` H4、親プロジェクトの `../HITL_TODO.md` H1〜H3 が先）。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .layout import file_hashes, sha256, write_json

#: 配布に含めない。生成の中間物で、受け取る側には意味がない
EXCLUDE = ("render.html",)


def build(
    dataset_dir: Path,
    out_dir: Path,
    *,
    version: str,
    generator_version: str,
) -> dict:
    """`dataset_dir` の全文書を、正解つきの配布パッケージとして `out_dir` に組む。"""
    dataset_dir, out_dir = Path(dataset_dir), Path(out_dir)
    docs = sorted(p.parent.parent for p in dataset_dir.glob("*/calc/manifest.json"))
    if not docs:
        raise FileNotFoundError(f"{dataset_dir} に文書が無い（calc/manifest.json が見つからない）")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "documents").mkdir(parents=True)

    entries: list[dict] = []
    for doc in docs:
        dest = out_dir / "documents" / doc.name
        shutil.copytree(doc, dest, ignore=shutil.ignore_patterns(*EXCLUDE))
        man = json.loads((doc / "calc" / "manifest.json").read_text(encoding="utf-8"))
        entries.append(
            {
                "doc_id": doc.name,
                "genre": man.get("genre") or doc.name.split("-")[0],
                "profile": man.get("profile"),
                "seed": man.get("seed"),
                "rules": man["counts"]["rules"],
                "cases": man["counts"]["cases"],
                "cases_by_kind": man["counts"]["cases_by_kind"],
                "patterns": sorted(man["plan"]["patterns"]),
                "renders": man.get("renders") or [],
                "pages": man["pages"],
            }
        )

    index = {
        "name": "yakkan-calc",
        "version": version,
        "generator_version": generator_version,
        "documents": entries,
        "totals": _totals(entries),
        "contains_answers": True,
        "files": file_hashes(out_dir / "documents", skip=()),
    }
    write_json(out_dir / "index.json", index)
    (out_dir / "README.md").write_text(_readme(index), encoding="utf-8")
    (out_dir / "DATASHEET.md").write_text(_datasheet(index), encoding="utf-8")
    (out_dir / "LICENSE").write_text(_license(), encoding="utf-8")
    index["checksum"] = sha256(out_dir / "index.json")
    return index


def _totals(entries: list[dict]) -> dict:
    kinds: dict[str, int] = {}
    for e in entries:
        for k, v in e["cases_by_kind"].items():
            kinds[k] = kinds.get(k, 0) + v
    return {
        "documents": len(entries),
        "genres": len({e["genre"] for e in entries}),
        "rules": sum(e["rules"] for e in entries),
        "cases": sum(e["cases"] for e in entries),
        "cases_by_kind": dict(sorted(kinds.items())),
        "layouts": sum(len(e["renders"]) for e in entries),
        "styles": sorted({r["style"] for e in entries for r in e["renders"]}),
    }


def _readme(index: dict) -> str:
    t = index["totals"]
    return f"""# yakkan-calc {index["version"]}

日本語の保険約款（**完全に架空**）から、計算・判定の規定を読んで実装する課題のデータセット。

- 文書 **{t["documents"]}**（{t["genres"]} 種目）／ルール **{t["rules"]}**／テストケース **{t["cases"]}**
- 描画結果（レイアウト）**{t["layouts"]}**（{len(t["styles"])} スタイル。同じ内容を別の体裁で描いたもの）
- 生成器の版 `{index["generator_version"]}`

## ⚠ 先に読んでください：正解が入っています

このパッケージには**正解（計算仕様・正解プログラム・正解表・全テストケース）が入っています**。

- **学習データに使わないでください。** 使った時点で、このデータセットでそのモデルを評価できなくなります。
- **採点するときは、評価対象に渡すものを絞ってください。** `icc export` が機械的に分けます
  （渡すのは `policy.json`・PDF・`calc/tasks.jsonl`・`calc/examples.jsonl` だけ）。
- 汚染が疑われるときは**作り直せます**（下の「作り直し方」）。

## 中身

```
documents/<doc_id>/
├── policy.json                     # 約款の内容・構造・意味（読み取りの対象）
├── <doc_id>--<style>/              # レイアウトごとの描画結果
│   ├── doc.pdf
│   ├── layout.json                 # bbox・読み順
│   └── source.json
└── calc/
    ├── tasks.jsonl                 # 出題（ヒント H0）。H1・H2 は根拠つき
    ├── examples.jsonl              # 約款に載っている設例
    ├── spec.json                   # ★正解：計算仕様（唯一の正）
    ├── answer_key.json             # ★正解：根拠単位・パターン・難易度
    ├── programs/                   # ★正解：参照実装
    ├── cases.jsonl                 # ★正解：全テストケース
    ├── tests/                      # ★正解：pytest
    ├── patch.json                  # 既定の約款への追加操作
    └── manifest.json               # 版・seed・ハッシュ・検証結果
```

★ の付いたものが正解である。

## 使い方

```bash
# 1. 出題を読む
cat documents/<doc_id>/calc/tasks.jsonl
# 2. 実装して提出する
# 3. 採点する（正解プログラムと同じ入力で突き合わせる）
icc eval --submission your_impl.py --data documents/<doc_id>
```

## 作り直し方

このデータセットは**決定的に生成されます**。同じ既定の約款・同じ seed・同じ生成器の版なら、
同じ内容が出ます。各文書の `calc/manifest.json` に `seed` と `profile` が入っています。

```bash
icc generate --base <既定の約款> --out out --seed <seed> --profile <profile> --multi-style
```

## 架空であること

会社名・商品名・連絡先・様式番号・人物名はすべて架空です。実在の保険会社・商品・約款とは
関係がありません。URL は `example.jp` など、電話番号はゼロ埋めのみを使っています。
法令は名称だけを引用し、条番号は書いていません。

## ライセンス

`LICENSE` を見てください。
"""


def _datasheet(index: dict) -> str:
    t = index["totals"]
    kinds = "・".join(f"{k} {v}" for k, v in t["cases_by_kind"].items())
    genres: dict[str, int] = {}
    for e in index["documents"]:
        genres[e["genre"]] = genres.get(e["genre"], 0) + 1
    rows = "\n".join(f"| {g} | {n} |" for g, n in sorted(genres.items()))
    return f"""# データセット説明書 — yakkan-calc {index["version"]}

## 何のためのものか

ドキュメント読み取りシステム（OCR・レイアウト解析・VLM・構造化抽出）と、
**約款を読んで計算規定を実装する**能力を測るためのデータである。
実在の約款は著作権・正解データ不在・ページ数過多の問題があるので、
構造的な特徴を再現した合成文書と**完全な正解**を対で作っている。

## 規模

| 項目 | 数 |
|---|---|
| 文書 | {t["documents"]} |
| 種目 | {t["genres"]} |
| ルール（計算・判定の規定） | {t["rules"]} |
| テストケース | {t["cases"]}（{kinds}） |
| 描画結果（レイアウト） | {t["layouts"]} |
| スタイル | {len(t["styles"])}（{", ".join(t["styles"])}） |

| 種目 | 文書数 |
|---|---|
{rows}

## どう作ったか

1. 既定の架空約款（別プロジェクト `yakkan-synth` が生成）に、計算・判定の規定を機械的に足す。
2. **計算仕様が唯一の正**である。約款の文言・正解プログラム・テストの期待値は、
   すべて同じ仕様から機械的に作る。文言とプログラムを別々に書いていない。
3. 12 の検証ゲートを通す。通らない文書は出力しない（仕様の整合・根拠の逐語一致・
   明示性・設例の一致・実装の一致・テストの十分性・名前の衝突・本体の lint と verify・決定性）。
4. **生成の経路で LLM を使っていない。** 文言は文型（テンプレート）から組んでいる。

## 正解が入っていることの意味

**学習に使うとこのデータセットで評価できなくなる。**
採点のときは `icc export` で評価対象に渡すものを絞る。

## 限界（知っておいてほしいこと）

- **架空である。** 実在の約款の文言は 1 文字も含まない。実在約款の読み取り性能を
  そのまま予測するものではない。
- **三値論理が最大の難所である。** 入力が不明（`None`）のケースが
  {t["cases_by_kind"].get("unknown", 0)} 件ある。「ほかの条件で結論が決まるなら確定値を返す」
  という取り決めで、`calc/tasks.jsonl` の `conventions` に書いてある。
- **既定の約款には、一義に読めない計算規定が残っている。** 足した規定は明示性のゲートで
  一義性を強制しているが、既定の部分にはその保証がない。
- **縦書き・スキャン劣化画像は入っていない。** 日本語横書きのみである。

## 連絡先

架空の文書なので、文書中の連絡先は使えない。データセットについては配布元を見ること。
"""


def _license() -> str:
    return """このデータセットの文書・正解データ・生成器の出力は、作成者の指定する条件で提供される。

この配布物は**配布の準備として機械的に組み立てたもの**であり、
ライセンスの選定は人が行う（`HITL.md` H4）。
ライセンスを確定するまで、再配布・商用利用の可否は未定である。

注意：
- 文書は完全に架空であり、実在の保険会社・商品・約款とは関係がない。
- **正解が含まれる。** 学習データに使うと、このデータセットでの評価が成り立たなくなる。
"""
