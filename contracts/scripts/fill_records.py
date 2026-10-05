"""grid から `records`（意味レコード）を機械的に導出する補助スクリプト。

CLAUDE.md §2-4／§5 は表を `grid`（結合セル込みの見た目構造）と
`records`／`header_path`（意味）の二重表現で持つことを求めているが、
P4-c で執筆した7文書の表はほぼすべて `records: null` だった。

`header_rows == 1` かつ結合セル（colspan/rowspan > 1）が無い表は、
「表頭のセル文字列 → その列の値」の辞書に機械的に落とせる。
それ以外（表頭が複数行・結合セルあり）は意味の対応付けに判断が要るので
**書き換えず、一覧で報告する**。手で埋めること。

    uv run python scripts/fill_records.py content/<cid>            # 下見（書き換えない）
    uv run python scripts/fill_records.py content/<cid> --write    # parts/*.json を書き換える
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# 結合セルが無く表頭が1行なら機械導出できる
Derivable = tuple[str, list[dict[str, str]]]

# 列挙表は「文と一体の箇条書き」であって参照表ではないので、
# records を持たせても grid 以上の情報が増えない（table_lookup QA の対象外）。
NO_RECORDS_TYPES = frozenset({"enumeration", "exclusions"})


def _cells(row: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in row if isinstance(c, dict)]


def _has_merge(grid: list[list[dict[str, Any]]]) -> bool:
    return any(
        int(c.get("colspan", 1)) > 1 or int(c.get("rowspan", 1)) > 1 for row in grid for c in _cells(row)
    )


def derive(table: dict[str, Any]) -> Derivable | None:
    """機械導出できるなら (table_id, records) を返す。できないなら None。"""
    grid = table.get("grid") or []
    layout = table.get("layout") or {}
    if len(grid) < 2:
        return None
    if int(layout.get("header_rows", 0)) != 1:
        return None
    if _has_merge(grid):
        return None
    header = [str(c.get("text", "")).strip() for c in _cells(grid[0])]
    if not all(header) or len(set(header)) != len(header):
        return None  # 空の表頭や重複する表頭は意味レコードの鍵にできない
    records: list[dict[str, str]] = []
    for row in grid[1:]:
        values = [str(c.get("text", "")) for c in _cells(row)]
        if len(values) != len(header):
            return None
        records.append(dict(zip(header, values, strict=True)))
    return str(table.get("id", "")), records


def walk(obj: Any, found: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if obj.get("type") == "table":
            found.append(obj)
        for value in obj.values():
            walk(value, found)
    elif isinstance(obj, list):
        for value in obj:
            walk(value, found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("content_dir", type=Path)
    parser.add_argument("--write", action="store_true", help="parts/*.json を書き換える")
    args = parser.parse_args()

    files = sorted((args.content_dir / "parts").glob("*.json"))
    files += [args.content_dir / "doc.json"]
    done: list[str] = []
    manual: list[str] = []
    already: list[str] = []
    skipped: list[str] = []

    for path in files:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        tables: list[dict[str, Any]] = []
        walk(data, tables)
        changed = False
        for table in tables:
            table_id = str(table.get("id", "?"))
            if table.get("records"):
                already.append(table_id)
                continue
            if table.get("semantic_type") in NO_RECORDS_TYPES:
                skipped.append(f"{table_id}（{table.get('semantic_type')}）")
                continue
            result = derive(table)
            if result is None:
                rows = len(table.get("grid") or [])
                header_rows = (table.get("layout") or {}).get("header_rows")
                merged = _has_merge(table.get("grid") or [])
                reason = "結合セルあり" if merged else f"header_rows={header_rows}"
                manual.append(f"{table_id}（{rows}行・{reason}）")
                continue
            _, records = result
            table["records"] = records
            done.append(f"{table_id}（{len(records)}行）")
            changed = True
        if changed and args.write:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    verb = "書き込んだ" if args.write else "機械導出できる"
    print(f"== {verb}表（{len(done)}） ==")
    for item in done:
        print(f"  {item}")
    print(f"== 手で埋める表（{len(manual)}） ==")
    for item in manual:
        print(f"  {item}")
    if skipped:
        print(f"== records 不要と判断した表（{len(skipped)}。列挙表は参照表ではない） ==")
        for item in skipped:
            print(f"  {item}")
    if already:
        print(f"== すでに records がある表（{len(already)}） ==")
        for item in already:
            print(f"  {item}")
    if not args.write and done:
        print("\n--write を付けると parts/*.json に書き込む。書き込み後は build → render → verify。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
