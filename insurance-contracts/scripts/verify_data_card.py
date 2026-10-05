"""`dataset/data-card.md` の**測り方そのもの**を検算する（`docs/data_card.md` §5 の後者）。

    uv run python scripts/verify_data_card.py [--dataset dataset]

`yakkan datacard check` は「カードが**いまの dataset から生成したもの**か」（鮮度）を見る。
本スクリプトは「**その測り方が正しいか**」を見る。同じコードを呼んで一致を確かめては
意味がないので、**`yakkan/datacard.py` を一切使わず**に別経路で再計算して突き合わせる。

別経路であることの担保：

- pydantic モデルを通さず、**素の `json.load` で dict を再帰的に歩く**。
- 埋め込みフォントは `/BaseFont`（カードの経路）ではなく **PDF の全文字**（`page.chars`）から測る。
- 分布は `collections.Counter` ではなく素の dict で組み、カードの Markdown の**表から読み戻す**。
- 全件表（文書ごとの行）は 1 行ずつ `manifest.json` と照合する。

測り方を変えたとき（節や項目を足したとき）に手で回す。`make check` には入れない
（PDF の全文字走査が重い）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ARTIFACT_FILES = (
    "doc.pdf",
    "source.json",
    "layout.json",
    "answer.json",
    "qa.json",
    "elements.jsonl",
    "passages.jsonl",
    "render.html",
)


# --- 別経路での再計算 ---------------------------------------------------------


def walk_nodes(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    for node in nodes:
        out.append(node)
        out += walk_nodes(node.get("children") or [])
    return out


def walk_blocks(blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for block in blocks:
        out.append(block)
        out += walk_blocks(block.get("blocks") or [])
    return out


def blocks_of(source: dict) -> list[dict]:
    nodes = walk_nodes(source["body"]) + walk_nodes(source["appendices"])
    blocks = walk_blocks([b for node in nodes for b in node.get("blocks") or []])
    blocks += walk_blocks(source["front_matter"].get("preface") or [])
    blocks += walk_blocks(source["back_matter"].get("colophon") or [])
    blocks += walk_blocks(source["back_matter"].get("contact") or [])
    front = source["front_matter"]
    blocks += [front[k] for k in ("purpose_index", "rider_index", "petname_table") if front.get(k)]
    return blocks


def pdf_fonts_by_chars(pdf_path: Path) -> set[str]:
    """**全文字を走査して**使われたフォント名を集める（カードとは別経路）。"""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        return {char["fontname"].split("+")[-1] for page in pdf.pages for char in page.chars}


def recompute(dataset_dir: Path) -> dict[str, object]:
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["documents"]
    out: dict[str, object] = {}
    totals = dict.fromkeys(
        (
            "pages",
            "page_images",
            "chars",
            "answer_chars",
            "tables",
            "table_cells",
            "merged_cells",
            "figures",
            "figure_nodes",
            "figure_edges",
            "figure_paths",
            "formulas",
            "refs",
            "footnotes",
            "defined_terms",
            "term_uses",
            "constants",
            "enumerations",
            "enumeration_items",
            "toc_entries",
            "qa_items",
            "elements",
            "passages",
        ),
        0,
    )
    node_kinds: dict[str, int] = {}
    block_types: dict[str, int] = {}
    semantic: dict[str, int] = {}
    figure_kinds: dict[str, int] = {}
    qa_types: dict[str, int] = {}
    qa_sources: dict[str, int] = {}
    qa_answer_types: dict[str, int] = {}
    schemes: dict[str, int] = {}
    issuers: dict[str, int] = {}
    columns: dict[str, int] = {}
    regions: dict[str, int] = {}
    embedded: dict[str, int] = {}
    registered: dict[str, int] = {}
    page_sizes: dict[str, int] = {}
    kana: dict[str, int] = {}
    strays: dict[str, int] = {}
    contents: set[str] = set()
    genres: set[str] = set()
    styles: set[str] = set()
    disclaimers: set[str] = set()
    rows: list[tuple[str, ...]] = []

    def bump(table: dict[str, int], key: str, by: int = 1) -> None:
        table[key] = table.get(key, 0) + by

    for entry in entries:
        doc_dir = dataset_dir / entry["doc_id"]
        source = json.loads((doc_dir / "source.json").read_text(encoding="utf-8"))
        layout = json.loads((doc_dir / "layout.json").read_text(encoding="utf-8"))
        derived = source["derived"]
        contents.add(entry["content_id"])
        genres.add(entry["genre"])
        styles.add(entry["style_id"])
        disclaimers.add(source["meta"]["disclaimer"])

        for node in walk_nodes(source["body"]) + walk_nodes(source["appendices"]):
            bump(node_kinds, node["kind"])
        for block in blocks_of(source):
            bump(block_types, block["type"])
            if block["type"] == "table":
                bump(semantic, block["semantic_type"])
                for grid_row in block["grid"]:
                    totals["table_cells"] += len(grid_row)
                    totals["merged_cells"] += sum(1 for c in grid_row if c.get("merged_into"))
            if block["type"] == "figure":
                bump(figure_kinds, block["diagram"]["kind"])

        totals["pages"] += entry["pages"]
        totals["page_images"] += entry["page_images"]
        totals["chars"] += entry["chars"]
        totals["tables"] += entry["tables"]
        totals["figures"] += entry["figures"]
        totals["refs"] += entry["refs"]
        totals["footnotes"] += entry["footnotes"]
        totals["qa_items"] += entry["qa_items"]
        totals["formulas"] += len(derived["formulas"])
        totals["defined_terms"] += len(source["defined_terms"])
        totals["term_uses"] += len(derived["term_uses"])
        totals["constants"] += len(source["meta"]["constants"])
        totals["enumerations"] += len(derived["enumerations"])
        totals["enumeration_items"] += sum(len(e["items"]) for e in derived["enumerations"])
        totals["toc_entries"] += len(derived["toc"])
        for figure in derived["figures"].values():
            totals["figure_nodes"] += len(figure["graph"]["nodes"])
            totals["figure_edges"] += len(figure["graph"]["edges"])
            totals["figure_paths"] += len(figure["paths"])
        for term in source["defined_terms"]:
            bump(kana, term["index_kana"])

        answer_path = doc_dir / "answer.json"
        if answer_path.is_file():
            answer = json.loads(answer_path.read_text(encoding="utf-8"))
            totals["answer_chars"] += sum(p["chars"] for p in answer["pages"])
        for name in ("elements", "passages"):
            path = doc_dir / f"{name}.jsonl"
            if path.is_file():
                totals[name] += sum(1 for line in path.open(encoding="utf-8") if line.strip())
        qa_path = doc_dir / "qa.json"
        if qa_path.is_file():
            for item in json.loads(qa_path.read_text(encoding="utf-8"))["items"]:
                bump(qa_types, item["type"])
                bump(qa_sources, item["source"])
                bump(qa_answer_types, item["answer_type"])

        meta = source["meta"]
        bump(schemes, meta["numbering_scheme"])
        bump(issuers, {"stock": "株式会社", "mutual": "相互会社"}[meta["issuer"]["kind"]])
        width, height = layout["page_size_pt"]
        bump(
            page_sizes, f"{width:.0f}×{height:.0f} pt（{width * 25.4 / 72:.0f}×{height * 25.4 / 72:.0f} mm）"
        )
        for font in layout["renderer"]["fonts"]:
            bump(registered, font)
        for page in layout["pages"]:
            bump(columns, f"{page['columns']} 段")
            for line in page["text_lines"]:
                bump(regions, line["region"])
        pdf_path = doc_dir / "doc.pdf"
        if pdf_path.is_file():
            for font in pdf_fonts_by_chars(pdf_path):
                bump(embedded, font)
        for path in doc_dir.iterdir():
            if path.is_file() and path.name not in ARTIFACT_FILES and not path.name.startswith("."):
                bump(strays, path.name)

        rows.append(
            (
                entry["doc_id"],
                entry["genre"],
                source["meta"]["title"],
                str(entry["seed"]),
                str(entry["pages"]),
                f"{entry['chars']:,}",
                str(entry["tables"]),
                str(entry["figures"]),
                str(entry["qa_items"]),
                entry["status"],
            )
        )

    out |= {f"scale.{k}": v for k, v in totals.items()}
    out["scale.documents"] = len(entries)
    out["scale.ready"] = sum(1 for d in entries if d["status"] == "ready")
    out["scale.failed"] = sum(1 for d in entries if d["status"] != "ready")
    out["scale.contents"] = len(contents)
    out["scale.genres"] = len(genres)
    out["scale.styles"] = len(styles)
    out["disclaimers"] = len(disclaimers)
    out["dist.node_kinds"] = node_kinds
    out["dist.block_types"] = block_types
    out["dist.semantic_types"] = semantic
    out["dist.figure_kinds"] = figure_kinds
    out["dist.qa_types"] = qa_types
    out["dist.qa_sources"] = qa_sources
    out["dist.qa_answer_types"] = qa_answer_types
    out["dist.numbering_schemes"] = schemes
    out["dist.issuer_kinds"] = issuers
    out["dist.columns"] = columns
    out["dist.regions"] = regions
    out["dist.embedded_fonts"] = embedded
    out["dist.registered_fonts"] = registered
    out["dist.page_sizes"] = page_sizes
    out["dist.term_kana"] = kana
    out["dist.strays"] = strays
    out["rows"] = rows

    search_dir = dataset_dir / "search"
    for name in ("passages", "queries", "qrels"):
        path = search_dir / f"{name}.jsonl"
        out[f"search.{name}"] = (
            sum(1 for line in path.open(encoding="utf-8") if line.strip()) if path.is_file() else 0
        )
    sizes: dict[str, list[int]] = {}
    for path in dataset_dir.rglob("*"):
        if not path.is_file() or path.name.startswith(".") or path.name == "data-card.md":
            continue
        ext = path.suffix.lstrip(".") or "(拡張子なし)"
        got = sizes.setdefault(ext, [0, 0])
        got[0] += 1
        got[1] += path.stat().st_size
    out["sizes"] = sizes
    return out


# --- カードの Markdown から読み戻す -------------------------------------------


def card_tables(card: str) -> list[list[list[str]]]:
    """Markdown の表を「行の配列」の配列として取り出す。"""
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for line in card.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= {"-"}:
                continue
            current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def find_pairs(tables: list[list[list[str]]], header: str) -> dict[str, str]:
    """見出しが `header` で始まる 2 列の表を「名前 → 値」にする。"""
    for table in tables:
        if table and table[0] and table[0][0].startswith(header):
            return {row[0]: row[1] for row in table[1:] if len(row) >= 2}
    return {}


def unquote(name: str) -> str:
    return name.strip("`")


def num(text: str) -> int:
    match = re.search(r"-?[\d,]+", text)
    return int(match.group().replace(",", "")) if match else -1


# --- 突合 ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("dataset"))
    args = parser.parse_args()
    dataset_dir: Path = args.dataset
    card_path = dataset_dir / "data-card.md"
    if not card_path.is_file():
        print(f"✗ {card_path} が無い（`uv run yakkan datacard update` を実行する）")
        return 2

    print(f"別経路で再計算する（PDF の全文字を走査するので時間がかかる）… {dataset_dir}")
    truth = recompute(dataset_dir)
    card = card_path.read_text(encoding="utf-8")
    tables = card_tables(card)
    problems: list[str] = []
    checked = 0

    def compare(label: str, expected: object, actual: object) -> None:
        nonlocal checked
        checked += 1
        if expected != actual:
            problems.append(f"{label}: 再計算 {expected!r} ≠ カード {actual!r}")

    # --- §3 規模（スカラ） ----------------------------------------------------
    scale = find_pairs(tables, "項目")
    scalars = {
        "文書（PDF）": "scale.documents",
        "content（執筆物）": "scale.contents",
        "genre（ジャンル）": "scale.genres",
        "style（版面）": "scale.styles",
        "ページ": "scale.pages",
        "ページ画像（PNG）": "scale.page_images",
        "本文の文字数（`derived.plain_text`）": "scale.chars",
        "紙面の文字数（`answer.json` のページ本文）": "scale.answer_chars",
        "算式（`formula`）": "scale.formulas",
        "参照（`{ref:}` の解決結果）": "scale.refs",
        "定数（`{const:}` で参照する `meta.constants`）": "scale.constants",
        "脚注（条末）": "scale.footnotes",
        "目次の項目": "scale.toc_entries",
        "QA": "scale.qa_items",
        "要素索引の行（`elements.jsonl`）": "scale.elements",
        "検索パッセージ（全文書の合計）": "scale.passages",
    }
    for label, key in scalars.items():
        if label not in scale:
            problems.append(f"§3 に「{label}」の行が無い")
            continue
        compare(f"§3 {label}", truth[key], num(scale[label]))
    compare("§3 ready", truth["scale.ready"], num(scale["文書（PDF）"].split("ready")[1]))
    compare("§3 failed", truth["scale.failed"], num(scale["文書（PDF）"].split("failed")[1]))
    for label, keys in (
        ("表 / セル / 結合セル", ("scale.tables", "scale.table_cells", "scale.merged_cells")),
        (
            "図 / ノード / 辺 / 経路",
            ("scale.figures", "scale.figure_nodes", "scale.figure_edges", "scale.figure_paths"),
        ),
        ("列挙 / 列挙の項目", ("scale.enumerations", "scale.enumeration_items")),
        ("定義語 / `{term:}` の出現", ("scale.defined_terms", "scale.term_uses")),
    ):
        got = [int(p.replace(",", "")) for p in re.findall(r"[\d,]+", scale.get(label, ""))]
        compare(f"§3 {label}", [truth[k] for k in keys], got)

    # --- §3 容量の内訳 --------------------------------------------------------
    size_rows = find_pairs(tables, "種類")
    sizes: dict[str, list[int]] = truth["sizes"]  # type: ignore[assignment]
    compare("§3 容量の拡張子の数", len(sizes), len(size_rows))
    for ext, (files, _bytes) in sizes.items():
        compare(f"§3 容量 .{ext} のファイル数", files, num(size_rows.get(f"`.{ext}`", "-1")))

    # --- §4.3 文書の全件 ------------------------------------------------------
    doc_table = next((t for t in tables if t and t[0] and t[0][0] == "doc_id"), [])
    card_rows = [tuple(unquote(c) for c in row) for row in doc_table[1:]]
    expected_rows = sorted(truth["rows"], key=lambda r: r[0])  # type: ignore[arg-type]
    compare("§4.3 行数", len(expected_rows), len(card_rows))
    for expected in expected_rows:
        if expected not in card_rows:
            problems.append(f"§4.3 の行が合わない: {expected}")
    checked += len(expected_rows)

    # --- §5・§6 の分布 --------------------------------------------------------
    for label, key, header in (
        ("ノード種別", "dist.node_kinds", "`kind`"),
        ("ブロック種別", "dist.block_types", "`type`"),
        ("表の意味種別", "dist.semantic_types", "`semantic_type`"),
        ("QA 種別", "dist.qa_types", "種別"),
        ("QA の出所", "dist.qa_sources", "`source`"),
        ("QA の答えの型", "dist.qa_answer_types", "`answer_type`"),
        ("番号方式", "dist.numbering_schemes", "`numbering_scheme`"),
        ("発行体", "dist.issuer_kinds", "発行体の種別"),
        ("索引見出し", "dist.term_kana", "索引見出し"),
        ("段組", "dist.columns", "段組"),
        ("region", "dist.regions", "region"),
        ("判型", "dist.page_sizes", "判型"),
        ("埋め込みフォント", "dist.embedded_fonts", "PDF に埋め込まれていたフォント"),
        ("登録フォント", "dist.registered_fonts", "描画に登録したフォント"),
        ("成果物でないファイル", "dist.strays", "ファイル名"),
    ):
        expected_dist: dict[str, int] = truth[key]  # type: ignore[assignment]
        pairs = find_pairs(tables, header)
        got = {unquote(name): num(value) for name, value in pairs.items()}
        compare(f"分布 {label}", expected_dist, got)

    # 図の種別は `kind` 見出しがノード種別と重なるので、節の位置で切り出す
    figure_section = card.split("### 5.4 図の種別", 1)
    if len(figure_section) == 2:
        got = {
            unquote(name): num(value)
            for name, value in find_pairs(card_tables(figure_section[1]), "`kind`").items()
        }
        compare("分布 図の種別", truth["dist.figure_kinds"], got)
    else:
        problems.append("§5.4 図の種別が無い")

    # --- §7 検索評価セット ----------------------------------------------------
    # **節で切り出す。** 「項目」見出しの表は §3 にもあるので、カード全体から
    # 最初の 1 つを拾うと §3 を読んでしまう（実際に読んでいた）
    search_section = card.split("## 7. 検索評価セット", 1)
    search_pairs = find_pairs(card_tables(search_section[1]), "項目") if len(search_section) == 2 else {}
    if not search_pairs:
        problems.append("§7 検索評価セットの表が無い")
    for label, key in (
        ("パッセージ", "search.passages"),
        ("クエリ", "search.queries"),
        ("適合判定（qrels）", "search.qrels"),
    ):
        compare(f"§7 {label}", truth[key], num(search_pairs.get(label, "-1")))

    # --- §9 奥付の断り書き ----------------------------------------------------
    quoted = len([line for line in card.splitlines() if line.startswith("> ")])
    compare("§9 disclaimer の種類", truth["disclaimers"], quoted)

    print(f"\n突合 {checked} 項目")
    if problems:
        print(f"✗ 食い違い {len(problems)} 件")
        for line in problems:
            print(f"  - {line}")
        return 1
    print("✓ すべて一致した（カードの測り方は別経路の再計算と合っている）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
