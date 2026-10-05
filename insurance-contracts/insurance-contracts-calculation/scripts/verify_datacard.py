"""データカードの**測り方そのもの**を検算する（`docs/data_card.md` §5）。

`export/datacard.py` を使わない別経路で `dataset/` を数え直し、カードに載っている数と
突き合わせる。前提を共有しないために、

  * `Doc`（索引）を使わず、`policy.json` の木を自力で辿る、
  * PDF のフォントは**全文字を走査**して読む（カード側はフォント資源から読む）、
  * 件数は正規表現でカードの本文から取り出す、

という 3 点を変えてある。鮮度の検査（`icc datacard check`）とは別物で、あちらは
「カードがいまの `dataset/` から生成されたか」を見る。

    PYTHONPATH=src python scripts/verify_datacard.py [dataset]
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CARD_NAME = "data-card.md"


def scalar(card: str, label: str) -> int:
    """カードの `| ラベル | 1,234 |` から数を取る（複合欄は最初の数）。"""
    pattern = re.compile(r"^\| " + re.escape(label) + r" \| ([0-9,]+)", re.MULTILINE)
    m = pattern.search(card)
    if m is None:
        raise AssertionError(f"カードに「{label}」の行が無い")
    return int(m.group(1).replace(",", ""))


def count_table(card: str, heading: str, label: str) -> dict[str, int]:
    """見出し `heading` の直後にある「`label` | 件数」の表を読む。"""
    start = card.index(heading)
    body = card[start:]
    head = f"| {label} | 件数"
    if head not in body:
        raise AssertionError(f"{heading} の下に「{label}」の表が無い")
    body = body[body.index(head) :]
    out: dict[str, int] = {}
    for line in body.splitlines()[2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        out[cells[0]] = int(cells[1].replace(",", ""))
    return out


def walk_nodes(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from walk_nodes(node.get("children", []) or [])


def walk_blocks(blocks: list[dict]):
    for block in blocks or []:
        yield block
        yield from walk_blocks(block.get("blocks", []) or [])


def policy_counts(policy: dict) -> dict[str, int]:
    """`policy.json` を自力で数える（`Doc` を使わない）。"""
    roots = list(policy["body"]) + list(policy["appendices"])
    nodes = list(walk_nodes(roots))
    blocks = list(walk_blocks([b for n in nodes for b in n.get("blocks", []) or []]))
    front = policy["front_matter"]
    extra = list(front.get("preface", []) or [])
    for key in ("purpose_index", "rider_index", "petname_table"):
        value = front.get(key)
        if isinstance(value, dict) and value.get("type") == "table":
            extra.append(value)
    extra += list(policy["back_matter"].get("colophon", []) or [])
    blocks += list(walk_blocks(extra))
    tables = [b for b in blocks if b["type"] == "table"]
    figures = [b for b in blocks if b["type"] == "figure"]
    derived = policy["derived"]
    return {
        "nodes": len(nodes),
        "blocks": len(blocks),
        "tables": len(tables),
        "cells": sum(len(row) for b in tables for row in b.get("grid", [])),
        "figures": len(figures),
        "formulas": len(derived["formulas"]),
        "refs": len(derived["refs"]),
        "terms": len(policy.get("defined_terms", [])),
        "constants": len(policy["meta"].get("constants", {})),
        "chars": sum(len(v.get("without_label", "")) for v in derived["plain_text"].values()),
    }


def fonts_by_chars(pdf_path: Path) -> set[str]:
    """全文字を走査してフォント名を集める（カード側はフォント資源から読む）。"""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        return {ch["fontname"].split("+")[-1] for page in pdf.pages for ch in page.chars}


def main(argv: list[str]) -> int:
    dataset = Path(argv[1]) if len(argv) > 1 else ROOT / "dataset"
    card_path = dataset / CARD_NAME
    if not card_path.is_file():
        print(f"{card_path} が無い。先に `icc datacard update {dataset}` を実行する", file=sys.stderr)
        return 2
    card = card_path.read_text(encoding="utf-8")
    docs = sorted(p.parent.parent for p in dataset.glob("*/calc/manifest.json"))

    totals = Counter()
    patterns: Counter[str] = Counter()
    case_kinds: Counter[str] = Counter()
    gates_ok: Counter[str] = Counter()
    fonts: Counter[str] = Counter()
    rule_kinds: Counter[str] = Counter()
    genres: Counter[str] = Counter()
    bases: set[str] = set()
    styles: set[str] = set()
    for doc in docs:
        man = json.loads((doc / "calc" / "manifest.json").read_text(encoding="utf-8"))
        spec = json.loads((doc / "calc" / "spec.json").read_text(encoding="utf-8"))
        policy = json.loads((doc / "policy.json").read_text(encoding="utf-8"))
        bases.add(man["base_content_id"])
        genres[man["genre"]] += 1
        totals["documents"] += 1
        totals["rules"] += len(spec["rules"])
        totals["params"] += len(spec["params"])
        totals["steps"] += sum(len(r["steps"]) for r in spec["rules"])
        for rule in spec["rules"]:
            patterns[rule["presentation"]["pattern"]] += 1
            rule_kinds[rule["kind"]] += 1
        for line in (doc / "calc" / "cases.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                case_kinds[json.loads(line)["kind"]] += 1
        for name in ("tasks.jsonl", "tasks_H1.jsonl", "tasks_H2.jsonl"):
            path = doc / "calc" / name
            totals["taskcards"] += len(
                [x for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
            )
        for code, result in man["gates"].items():
            if result.get("ok"):
                gates_ok[code] += 1
            if code == "G7":
                totals["mutants"] += result.get("mutants", 0)
        for key, value in policy_counts(policy).items():
            totals[key] += value
        for program in sorted((doc / "calc" / "programs").glob("*.py")):
            totals["programs"] += 1
            totals["program_lines"] += len(program.read_text(encoding="utf-8").splitlines())
        for layout_path in sorted(doc.glob("*/layout.json")):
            layout = json.loads(layout_path.read_text(encoding="utf-8"))
            styles.add(layout["style_id"])
            totals["layouts"] += 1
            totals["pages"] += layout["page_count"]
            totals["page_images"] += len(list((layout_path.parent / "pages").glob("*.png")))
            for font in fonts_by_chars(layout_path.parent / "doc.pdf"):
                fonts[font] += 1

    checks: list[tuple[str, object, object]] = [
        ("文書", scalar(card, "文書（`policy.json` ＋ 1 組の正解）"), totals["documents"]),
        ("既定の約款", scalar(card, "既定の約款（本体の執筆物）"), len(bases)),
        ("種目", scalar(card, "種目"), len(genres)),
        ("体裁", scalar(card, "体裁（style）"), len(styles)),
        ("レイアウト", scalar(card, "描画結果（レイアウト）"), totals["layouts"]),
        ("ページ", scalar(card, "ページ"), totals["pages"]),
        ("ページ画像", scalar(card, "ページ画像（PNG）"), totals["page_images"]),
        ("ルール", scalar(card, "ルール（計算・判定の規定）"), totals["rules"]),
        ("手順", scalar(card, "手順（名前つきの中間の額）"), totals["steps"]),
        ("パラメータ", scalar(card, "パラメータ（仕様が参照する定数）"), totals["params"]),
        ("テストケース", scalar(card, "テストケース"), sum(case_kinds.values())),
        ("タスクカード", scalar(card, "タスクカード（出題。H0・H1・H2 の合計）"), totals["taskcards"]),
        ("正解プログラム", scalar(card, "正解プログラム"), totals["programs"]),
        ("変異体", scalar(card, "変異体（テストの十分性の検査）"), totals["mutants"]),
        ("本文の文字数", scalar(card, "約款の本文の文字数（`derived.plain_text`）"), totals["chars"]),
        ("ノード", scalar(card, "約款のノード / ブロック / 根拠単位"), totals["nodes"]),
        ("表", scalar(card, "表 / セル"), totals["tables"]),
        ("図", scalar(card, "図 / ノード / 辺"), totals["figures"]),
        ("算式", scalar(card, "算式"), totals["formulas"]),
        ("参照", scalar(card, "参照（`{ref:}` の解決結果）"), totals["refs"]),
        ("定数", scalar(card, "定数（`{const:}`）"), totals["constants"]),
        ("パターンの分布", count_table(card, "### 5.1 パターン", "パターン"), dict(patterns)),
        ("ルールの種別", count_table(card, "### 5.2 ルールの種別と配置", "種別"), dict(rule_kinds)),
        ("ケースの種別", count_table(card, "### 6.1 テストケース", "種別"), dict(case_kinds)),
        (
            "埋め込みフォント",
            count_table(card, "## 8. 版面", "PDF に埋め込まれていたフォント（レイアウト数）"),
            dict(fonts),
        ),
    ]
    bad = [(name, got, want) for name, got, want in checks if got != want]
    for name, got, want in checks:
        mark = "ok " if (name, got, want) not in bad else "NG "
        print(f"{mark}{name}: カード={got} 再計算={want}")
    # ゲートの表は「測った文書 / ok」の 2 列なので、`count_table` ではなく行ごとに見る
    for code, ok in sorted(gates_ok.items()):
        line = re.search(rf"^\| `{code}` \| [^|]+ \| ([0-9,]+) \| ([0-9,]+) \|", card, re.MULTILINE)
        if line is None:
            bad.append((f"ゲート {code}", "（行が無い）", ok))
            continue
        shown = int(line.group(2).replace(",", ""))
        if shown != ok:
            bad.append((f"ゲート {code} の ok", shown, ok))
        print(f"{'ok ' if shown == ok else 'NG '}ゲート {code} の ok: カード={shown} 再計算={ok}")
    print()
    if bad:
        print(f"不一致 {len(bad)} 件:", file=sys.stderr)
        for name, got, want in bad:
            print(f"  - {name}: カード={got} 再計算={want}", file=sys.stderr)
        return 1
    print(f"突合 {len(checks) + len(gates_ok)} 項目すべて一致（文書 {len(docs)} 件）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
