"""`dataset/views/*.jsonl`（と Hub の config が指す jsonl）が表形式に落ちるかを確かめる。

    uv run python scripts/verify_views.py                  # 型の走査だけ（追加依存なし）
    uv sync --group publish && uv run python scripts/verify_views.py   # parquet への変換も試す

Hugging Face の Dataset Viewer は jsonl を Arrow（parquet）に変換して表示する。**1 つの列に
複数の型が混ざると変換が落ちる**（`qa.json` の `answer` は float / str / list が混在するため、
views では型ごとに列を分けてある。`docs/publishing.md` §4）。この検査は 2 段で行う。

1. 追加依存なしの走査：全行の全列の Python 型を集め、`null` を除いて 2 種以上あれば落とす。
   リストの要素型も見る。**全行 null の列**も報告する（Arrow では型が決まらず、
   後から行を足したときに壊れる芽になる）。
2. `pyarrow` があれば実際に Table に変換して推論されたスキーマを出す（Viewer と同じ経路）。

食い違えば終了コード 1。仕様は `docs/publishing.md`。
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

DATASET = Path("dataset")
#: 検査する jsonl（`keiyaku.publish.CONFIGS` が Hub に宣言しているもの）
TARGETS = (
    "views/documents.jsonl",
    "views/pages.jsonl",
    "views/qa.jsonl",
    "search/passages.jsonl",
    "search/queries.jsonl",
    "search/qrels.jsonl",
)


def _type_name(value: object) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "null" if value is None else type(value).__name__


def scan(paths: list[Path]) -> list[str]:
    """列ごとの型を走査する。返り値は問題の説明（空なら合格）。"""
    problems: list[str] = []
    for path in paths:
        types: dict[str, set[str]] = defaultdict(set)
        rows = 0
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                rows += 1
                row = json.loads(line)
                for key, value in row.items():
                    types[key].add(_type_name(value))
                    if isinstance(value, list):
                        for item in value:
                            types[f"{key}[]"].add(_type_name(item))
                        if not value:
                            types[f"{key}[]"].add("(空)")
                    if isinstance(value, dict):
                        for sub, inner in value.items():
                            types[f"{key}.{sub}"].add(_type_name(inner))
        label = path.as_posix()
        print(f"{label}: {rows:,} 行 / {len([k for k in types if '[' not in k and '.' not in k])} 列")
        for key, found in sorted(types.items()):
            concrete = {t for t in found if t not in ("null", "(空)")}
            # int と float の混在は Arrow が double に寄せるので許す（それ以外の混在は落ちる）
            if len(concrete) > 1 and concrete != {"int", "float"}:
                problems.append(f"{label}: 列 `{key}` に型が混在する（{sorted(found)}）")
            if not concrete and rows:
                problems.append(f"{label}: 列 `{key}` が全行 null（Arrow で型が決まらない）")
    return problems


def to_arrow(paths: list[Path]) -> list[str]:
    """`pyarrow` で実際に変換する（Viewer と同じ経路）。無ければ飛ばす。"""
    try:
        import pyarrow as pa
        import pyarrow.json as pj
        import pyarrow.parquet as pq
    except ImportError:
        print("（pyarrow が無いので変換は飛ばす。`uv sync --group publish`）")
        return []
    problems: list[str] = []
    for path in paths:
        try:
            table = pj.read_json(path)
            buffer = pa.BufferOutputStream()
            pq.write_table(table, buffer)
            size = len(buffer.getvalue())
            print(
                f"{path.as_posix()}: Arrow {table.num_rows:,} 行 × {table.num_columns} 列 "
                f"→ parquet {size / 1024:.0f} KiB"
            )
        except Exception as exc:  # 変換できない＝Viewer で落ちる
            problems.append(f"{path.as_posix()}: Arrow に変換できない（{type(exc).__name__}: {exc}）")
    return problems


def elements_glob() -> list[str]:
    """`*/elements.jsonl`（Hub は glob で 1 つの config にまとめる）が**同じ列の集合**かを見る。

    文書ごとに列が違うと、Hub がまとめるときに落ちる（例：表が 1 つも無い文書が出ると
    `table` 列が無くなる）。`pyarrow` があれば実際に連結も試す。
    """
    paths = sorted(DATASET.glob("*/elements.jsonl"))
    if not paths:
        return [f"{DATASET}/*/elements.jsonl が無い（`keiyaku export` を実行する）"]
    problems: list[str] = []
    try:
        import pyarrow as pa
        import pyarrow.json as pj
    except ImportError:
        print("（pyarrow が無いので */elements.jsonl の連結は飛ばす）")
        return []
    tables = [pj.read_json(path) for path in paths]
    shapes = {tuple(sorted(t.schema.names)) for t in tables}
    if len(shapes) > 1:
        problems.append(
            f"*/elements.jsonl の列の集合が {len(shapes)} 種ある"
            "（Hub は glob で 1 つにまとめるので落ちる。全文書で同じ列になるようにする）"
        )
    try:
        joined = pa.concat_tables(tables, promote_options="default")
        print(
            f"{DATASET}/*/elements.jsonl: {len(paths)} ファイル → Arrow "
            f"{joined.num_rows:,} 行 × {joined.num_columns} 列"
        )
    except Exception as exc:
        problems.append(f"*/elements.jsonl を連結できない（{type(exc).__name__}: {exc}）")
    return problems


def main() -> int:
    paths = [DATASET / name for name in TARGETS]
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for path in missing:
            print(f"[ng] {path} が無い（`uv run keiyaku export` を実行する）")
        return 2
    problems = scan(paths)
    problems += to_arrow(paths)
    problems += elements_glob()
    if problems:
        print(f"\n[ng] {len(problems)} 件")
        for line in problems:
            print(f"  {line}")
        return 1
    print(f"\n[ok] {len(paths)} ファイルと */elements.jsonl のすべてが表形式に落ちる")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
