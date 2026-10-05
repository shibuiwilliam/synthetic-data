"""候補選定（決定的な一次スクリーニング）。

方針: 再現率優先。構造シグナル（算式ブロック・表の意味種別・図の分岐・定数参照）と
語彙シグナル（約款特有の計算・限度・条件・期間の言い回し）の和集合で候補を拾い、
LLM による精査（規範性・計算可能性の分類）はこの後段に置く。
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..core.docindex import Doc, Unit, quantities_in

# ---- 語彙シグナル（約款の言い回しの辞書）。運用では誤検出・見逃しの実績から育てる。
LEXICON: dict[str, list[str]] = {
    "ARITH": [
        r"乗じ",
        r"差し引",
        r"控除",
        r"合計額",
        r"合算",
        r"按分",
        r"割合に応じ",
        r"に加えて",
        r"相当する額",
        r"\d+割",
        r"算式",
        r"算定し",
        r"算出",
        r"計算し",
        r"日額",
        r"を基礎として",
        r"現価",
        r"利率",
        r"割り振",
        r"の額から",
    ],
    "BOUND": [
        r"限度",
        r"を超え",
        r"上回",
        r"下回",
        r"未満",
        r"以上",
        r"以下",
        r"満たない",
        r"いずれか早い",
        r"最も遅い",
        r"額の高い",
        r"割合の高い",
        r"重い障害",
    ],
    "COND": [
        r"場合(?:に|は|も|で|、)",
        r"とき(?:は|に|も|、)",
        r"ただし",
        r"この限りではありません",
        r"に限り",
        r"にかぎり",
        r"を除き",
        r"にかかわらず",
        r"該当",
    ],
    "TEMPORAL": [
        r"\d+(?:営業日|日|か月|年)(?:以内|を経過|を超えて|間|後|前)",
        r"翌日から起算",
        r"その日を含めて",
        r"経過した",
        r"初日",
        r"末日",
        r"属する月",
        r"満了",
        r"午後\d+時",
        r"\d+歳",
    ],
    "EFFECT": [
        r"支払います",
        r"支払いません",
        r"解除することができます",
        r"免除します",
        r"効力を失",
        r"消滅します",
        r"適用しません",
        r"行いません",
        r"返還します",
        r"取り扱いません",
        r"含みません",
        r"とみなし",
        r"更新するものとします",
        r"取り消すことができます",
    ],
    "OVERRIDE": [
        r"準用",
        r"読み替え",
        r"にかかわらず",
        r"別の定め",
        r"特約に.{0,12}定め",
        r"保険証券に.{0,14}記載",
        r"優先します",
        r"適用しません",
    ],
    "DISCRETION": [
        r"当会社が.{0,20}認め",
        r"会社が.{0,20}認め",
        r"相当と認め",
        r"別に定め",
        r"当会社所定",
        r"会社所定",
        r"会社が定め",
        r"当会社が定め",
        r"社会通念上",
        r"正当な理由",
        r"やむを得ない",
        r"会社の指定する",
    ],
}
_LEX = {k: [re.compile(p) for p in v] for k, v in LEXICON.items()}

COMPUTATIONAL_TABLES = {"benefit_schedule", "grade_schedule", "rate", "surgery_schedule"}
DECISION_TABLES = {"exclusions", "enumeration"}


@dataclass
class Candidate:
    unit: Unit
    signals: set[str] = field(default_factory=set)
    kinds: set[str] = field(default_factory=set)
    normative: bool = True
    quantities: list[str] = field(default_factory=list)


def _is_explanatory(doc: Doc, u: Unit) -> bool:
    """しおり・囲み・図・前付けは「説明」。規範（約款本文）ではなく照合・テスト例に使う。"""
    if u.zone in ("front", "back"):
        return True
    if u.extra.get("in_box") or u.utype in ("figure", "box_title", "formula_alt", "caption", "cover_note"):
        return True
    cur = u.owner
    while cur is not None:
        n = doc.nodes[cur]
        if n["kind"] == "part" and "しおり" in (n.get("title") or ""):
            return True
        cur = doc.parent.get(cur)
    return False


LOOKUP_TABLES = {"grade_schedule", "rate", "surgery_schedule"}  # 表全体で1つの参照表
ROW_TABLES = {"benefit_schedule", "exclusions", "enumeration"}  # 1行（1号）が1つの規定


def logical_units(doc: Doc) -> list[Unit]:
    """候補判定の単位。表は意味種別に応じて「表全体」または「行」にまとめる。

    用語定義表は defined_terms と重複するため除外する。
    """
    out: list[Unit] = []
    for u in doc.units.values():
        if u.utype in ("caption", "box_title", "formula_alt", "cover_note"):
            continue
        if u.utype in ("cell", "table_note") and u.block in doc.blocks:
            sem = doc.blocks[u.block].get("semantic_type")
            if sem in LOOKUP_TABLES | ROW_TABLES | {"definitions"}:
                continue  # 下で表・行としてまとめ直す
            if u.utype == "cell" and u.extra.get("role") == "header":
                continue
        out.append(u)
    for bid, b in doc.blocks.items():
        if b["type"] != "table":
            continue
        sem = b.get("semantic_type")
        owner = doc.block_owner.get(bid)
        zone = doc.nodes[owner]["_zone"] if owner else "front"
        hdr = b["layout"].get("header_rows", 0)
        notes = [doc.units[f"{bid}__note{i}"] for i in range(len(b.get("notes") or []))]
        if sem in LOOKUP_TABLES:
            cells = [doc.units[c["id"]] for row in b["grid"] for c in row if c.get("id") in doc.units]
            parts = cells + notes
            out.append(
                Unit(
                    bid,
                    "lookup_table",
                    " | ".join(x.raw for x in parts),
                    " | ".join(x.text for x in parts),
                    owner,
                    bid,
                    zone,
                    {"members": [x.id for x in parts], "sem": sem},
                )
            )
        elif sem in ROW_TABLES:
            for r, row in enumerate(b["grid"][hdr:], start=hdr):
                cells = [doc.units[c["id"]] for c in row if c.get("id") in doc.units]
                if not cells:
                    continue
                out.append(
                    Unit(
                        f"{bid}__r{r}",
                        "table_row",
                        " | ".join(x.raw for x in cells),
                        " | ".join(x.text for x in cells),
                        owner,
                        bid,
                        zone,
                        {"members": [x.id for x in cells], "sem": sem},
                    )
                )
            for n in notes:
                out.append(Unit(n.id, "table_note", n.raw, n.text, owner, bid, zone, {"sem": sem}))
    return out


# 数値を含まない「金額の定義文」（例: 損害の額は…価額とします）。初版の語彙では見逃していた型。
_AMOUNT_DEF = re.compile(r"額は、|額とします|額を.{0,14}とします|額から|額に.{0,10}含め")


def detect(doc: Doc, lexicon: str = "v2") -> list[Candidate]:
    """lexicon="v1" は初版（計算候補に数値の併存を要求）。比較のために残している。"""
    out: list[Candidate] = []
    for u in logical_units(doc):
        sig: set[str] = set()
        for name, pats in _LEX.items():
            if any(p.search(u.text) for p in pats):
                sig.add(name)
        if "{const:" in u.raw:
            sig.add("S_CONST")
        qty = quantities_in(u.text)
        if qty:
            sig.add("S_QTY")
        if u.utype == "formula":
            sig.add("S_FORMULA")
        table_sem = None
        if u.block and u.block in doc.blocks:
            b = doc.blocks[u.block]
            if b["type"] == "table":
                table_sem = b.get("semantic_type")
                if table_sem in COMPUTATIONAL_TABLES | DECISION_TABLES:
                    sig.add(f"S_TABLE:{table_sem}")
            if b["type"] == "figure":
                dia = b.get("diagram", {})
                if any(n.get("shape") == "decision" for n in dia.get("nodes", [])):
                    sig.add("S_FIG_DECISION")
                if dia.get("kind") == "timeline":
                    sig.add("S_FIG_TIMELINE")

        kinds: set[str] = set()
        has_num = "S_QTY" in sig or "S_CONST" in sig
        if (
            "S_FORMULA" in sig
            or ("ARITH" in sig and has_num)
            or (table_sem in COMPUTATIONAL_TABLES and has_num)
            or lexicon != "v1"
            and (
                "ARITH" in sig
                or _AMOUNT_DEF.search(u.text)
                or (table_sem == "benefit_schedule" and u.utype == "table_row")
            )
        ):
            kinds.add("calculation")
        if u.utype == "lookup_table":
            kinds.add("table_lookup")
        if "BOUND" in sig and has_num:
            kinds.add("limit")
        if "TEMPORAL" in sig and has_num:
            kinds.add("temporal")
        if ("COND" in sig and "EFFECT" in sig) or (table_sem in DECISION_TABLES and u.utype == "table_row"):
            kinds.add("decision")
        if "OVERRIDE" in sig:
            kinds.add("override")
        if "S_FIG_DECISION" in sig or "S_FIG_TIMELINE" in sig:
            kinds.add("flow")
        if u.utype == "term" and (has_num or "BOUND" in sig or "COND" in sig):
            kinds.add("definition")
        if not kinds:
            continue
        out.append(Candidate(u, sig, kinds, not _is_explanatory(doc, u), qty))
    return out


def clusters(doc: Doc, cands: list[Candidate]) -> dict[str, list[Candidate]]:
    """候補を条（article）単位に束ねる。抽出の単位は文ではなく「条＋参照先」。"""
    groups: dict[str, list[Candidate]] = defaultdict(list)
    for c in cands:
        key = doc.article_of(c.unit.owner) if c.unit.owner else f"<{c.unit.zone}>"
        groups[key or f"<{c.unit.zone}>"].append(c)
    return groups


def context_pack(doc: Doc, article_id: str, depth: int = 1) -> dict:
    """ある条をLLMに渡すときの文脈を決定的に組み立てる。

    条そのものに加え、参照先（{ref:}）、使用する定義語（{term:}）、
    その条を参照している他の条（特約による上書きなど）を集める。
    """

    def units_under(node_id: str) -> list[str]:
        ids = []
        for u in doc.units.values():
            cur = u.owner
            while cur is not None:
                if cur == node_id:
                    ids.append(u.id)
                    break
                cur = doc.parent.get(cur)
        return ids

    core = units_under(article_id)
    refs_out, terms, consts = set(), set(), set()
    frontier = list(core)
    for _ in range(depth):
        nxt = []
        for uid in frontier:
            for target in doc.placeholders(uid, "ref"):
                if target not in refs_out:
                    refs_out.add(target)
                    nxt.extend(units_under(target) if target in doc.nodes else [])
            terms.update(doc.placeholders(uid, "term"))
            consts.update(doc.placeholders(uid, "const"))
        frontier = nxt
    core_nodes = {article_id} | {n for n in doc.nodes if _is_descendant(doc, n, article_id)}
    refs_in = set()
    for u in doc.units.values():
        if u.id in core:
            continue
        if any(t in core_nodes for t in doc.placeholders(u.id, "ref")):
            refs_in.add(doc.article_of(u.owner) or u.id)
    ref_units = [x for t in refs_out if t in doc.nodes for x in units_under(t)]
    chars = sum(len(doc.units[i].text) for i in set(core) | set(ref_units)) + sum(
        len(doc.terms[t]["definition"]) for t in terms if t in doc.terms
    )
    return {
        "article": article_id,
        "citation": doc.citation(article_id),
        "core_units": core,
        "refs_out": sorted(refs_out),
        "refs_in": sorted(refs_in),
        "terms": sorted(terms),
        "consts": sorted(consts),
        "chars": chars,
    }


def _is_descendant(doc: Doc, node_id: str, ancestor: str) -> bool:
    cur = doc.parent.get(node_id)
    while cur is not None:
        if cur == ancestor:
            return True
        cur = doc.parent.get(cur)
    return False


def summarize(doc: Doc) -> dict:
    cands = detect(doc)
    norm = [c for c in cands if c.normative]
    by_kind = Counter(k for c in norm for k in c.kinds)
    by_place = Counter()
    for c in norm:
        if c.unit.utype == "formula":
            by_place["算式ブロック"] += 1
        elif c.unit.utype == "lookup_table":
            by_place["参照表（表全体）"] += 1
        elif c.unit.utype in ("cell", "table_note", "table_row"):
            by_place["表の行・注記"] += 1
        elif c.unit.utype == "footnote":
            by_place["脚注"] += 1
        elif c.unit.utype == "term":
            by_place["用語定義"] += 1
        else:
            by_place["本文（条・項・号）"] += 1
    expl = [c for c in cands if not c.normative]
    groups = clusters(doc, norm)
    return {
        "content_id": doc.content_id,
        "units": len(doc.units),
        "logical_units": len(logical_units(doc)),
        "candidates_normative": len(norm),
        "candidates_explanatory": len(expl),
        "by_kind": dict(by_kind),
        "by_place": dict(by_place),
        "clusters": len(groups),
        "discretion_units": sum(1 for c in norm if "DISCRETION" in c.signals),
        "calc_or_limit_units": sum(1 for c in norm if c.kinds & {"calculation", "limit"}),
        "formula_blocks": sum(1 for b in doc.blocks.values() if b["type"] == "formula"),
    }


def render_context_pack(doc: Doc, article_id: str) -> str:
    """LLM に渡す文脈パックの本文。各行の先頭に単位IDを付け、根拠の引用元を指せるようにする。"""
    pack = context_pack(doc, article_id)
    out = [
        f"# 対象: {pack['citation']} {doc.nodes[article_id].get('title') or ''}".rstrip(),
        "",
        "## 対象の条（本文・表・算式・脚注・囲み）",
    ]
    for uid in pack["core_units"]:
        u = doc.units[uid]
        out.append(f"[{uid}] ({u.utype}) {u.text}")
    out += ["", "## 参照先の規定"]
    for target in pack["refs_out"]:
        if target in doc.nodes:
            for u in doc.units.values():
                cur = u.owner
                while cur is not None:
                    if cur == target and u.id not in pack["core_units"]:
                        out.append(f"[{u.id}] <{doc.citation(u.id)}> {u.text}")
                        break
                    cur = doc.parent.get(cur)
    out += ["", "## この条を参照している規定（特約による上書きの候補）"]
    out += [f"- {doc.citation(a)}" for a in pack["refs_in"]]
    out += ["", "## 用語の定義"]
    out += [
        f"[term_{t}] {doc.terms[t]['term']}: {doc.units['term_' + t].text}"
        for t in pack["terms"]
        if t in doc.terms
    ]
    out += ["", "## 使える定数（値は文書側で管理。IRにはキーだけを書く）"]
    out += [f"- {c} = {doc.constants[c]}" for c in pack["consts"] if c in doc.constants]
    return "\n".join(out) + "\n"
