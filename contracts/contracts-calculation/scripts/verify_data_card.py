#!/usr/bin/env python3
"""データカードの「測り方」を別経路で検算する（docs/data_card.md §5）。

`export/datacard.py` を **import しない**。実ファイルを別の手で数え直し、
生成済みの `data-card.md` に出ている行と突き合わせる。
節や項目を足したときに手で 1 回回す（鮮度検査 `datacard check` とは別物）。

使い方:
    uv run --project .. python scripts/verify_data_card.py --data dataset
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zlib
from collections import Counter
from pathlib import Path


def _packs(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir() and (p / "calc" / "manifest.json").is_file())


def _jsonl_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _pdf_pages(path: Path) -> int:
    """`/Type /Pages` の `/Count` から数える（datacard.py は `/Type /Page` を数える＝別経路）。"""
    raw = path.read_bytes()
    counts: list[int] = []
    for m in re.finditer(rb"stream\r?\n", raw):
        start = m.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        try:
            body = zlib.decompress(raw[start:end])
        except zlib.error:
            continue
        counts += [int(c) for c in re.findall(rb"/Type\s*/Pages.{0,400}?/Count\s+(\d+)", body, re.DOTALL)]
    return max(counts) if counts else 0


def _pdf_fonts(path: Path) -> set[str]:
    """`/FontDescriptor` の `/FontName` から取る（datacard.py は `/BaseFont`＝別経路）。"""
    raw = path.read_bytes()
    names: set[str] = set()
    for m in re.finditer(rb"stream\r?\n", raw):
        start = m.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        try:
            body = zlib.decompress(raw[start:end])
        except zlib.error:
            continue
        for chunk in re.findall(rb"/Type\s*/FontDescriptor.{0,400}", body, re.DOTALL):
            for name in re.findall(rb"/FontName\s*/([A-Za-z0-9+#\-]+)", chunk):
                names.add(name.decode("ascii").split("+")[-1])
    return names


def _sizes(root: Path) -> tuple[int, int]:
    files = total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        for name in filenames:
            if name.startswith("."):
                continue
            rel = Path(dirpath, name).relative_to(root)
            if str(rel) == "data-card.md":
                continue
            files += 1
            total += Path(dirpath, name).stat().st_size
    return files, total


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="データカードの測り方を別経路で検算する")
    ap.add_argument("--data", default="dataset")
    args = ap.parse_args(argv)
    root = Path(args.data)
    card_path = root / "data-card.md"
    if not card_path.is_file():
        print(f"ERROR: {card_path} が無い（`datacard update` で作る）", file=sys.stderr)
        return 2
    card = card_path.read_text(encoding="utf-8")

    packs = _packs(root)
    n_docs = len(packs)
    bases: set[str] = set()
    doctypes: Counter = Counter()
    profiles: Counter = Counter()
    seeds: set[int] = set()
    styles: Counter = Counter()
    pages = 0
    chars = 0
    n_rules = n_added = n_bound = 0
    n_cases = n_tasks = n_calc = n_det = 0
    ops: Counter = Counter()
    pat_rules: Counter = Counter()
    pat_docs: Counter = Counter()
    gate_status: dict[str, Counter] = {}
    doctype_bases: dict[str, set[str]] = {}
    fonts: Counter = Counter()
    bind_inc: Counter = Counter()
    bind_exc: Counter = Counter()
    challenge: Counter = Counter()
    case_kinds: Counter = Counter()
    mut_total = mut_detected = 0

    for pack in packs:
        calc = pack / "calc"
        manifest = json.loads((calc / "manifest.json").read_text(encoding="utf-8"))
        bases.add(manifest["base_content_id"])
        profiles[manifest["profile"]] += 1
        seeds.add(manifest["calc_seed"])
        for gate in manifest["gates"]:
            status = "skip" if gate["skipped"] else ("ok" if gate["passed"] else "NG")
            gate_status.setdefault(gate["gate"], Counter())[status] += 1
        for mut in manifest.get("mutation", {}).values():
            mut_total += mut["total"]
            mut_detected += mut["detected"]
        for b in manifest.get("bindings", {}).get("included", []):
            bind_inc[b["binding"]] += 1
        for e in manifest.get("bindings", {}).get("excluded", []):
            bind_exc[e["binding"]] += 1
        if manifest.get("challenge"):
            challenge[manifest["challenge"]["type"]] += 1

        spec = json.loads((calc / "spec.json").read_text(encoding="utf-8"))
        doctype = spec["document"]["doctype"]
        doctypes[doctype] += 1
        doctype_bases.setdefault(doctype, set()).add(manifest["base_content_id"])

        answer_key = json.loads((calc / "answer_key.json").read_text(encoding="utf-8"))
        n_rules += len(answer_key)
        seen: set[str] = set()
        for a in answer_key:
            n_added += a["origin"] == "added"
            n_bound += a["origin"] == "bound"
            pat_rules[a["pattern"]] += 1
            seen.add(a["pattern"])
        for pattern in seen:
            pat_docs[pattern] += 1

        n_cases += _jsonl_count(calc / "cases.jsonl")
        for line in (calc / "cases.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                case_kinds[json.loads(line)["kind"]] += 1
        n_tasks += _jsonl_count(calc / "tasks.jsonl")
        for line in (calc / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                task = json.loads(line)
                n_calc += task["kind"] == "calculation"
                n_det += task["kind"] == "determination"

        for op in json.loads((calc / "patch.json").read_text(encoding="utf-8"))["ops"]:
            ops[op["op"]] += 1

        contract = json.loads((pack / "contract.json").read_text(encoding="utf-8"))
        chars += sum(len(v.get("with_label", "")) for v in contract["derived"]["plain_text"].values())

        for pdf in sorted(pack.glob("*.pdf"))[:1]:
            pages += _pdf_pages(pdf)
            for font in _pdf_fonts(pdf):
                fonts[font] += 1
        for layout_path in sorted(pack.glob("_render/*/layout.json"))[:1]:
            styles[json.loads(layout_path.read_text(encoding="utf-8"))["style_id"]] += 1

    n_files, n_bytes = _sizes(root)
    oracle_path = root / "oracle_report.json"
    oracle = json.loads(oracle_path.read_text(encoding="utf-8")) if oracle_path.is_file() else None

    # 突合は正規表現で行う（行の一部ではなく、数値の並びまで一致させる）
    checks: list[tuple[str, str]] = [
        ("文書数", rf"\| 文書（計算パック） \| {n_docs:,} \|"),
        ("base content 数", rf"\| 既定の契約書（base content） \| {len(bases):,} \|"),
        ("doctype 数", rf"\| doctype（契約書種別） \| {len(doctypes):,} \|"),
        ("プロファイル数", rf"\| 難易度プロファイル \| {len(profiles):,}（宣言 \d+） \|"),
        ("calc_seed", rf"\| calc_seed \| {len(seeds):,}（{'、'.join(str(s) for s in sorted(seeds))}） \|"),
        ("ページ合計", rf"\| ページ（PDF の実測の合計） \| {pages:,} \|"),
        ("本文の文字数", rf"\| 契約書本文の文字数（`derived.plain_text`） \| {chars:,} \|"),
        ("ルール数", rf"\| ルール（計算・判定の規定） \| {n_rules:,} \|"),
        ("added", rf"\| 　うち条項を追加したもの（`origin: added`） \| {n_added:,} \|"),
        ("bound", rf"\| 　うち既定の条項に紐づけたもの（`origin: bound`） \| {n_bound:,} \|"),
        ("関数（タスクカード）", rf"\| 評価用の関数（タスクカード `calc/tasks.jsonl`） \| {n_tasks:,} \|"),
        ("calculation", rf"\| 　うち計算（`calculation`） \| {n_calc:,} \|"),
        ("determination", rf"\| 　うち判定（`determination`） \| {n_det:,} \|"),
        ("テストケース", rf"\| テストケース（`calc/cases.jsonl`） \| {n_cases:,} \|"),
        ("追加した条", rf"\| 追加した条 \| {ops_articles(packs):,} \|"),
        ("追加した定数", rf"\| 追加した定数（`meta.constants`） \| {ops['add_constant']:,} \|"),
        ("頭書へ分離した値", rf"\| 頭書へ分離した値 \| {ops['add_header_row']:,} \|"),
        ("容量", rf"\| 容量 \| {n_bytes / 1048576:.1f} MiB / {n_files:,} ファイル \|"),
    ]
    for op, count in sorted(ops.items()):
        checks.append((f"パッチ操作 {op}", rf"\| `{re.escape(op)}` \| [^|]+ \| {count:,} \|"))
    for pattern in sorted(pat_docs):
        checks.append(
            (
                f"パターン {pattern}",
                rf"\| `{re.escape(pattern)}` \| [^|]* \| {pat_docs[pattern]:,} \| {pat_rules[pattern]:,} \|",
            )
        )
    for profile in sorted(profiles):
        checks.append((f"プロファイル {profile}", rf"\| `{profile}` \| {profiles[profile]:,} \|"))
    for doctype in sorted(doctypes):
        checks.append(
            (
                f"doctype {doctype}",
                rf"\| `{doctype}` \| {len(doctype_bases[doctype]):,} \| {doctypes[doctype]:,} \|",
            )
        )
    for style in sorted(styles):
        checks.append((f"style {style}", rf"\| `{re.escape(style)}` \| {styles[style]:,} \|"))
    for kind, count in sorted(case_kinds.items()):
        checks.append((f"ケース種別 {kind}", rf"\| `{kind}` \| [^|]+ \| {count:,} \|"))
    for gate in sorted(gate_status, key=lambda g: int(g[1:])):
        st = gate_status[gate]
        checks.append(
            (
                f"ゲート {gate}",
                rf"\| `{gate}` \| [^|]+ \| {st.get('ok', 0):,} \| {st.get('skip', 0):,} \| {st.get('NG', 0):,} \|",
            )
        )
    for font, count in sorted(fonts.items()):
        checks.append((f"埋め込みフォント {font}", rf"\| `{re.escape(font)}` \| {count:,} \|"))
    for name in sorted(set(bind_inc) | set(bind_exc)):
        checks.append(
            (
                f"付与 {name}",
                rf"\| `{re.escape(name)}` \| [^|]+ \| {bind_inc[name]:,} \| {bind_exc[name]:,} \|",
            )
        )
    if oracle:
        checks.append(
            (
                "オラクル検査",
                rf"\| 合格した関数 \| {oracle['functions_passed']:,} / {oracle['functions_total']:,} \|",
            )
        )
        for kind, v in sorted(oracle.get("by_case_kind", {}).items()):
            checks.append((f"オラクル {kind}", rf"\| `{kind}` \| {v['ok']:,} \| {v['total']:,} \|"))
    checks.append(("変異の総数", rf"\| 仕様を 1 箇所だけ誤らせた実装 \| {mut_total:,} \|"))
    checks.append(
        (
            "変異の検出",
            rf"\| そのうち検出できたもの \| {mut_detected:,}（{mut_detected / mut_total:.1%}） \|",
        )
    )
    for ctype, count in sorted(challenge.items()):
        checks.append((f"難所 {ctype}", rf"\| `{ctype}` \| [^|]+ \| {count:,} \|"))

    width = max(len(name) for name, _ in checks)
    bad = 0
    for name, needle in checks:
        ok = re.search(needle, card) is not None
        if not ok:
            bad += 1
        print(f"{'OK ' if ok else 'NG '} {name.ljust(width)}  {needle}")
    print()
    print(f"検算 {len(checks)} 項目：一致 {len(checks) - bad} ／ 不一致 {bad}")
    return 1 if bad else 0


def ops_articles(packs: list[Path]) -> int:
    total = 0
    for pack in packs:
        for op in json.loads((pack / "calc" / "patch.json").read_text(encoding="utf-8"))["ops"]:
            if op["op"] == "add_node" and op.get("kind") == "article":
                total += 1
    return total


if __name__ == "__main__":
    raise SystemExit(main())
