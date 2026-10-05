"""データカードの数値を、`keiyaku/datacard.py` とは別経路の計算と突き合わせる。

    uv run python scripts/verify_data_card.py

生成器と同じコードを使わない（pydantic モデルを通さず json を生で読む）ことで、
**測り方の思い込み**を検出する。`dataset/data-card.md` に載っているスカラ値・分布の各行・
文書の全件が、独立計算の結果と一致するかを見る。食い違えば終了コード 1。

`keiyaku datacard check`（カードが現在の dataset/ と一致するか）とは別の検査である——
あちらは「生成器をもう一度回した結果と同じか」、こちらは「生成器の測り方が正しいか」を見る。
仕様は `docs/data_card.md`。
"""

import collections
import json
import pathlib
import re
import sys

D = pathlib.Path("dataset")
card = (D / "data-card.md").read_text(encoding="utf-8")
m = json.loads((D / "manifest.json").read_text())
docs = m["documents"]


def walk(nodes):
    for n in nodes:
        yield n
        yield from walk(n.get("children") or [])


def blocks_of(node_blocks):
    for b in node_blocks or []:
        yield b
        yield from blocks_of(b.get("blocks"))


exp = {}
exp["文書"] = len(docs)
exp["ready"] = sum(1 for d in docs if d["status"] == "ready")
exp["content"] = len({d["content_id"] for d in docs})
exp["doctype"] = len({d["doctype"] for d in docs})
exp["style"] = len({d["style_id"] for d in docs})
exp["ページ"] = sum(d["pages"] for d in docs)
exp["PNG"] = sum(d["page_images"] for d in docs)
exp["本文字数"] = sum(d["chars"] for d in docs)
exp["表"] = sum(d["tables"] for d in docs)
exp["図"] = sum(d["figures"] for d in docs)
exp["参照"] = sum(d["refs"] for d in docs)
exp["脚注"] = sum(d["footnotes"] for d in docs)
exp["QA"] = sum(d["qa_items"] for d in docs)

cells = enum = enum_items = terms = consts = party_uses = answer_chars = 0
fnodes = fedges = fpaths = 0
elements = passages = 0
semt = collections.Counter()
figk = collections.Counter()
nodek = collections.Counter()
blockt = collections.Counter()
alias = collections.Counter()
scheme = collections.Counter()
qat = collections.Counter()
qas = collections.Counter()
qaa = collections.Counter()
regions = collections.Counter()
cols = collections.Counter()
for d in docs:
    p = D / d["doc_id"]
    s = json.loads((p / "source.json").read_text())
    der = s["derived"]
    nodes = list(walk(s["body"])) + list(walk(s["appendices"])) + list(walk(s["back_matter"]["signature"]))
    for n in nodes:
        nodek[n["kind"]] += 1
    bl = list(blocks_of([b for n in nodes for b in (n.get("blocks") or [])]))
    bl += list(blocks_of(s["front_matter"].get("preface")))
    bl += list(blocks_of(s["back_matter"].get("colophon")))
    bl += list(blocks_of(s["back_matter"].get("contact")))
    for b in bl:
        blockt[b["type"]] += 1
        if b["type"] == "table":
            semt[b["semantic_type"]] += 1
            cells += sum(len(r) for r in b["grid"])
        if b["type"] == "figure":
            figk[b["diagram"]["kind"]] += 1
    enum += len(der["enumerations"])
    enum_items += sum(len(e["items"]) for e in der["enumerations"])
    terms += len(s["defined_terms"])
    consts += len(s["meta"]["constants"])
    party_uses += len(der["party_uses"])
    for f in der["figures"].values():
        fnodes += len(f["graph"]["nodes"])
        fedges += len(f["graph"]["edges"])
        fpaths += len(f["paths"])
    for pa in s["meta"]["parties"]:
        alias[pa["alias"]] += 1
    scheme[s["meta"]["numbering_scheme"]] += 1
    a = json.loads((p / "answer.json").read_text())
    answer_chars += sum(pg["chars"] for pg in a["pages"])
    elements += sum(1 for _ in (p / "elements.jsonl").open())
    passages += sum(1 for _ in (p / "passages.jsonl").open())
    q = json.loads((p / "qa.json").read_text())
    for it in q["items"]:
        qat[it["type"]] += 1
        qas[it["source"]] += 1
        qaa[it["answer_type"]] += 1
    lay = json.loads((p / "layout.json").read_text())
    for pg in lay["pages"]:
        cols[pg["columns"]] += 1
        for tl in pg["text_lines"]:
            regions[tl["region"]] += 1

exp["セル"] = cells
exp["列挙"] = enum
exp["列挙項目"] = enum_items
exp["定義語"] = terms
exp["定数"] = consts
exp["当事者呼称"] = party_uses
exp["紙面字数"] = answer_chars
exp["図ノード"] = fnodes
exp["図辺"] = fedges
exp["図経路"] = fpaths
exp["elements"] = elements
exp["passages"] = passages

size = collections.Counter()
nfiles = 0
for f in D.rglob("*"):
    if f.is_file() and not f.name.startswith(".") and f.name != "data-card.md":
        size[f.suffix.lstrip(".")] += f.stat().st_size
        nfiles += 1
exp["容量MiB"] = round(sum(size.values()) / 1048576, 1)
exp["ファイル数"] = nfiles

se = D / "search"
sp = [json.loads(line) for line in (se / "passages.jsonl").open()]
sq = [json.loads(line) for line in (se / "queries.jsonl").open()]
sr = [json.loads(line) for line in (se / "qrels.jsonl").open()]
exp["検索パッセージ"] = len(sp)
exp["検索クエリ"] = len(sq)
exp["qrels"] = len(sr)
exp["打ち切り"] = sum(1 for q in sq if q.get("related_truncated"))

# PDF に実際に埋め込まれているフォント（`layout.renderer.fonts` の候補一覧ではない）
import pdfplumber  # noqa: E402

fonts: collections.Counter = collections.Counter()
style_fonts: dict[str, set] = collections.defaultdict(set)
for d in docs:
    with pdfplumber.open(D / d["doc_id"] / "doc.pdf") as pdf:
        used = {c["fontname"].split("+")[-1] for pg in pdf.pages for c in pg.chars}
    for f in used:
        fonts[f] += 1
    style_fonts[d["style_id"]] |= used


def has(label, value):
    """カードの本文に `value`（桁区切りつき）が現れるか。"""
    text = f"{value:,}" if isinstance(value, int) else str(value)
    return text in card


bad = []
for label, value in exp.items():
    if not has(label, value):
        bad.append((label, value))


# 分布の表（名前と件数の対）が 1 行として載っているか
def rows_ok(name, counter, kind):
    missing = []
    for key, n in counter.items():
        if not re.search(rf"\|\s*{re.escape(str(key))}\s*\|\s*{n:,}\s*\|", card):
            missing.append((key, n))
    if missing:
        bad.append((f"{kind}:{name}", missing))


rows_ok("semantic_type", semt, "分布")
rows_ok("figure_kind", figk, "分布")
rows_ok("node_kind", nodek, "分布")
rows_ok("block_type", blockt, "分布")
rows_ok("qa_type", qat, "分布")
rows_ok("qa_source", qas, "分布")
rows_ok("qa_answer_type", qaa, "分布")
rows_ok("region", regions, "分布")
rows_ok("alias", alias, "分布")
rows_ok("numbering", scheme, "分布")
rows_ok("embedded_font", fonts, "分布")

for style, used in style_fonts.items():
    joined = "、".join(sorted(used))
    if joined not in card:
        bad.append(("style のフォント", (style, joined)))

# 文書の全件が載っているか
for d in docs:
    if f"`{d['doc_id']}`" not in card:
        bad.append(("全件表", d["doc_id"]))

print(
    f"独立計算 {len(exp)} 項目 ＋ 分布 11 種 ＋ style のフォント {len(style_fonts)} 件 ＋ 全件 {len(docs)} 行"
)
for label, value in sorted(exp.items()):
    print(f"  {label}: {value}")
if bad:
    print("\n=== カードに見つからない / 一致しない ===")
    for label, value in bad:
        print(" ", label, value)
    sys.exit(1)
print("\nすべてカードの記載と一致した")
