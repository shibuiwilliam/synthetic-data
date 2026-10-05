"""本体 `content/` の状態を一息で測る（T12・`HITL.md` H10 (c)）。

本体には**並行して別の作業が入る**。拡張が入れた文言が気づかないうちに上書きされた
実例があるので（`content/life-0001` `life-0003`）、本体を触る作業の**前後で必ずこれを回す**。

    PYTHONPATH=src python scripts/check_base.py            # いまの状態を表示
    PYTHONPATH=src python scripts/check_base.py --save      # 基準として保存
    PYTHONPATH=src python scripts/check_base.py --diff      # 保存した基準と比べる

`--diff` で差分が出たら、**自分の変更か、他の作業の変更かを確かめるまで先に進まない。**
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from insurance_contracts_calculation import base_adapter as ba  # noqa: E402
from insurance_contracts_calculation.verify.lint_base import lint_base  # noqa: E402

#: 計算規定を足せる種目（`teikan`・`jyusetsu` は条を持たない／計算規定が無い）
GENRES = ("auto", "quake", "health", "oneday", "travel", "golf", "group", "life")
BASELINE = Path(__file__).resolve().parent / ".base_state.json"


def content_dirs(root: Path) -> list[Path]:
    return sorted(d for d in root.iterdir() if d.is_dir() and d.name.split("-")[0] in GENRES)


def measure(root: Path) -> dict:
    """文書ごとに「曖昧な箇所の数」「ページ余裕」「parts のハッシュ」を測る。"""
    out: dict[str, dict] = {}
    for d in content_dirs(root):
        parts = sorted((d / "parts").glob("*.json"))
        digest = hashlib.sha256()
        for f in parts:
            digest.update(f.name.encode("utf-8"))
            digest.update(f.read_bytes())
        try:
            report = lint_base(str(d))
            base = ba.load_base(d)
            slack = round(ba.max_pages() - ba.estimate_pages(base.data, base.genre), 2)
            out[d.name] = {
                "ambiguous": report["ambiguous_total"],
                "slack": slack,
                "parts": len(parts),
                "sha": digest.hexdigest()[:16],
            }
        except Exception as e:  # noqa: BLE001  読めない content は理由を残して続ける
            out[d.name] = {"error": f"{type(e).__name__}: {e}"}
    return out


def show(state: dict) -> None:
    bad = {k: v for k, v in state.items() if v.get("error")}
    amb = {k: v["ambiguous"] for k, v in state.items() if v.get("ambiguous")}
    tight = {k: v["slack"] for k, v in state.items() if not v.get("error") and v["slack"] < 1.8}
    print(f"対象 {len(state)} 文書")
    print(f"  一義に読めない箇所: {sum(amb.values())} 件" + (f" {amb}" if amb else "（ゼロ）"))
    print(f"  ページ余裕 1.8 未満（拡張の対象外）: {len(tight)} 件 {tight}")
    if bad:
        print(f"  ★読めない content: {bad}")


def diff(old: dict, new: dict) -> int:
    keys = sorted(set(old) | set(new))
    rows = []
    for k in keys:
        a, b = old.get(k), new.get(k)
        if a == b:
            continue
        if a is None:
            rows.append((k, "追加された", "", ""))
        elif b is None:
            rows.append((k, "消えた", "", ""))
        else:
            for field in ("ambiguous", "slack", "parts", "sha"):
                if a.get(field) != b.get(field):
                    rows.append((k, field, a.get(field), b.get(field)))
    if not rows:
        print("基準からの差分: **なし**")
        return 0
    print(f"基準からの差分: {len(rows)} 件")
    for k, field, a, b in rows:
        print(f"  {k:14} {field:10} {a} → {b}")
    print("\n★ 自分の変更か、ほかの作業の変更かを確かめるまで先に進まない（HITL.md H10）")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default="../content", help="本体の content ディレクトリ")
    ap.add_argument("--save", action="store_true", help="いまの状態を基準として保存する")
    ap.add_argument("--diff", action="store_true", help="保存した基準と比べる")
    args = ap.parse_args()

    state = measure(Path(args.root))
    show(state)
    if args.save:
        BASELINE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n基準を書いた: {BASELINE}")
        return 0
    if args.diff:
        if not BASELINE.is_file():
            print(f"\n基準が無い。先に --save で作る: {BASELINE}")
            return 1
        print()
        return diff(json.loads(BASELINE.read_text(encoding="utf-8")), state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
