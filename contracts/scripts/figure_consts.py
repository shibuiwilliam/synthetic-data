"""図・算式の中の数値を `{const:}` に寄せる（docs/shared_fixes.md A2）。

A2 で図と算式のトークンが解決されるようになったので、`meta.constants` に宣言済みの値が
図の中に生文字列で書かれているところをトークンに置き換える。置き換えたあと、
build が解決した文字列が元の生文字列と一字一句同じであることを確かめる（`--check`）。

    uv run python scripts/figure_consts.py content/<cid> [--write]

値が同じ定数が複数あるとき（どれを指すか決められない）と、数字に挟まれた一致
（「２０４３年」の中の「３年」など）は置き換えず、理由を出す。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DIGIT = re.compile(r"[0-9０-９]")
#: 図の中で「読み取れる文字」が入るキー。ここだけを置き換える。
TEXT_KEYS = (
    "label",
    "title",
    "detail",
    "asks",
    "docs",
    "note",
    "value",
    "meaning",
    "start",
    "end",
    "ticks",
    # timeline の区間・目印は目盛の文字列そのもので位置を指すので、ここも揃えないと
    # 「目盛に無い」と L06 に言われる
    "at",
    "from",
    "to",
    "rows",
    "cols",
    "box",
    "num",
    "den",
    "alt",
    "facts",
    "text",
)


def candidates(raw: str, constants: dict[str, str]) -> tuple[list[tuple[str, str]], list[str]]:
    """置き換えてよい (key, value) と、見送った理由を返す。"""
    by_value: dict[str, list[str]] = {}
    for key, value in constants.items():
        if value and len(value) >= 2 and value in raw:
            by_value.setdefault(value, []).append(key)
    ok: list[tuple[str, str]] = []
    skipped: list[str] = []
    for value, keys in by_value.items():
        if len(keys) > 1:
            skipped.append(f"{value!r} は {'/'.join(keys)} の値が同じで決められない")
            continue
        if any(_digit_adjacent(raw, m.start(), m.end()) for m in re.finditer(re.escape(value), raw)):
            skipped.append(f"{value!r} が数字に挟まれている（{raw[:30]!r}）")
            continue
        ok.append((keys[0], value))
    # 長い値から置き換える（「４０％」が「４０％以上６０％以下」を壊さないように）
    ok.sort(key=lambda kv: len(kv[1]), reverse=True)
    return ok, skipped


def _digit_adjacent(raw: str, start: int, end: int) -> bool:
    before = raw[start - 1] if start > 0 else ""
    after = raw[end] if end < len(raw) else ""
    return bool(DIGIT.match(before) or DIGIT.match(after))


def convert(raw: str, constants: dict[str, str]) -> tuple[str, list[str]]:
    if "{" in raw:
        return raw, []
    ok, skipped = candidates(raw, constants)
    out = raw
    for key, value in ok:
        out = out.replace(value, f"{{const:{key}}}")
    return out, skipped


def walk(obj: object, constants: dict[str, str], report: list[str], in_figure: bool = False) -> object:
    if isinstance(obj, dict):
        here = in_figure or obj.get("type") in ("figure", "formula")
        out: dict[str, object] = {}
        for key, value in obj.items():
            if here and key in TEXT_KEYS:
                out[key] = _convert_value(value, constants, report)
            else:
                out[key] = walk(value, constants, report, here)
        return out
    if isinstance(obj, list):
        return [walk(v, constants, report, in_figure) for v in obj]
    return obj


def _convert_value(value: object, constants: dict[str, str], report: list[str]) -> object:
    if isinstance(value, str):
        new, skipped = convert(value, constants)
        report.extend(skipped)
        return new
    if isinstance(value, list):
        return [_convert_value(v, constants, report) for v in value]
    if isinstance(value, dict):
        return {k: _convert_value(v, constants, report) for k, v in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("content", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    doc = json.loads((args.content / "doc.json").read_text(encoding="utf-8"))
    constants: dict[str, str] = doc["meta"].get("constants") or {}
    if not constants:
        print(f"{args.content.name}: meta.constants が無い")
        return 0

    changed = 0
    report: list[str] = []
    for part in sorted((args.content / "parts").glob("*.json")):
        before = part.read_text(encoding="utf-8")
        data = json.loads(before)
        after = json.dumps(walk(data, constants, report), ensure_ascii=False, indent=2) + "\n"
        if after != before:
            changed += 1
            if args.write:
                part.write_text(after, encoding="utf-8")
    print(f"{args.content.name}: {changed} part を{'書き換えた' if args.write else '書き換える'}")
    for line in sorted(set(report)):
        print("  見送り:", line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
