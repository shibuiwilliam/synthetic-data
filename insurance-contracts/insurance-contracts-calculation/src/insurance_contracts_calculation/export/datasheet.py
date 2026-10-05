"""データセットの説明書と公開パッケージ（DESIGN.md §10.3）。

公開してよいものと渡さないものを**機械的に**分ける。
正解（仕様・プログラム・正解表・テストケース）が混ざらないことをテストで固定する。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..testgen.taskcards import CONVENTIONS
from .layout import PRIVATE, is_public


def export_public(target: Path, out: Path) -> dict:
    """評価対象システムに渡してよいファイルだけを書き出す。"""
    target, out = Path(target), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for src in sorted(target.rglob("*")):
        if not src.is_file():
            continue
        rel = str(src.relative_to(target))
        if not is_public(rel):
            continue
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    # 設例だけはケースを公開してよい（DESIGN.md §10.3）
    cases = target / "calc" / "cases.jsonl"
    if cases.is_file():
        rows = [json.loads(line) for line in cases.read_text(encoding="utf-8").splitlines() if line]
        public = [r for r in rows if r["kind"] == "example"]
        if public:
            (out / "calc").mkdir(parents=True, exist_ok=True)
            (out / "calc" / "examples.jsonl").write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in public), encoding="utf-8"
            )
            copied.append("calc/examples.jsonl")
    (out / "DATASHEET.md").write_text(datasheet(target), encoding="utf-8")
    return {"out": str(out), "files": copied + ["DATASHEET.md"], "withheld": list(PRIVATE)}


def datasheet(target: Path) -> str:
    """データセットの説明書（公開パッケージに入れる）。"""
    manifest = json.loads((Path(target) / "calc" / "manifest.json").read_text(encoding="utf-8"))
    tasks = [
        json.loads(line)
        for line in (Path(target) / "calc" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    lines = [
        f"# 計算規定の読み取り課題 {manifest['content_id']}",
        "",
        "この約款は**完全に架空**で、実在の保険会社・商品とは関係がありません。",
        "計算・判定の規定は機械的に生成したもので、文言・正解プログラム・テストは",
        "同じ計算仕様から作られています。",
        "",
        "## 入っているもの",
        "",
        "| ファイル | 内容 |",
        "|---|---|",
        "| `policy.json` | 約款の内容・構造・意味（読み取りの対象） |",
        "| `*.pdf` / `pages/` | 描画結果（一気通貫の評価に使う） |",
        "| `calc/tasks.jsonl` | 実装してもらう関数の契約（関数名・引数・単位） |",
        "| `calc/examples.jsonl` | 約款の囲みに書いた設例（入力と期待値） |",
        "",
        "## 課題",
        "",
        "| 関数 | 題 | 入力 | 出力 |",
        "|---|---|---|---|",
    ]
    for t in tasks:
        args = "、".join(f"{i['name']}（{i['desc']}）" for i in t["inputs"]) or "（なし）"
        unit = t["output"].get("unit") or t["output"]["type"]
        lines.append(f"| `{t['function']}` | {t['title']} | {args} | {unit} |")
    lines += [
        "",
        "## 約束ごと",
        "",
        # 取り決めは `taskcards.CONVENTIONS` が唯一の正。ここに書き写すと必ずずれる
        # （S10-3 で出題・タスクカード・説明書の 3 か所がずれていた）
        *[f"- {text}。" for text in CONVENTIONS.values()],
        "",
        "## 渡していないもの",
        "",
        "正解の計算仕様・正解プログラム・正解表・設例以外のテストケースは含みません。",
    ]
    return "\n".join(lines) + "\n"
