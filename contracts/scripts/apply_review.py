"""`apply` QA の人手レビュー用シートを作る（HITL_TODO.md の H5）。

`apply`（場面適用）の答えは**計算の結果**なので、L14 の包含検査にも eval にも引っかからない。
人間が検算するほかないが、そのために PDF を開いて根拠の条文を探すのは手間が大きい。
この台本は、**問い・答え・根拠の条文（紙面の文字列）・ページ・AI 側の検算・見てほしい点**を
1 枚にまとめる。検算と「見てほしい点」の文は `specs/apply_notes.yaml` に置く
（生成物を手で書き換えないため。CLAUDE.md §0.4-3）。

    uv run python scripts/apply_review.py            # HITL_apply_review.md を書き出す
    uv run python scripts/apply_review.py --check    # 中身を確かめるだけ（書き出さない）
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CONTENT = Path("content")
DATASET = Path("dataset")
NOTES = Path("specs/apply_notes.yaml")
OUT = Path("HITL_apply_review.md")


def _notes() -> dict:
    """検算メモ（`specs/apply_notes.yaml`）。無ければ空で続ける。"""
    if not NOTES.is_file():
        return {}
    import yaml

    return yaml.safe_load(NOTES.read_text(encoding="utf-8")) or {}


def _dataset_for(content_id: str) -> Path | None:
    """その content の描画結果（どれか 1 つ。根拠の文字列とページを引くのに使う）。"""
    for directory in sorted(DATASET.glob(f"{content_id}--*")):
        if (directory / "answer.json").is_file():
            return directory
    return None


def _evidence_text(directory: Path) -> dict[str, tuple[str, int | None]]:
    """要素 id → (紙面の文字列, ページ)。"""
    source = json.loads((directory / "source.json").read_text(encoding="utf-8"))
    layout = json.loads((directory / "layout.json").read_text(encoding="utf-8"))
    pages = {
        element_id: (value.get("fragments") or [{}])[0].get("page")
        for element_id, value in layout.get("elements", {}).items()
    }
    out: dict[str, tuple[str, int | None]] = {}
    for element_id, plain in source["derived"]["plain_text"].items():
        out[element_id] = (plain.get("with_label") or plain["without_label"], pages.get(element_id))
    return out


def build() -> str:
    header = [
        "# HITL_apply_review.md — `apply` QA の検算シート（自動生成）",
        "",
        "> `uv run python scripts/apply_review.py` で作り直せる。**手で編集しない。**",
        "> 判断は `HITL_TODO.md` の H5 の「決定」欄に記入する（この表は**材料**）。",
        "> 検算と「見てほしい点」の文は `specs/apply_notes.yaml` にある（直すならそちら）。",
        "",
    ]
    lines: list[str] = []
    notes = _notes()
    total = 0
    missing: list[str] = []
    for content_dir in sorted(CONTENT.iterdir()):
        qa_path = content_dir / "qa_authored.json"
        if not qa_path.is_file():
            continue
        items = [
            item
            for item in json.loads(qa_path.read_text(encoding="utf-8"))["items"]
            if item.get("type") == "apply"
        ]
        if not items:
            continue
        directory = _dataset_for(content_dir.name)
        evidence = _evidence_text(directory) if directory else {}
        doc = json.loads((content_dir / "doc.json").read_text(encoding="utf-8"))
        lines.append(f"## {content_dir.name}（{doc['meta'].get('title', '')}）")
        lines.append("")
        note = notes.get(content_dir.name) or {}
        if note.get("review"):
            lines.append(f"> **あわせて見てほしいこと**：{note['review'].strip()}")
            lines.append("")
        for item in items:
            total += 1
            lines.append(f"### {item['id']}")
            lines.append("")
            lines.append(f"- **問い**：{item['question']}")
            lines.append(f"- **答え**：**{item['answer']}**")
            lines.append("- **根拠（紙面の文字列）**：")
            for element_id in item.get("evidence", []):
                text, page = evidence.get(element_id, ("（見つからない）", None))
                where = f"p.{page}" if page else "？"
                lines.append(f"  - `{element_id}`（{where}）{text}")
            detail = (note.get("questions") or {}).get(item["id"]) or {}
            if detail.get("derivation"):
                lines.append("- **AI 側の検算**：")
                for step in detail["derivation"]:
                    lines.append(f"  - {step}")
            else:
                missing.append(f"{content_dir.name}/{item['id']}")
            if detail.get("caution"):
                lines.append(f"- **読み方に幅がある点**：{detail['caution'].strip()}")
            lines.append("")
    header.insert(5, f"> 対象：**{total} 問**（`apply` 型のみ）")
    if missing:
        header.insert(6, f"> **検算メモの無い問い：{len(missing)} 件**（{'、'.join(missing[:5])}…）")
    return "\n".join(header + lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="書き出さずに行数だけ見る")
    args = parser.parse_args()
    text = build()
    if args.check:
        print(f"{len(text.splitlines())} 行")
        return
    OUT.write_text(text + "\n", encoding="utf-8")
    print(f"書いた {OUT}（{len(text.splitlines())} 行）")


if __name__ == "__main__":
    main()
