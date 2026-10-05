"""手順（steps）→ 約款の文・算式・表・図・囲み。

1 つの手順が、1 つの文・表の 1 行・図の 1 ノードのどれかになる（DESIGN.md §8.1）。
手順名は生成する Python の変数名と同じなので、文とコードが 1 対 1 で対応する。

役割（`StepDraft.role`）の扱い:

| role | 展開 |
|---|---|
| `core` | 体言に積む（「…から…を差し引いた額」）。最後に「…の額は、…とします。」の文になる |
| `qualify` | 直前の額に対する但し書き（限度・端数・下限0）。同じ項か次の項に置く |
| `sentence` | それ自身で 1 文（場合分け・期限） |
| `decide` | 判定。図または号の表に出す |
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

from ..core import numbers_ja as nj
from ..patterns.base import ConstDraft, RuleDraft, StepDraft, TableDraft
from ..planning.context import Context
from ..spec.ops import CMP
from . import blocks as bk
from . import figures as fg
from . import lexicon_ja as lex

#: 算式ブロックにできる手順の形
FORMULA_SHAPES = ("sub", "sum", "mul", "table_rate", "proration")

#: 但し書きの手順に付ける日本語の名前（生成コードの変数名の対訳になる）
QUALIFY_LABELS = {
    "policy_limit": "保険証券の限度額を適用した額",
    "round_unspecified": "端数処理をした額",
    "cap": "限度額を適用した額",
    "floor_zero": "0円を下限とした額",
    "round": "端数処理をした額",
    "out_of_range": "表に定めのない場合を除いた額",
    "default": "記載がないときの値を補った額",
    "min": "限度額を適用した額",
}


@dataclass
class Realized:
    """1 つの条の実現結果。"""

    article: dict
    patch_ops: list[dict] = field(default_factory=list)
    spec_rules: list[dict] = field(default_factory=list)
    spec_params: dict[str, dict] = field(default_factory=dict)
    spec_tables: dict[str, dict] = field(default_factory=dict)
    answer: list[dict] = field(default_factory=list)
    #: 設例に必要な入力（2 パス目で値を埋める）
    example_requests: list[dict] = field(default_factory=list)
    #: 別表に出す表（`appendix` 配置のとき）。条の中には置かない
    appendix_table: dict | None = None
    #: 但し書きを分けて置く条（`proviso == "article"` のとき）。本文の条の次に並べる
    proviso_article: dict | None = None


@dataclass
class _Para:
    pid: str
    sentences: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)
    blocks: list[dict] = field(default_factory=list)

    def text(self) -> str:
        return "".join(s for s, _ in self.sentences)


def infer_shape(e: dict) -> str:
    """手順の形を式から推す（パターンが `hint["shape"]` で上書きできる）。"""
    if "op" not in e:
        return "identity"
    o = e["op"]
    if o == "sub":
        return "sub"
    if o == "add":
        return "sum"
    if o == "mul":
        return "mul"
    if o == "muldiv":
        return "table_rate" if e["args"][1].get("op") == "lookup" else "proration"
    if o == "round_to":
        return "round"
    if o == "min":
        return "cap" if any("param" in a for a in e["args"]) else "min"
    if o == "max":
        return "floor_zero" if any(a.get("lit") == 0 for a in e["args"]) else "max"
    if o == "lookup":
        return "lookup"
    if o == "if":
        return "case"
    if o in CMP or o in ("and", "or", "not"):
        return "decision"
    if o == "add_days":
        return "deadline"
    if o == "add_months":
        return "deadline"
    if o == "days_between":
        return "elapsed"
    if o == "end_of_month":
        return "month_end"
    if o == "coalesce":
        return "default"
    if o == "agg":
        return "aggregate"
    return "identity"


class _Pen:
    """1 ルール分の文を書く筆。体言の積み上げと文の並びを持つ。"""

    def __init__(self, ctx: Context, draft: RuleDraft, rng: random.Random, aid: str):
        self.ctx = ctx
        self.d = draft
        self.rng = rng
        self.aid = aid
        self.phrases: dict[str, str] = {}
        self.labels: dict[str, str] = {}
        self.sources: list[dict] = []
        self.satisfied: set[str] = set()
        self.table_id: str | None = None
        #: 表の在りか（「下表」または `{ref:別表}`）。文型がこれを使う
        self.table_where: str = "下表"
        #: 配置（article / appendix / rider）。正解表と仕様に残す
        self.placement_kind: str = "article"
        self.figure_id: str | None = None
        self.formula_id: str | None = None
        self.units: list[str] = []
        #: 条末脚注（番号, 本文）。本文には `{fn:n}` の印を付ける
        self.footnotes: list[tuple[int, str]] = []
        #: 「…の額は、…とします。」を出した文の位置（脚注の印はここに付ける）
        self.main_sentence: int | None = None

    # ---- 体言 ----
    def operand(self, e: dict) -> str:
        if "var" in e:
            return self.d.inputs[e["var"]]["desc"]
        if "param" in e:
            return f"{{const:{e['param']}}}"
        if "step" in e:
            return self.phrases.get(e["step"], self.labels.get(e["step"], ""))
        if "rule" in e:
            return self.d.vocab.get("decision_phrase", "前項の判定")
        if "lit" in e:
            v = e["lit"]
            if v == 0:
                return "0円" if self.d.output.get("unit") == "JPY" else "0"
            unit = e.get("unit") or self.d.output.get("unit") or "1"
            return nj.surface(int(v), unit) if isinstance(v, int) else str(v)
        if "item" in e:
            return self.d.vocab.get("item_phrase", "明細の額")
        return ""

    def operands(self, e: dict) -> list[str]:
        return [self.operand(a) for a in e.get("args", [])]


def _phrase_for(pen: _Pen, step: StepDraft, shape: str) -> str:
    e, rng, h = step.expr, pen.rng, step.hint
    a = pen.operands(e)
    if shape == "sub":
        return lex.phrase_sub(a[0], a[1], rng)
    if shape == "sum":
        return lex.phrase_sum(a, rng)
    if shape == "mul":
        return lex.phrase_mul(a[0], a[1], rng)
    if shape == "table_rate":
        return lex.phrase_table_rate(a[0], h["key_phrase"], h["rate_name"], rng, where=pen.table_where)
    if shape == "proration":
        return lex.phrase_proration(a[0], a[1], a[2], rng)
    if shape == "lookup":
        return lex.phrase_lookup(h["key_phrase"], h["value_name"], rng, where=pen.table_where)
    if shape == "limited":
        return lex.phrase_limited(a[0], a[1], rng)
    if shape == "min":
        return lex.phrase_min(a, rng)
    if shape == "max":
        return lex.phrase_max(a, rng)
    if shape == "deadline":
        return lex.phrase_deadline(a[0], a[1], rng)
    if shape == "elapsed":
        return lex.phrase_elapsed(a[0], a[1], rng)
    if shape == "aggregate":
        inner = e["args"][0]
        per_item = next((pen.operand(x) for x in inner.get("args", []) if "param" in x), None)
        item = h.get("item_phrase", "額")
        return lex.phrase_aggregate(lex.phrase_limited(item, per_item, rng) if per_item else item, rng)
    if shape == "ceil_period":
        return h.get("phrase") or pen.operand(e["args"][0])
    if shape == "identity":
        return pen.operand(e)
    if shape in ("cap", "floor_zero", "round", "case", "default", "out_of_range"):
        # 但し書きは体言を変えない（直前の額を指す）
        inner = e["args"][0] if shape != "cap" else e["args"][0]
        return pen.operand(inner)
    return pen.operand(e)


def _formula_terms(pen: _Pen, step: StepDraft, shape: str) -> list[tuple[str, Any]] | None:
    """算式ブロックにできる形だけ項を返す。括弧と複数行は使えない。"""
    a = pen.operands(step.expr)
    result = f"{pen.d.benefit}の額"
    if shape == "sub":
        return [("box", a[0]), ("op", "－"), ("box", a[1]), ("op", "＝"), ("box", result)]
    if shape == "sum" and len(a) == 2:
        return [("box", a[0]), ("op", "＋"), ("box", a[1]), ("op", "＝"), ("box", result)]
    if shape == "mul":
        return [("box", a[0]), ("op", "×"), ("box", a[1]), ("op", "＝"), ("box", result)]
    if shape == "table_rate":
        return [
            ("box", a[0]),
            ("op", "×"),
            ("box", step.hint["rate_name"]),
            ("op", "＝"),
            ("box", result),
        ]
    if shape == "proration":
        return [
            ("box", a[0]),
            ("op", "×"),
            ("fraction", (a[1], a[2])),
            ("op", "＝"),
            ("box", result),
        ]
    return None


# --------------------------------------------------------------------- 実現
def realize(
    ctx: Context,
    drafts: list[RuleDraft],
    aid: str,
    rng: random.Random,
    *,
    example_values: dict[str, list] | None = None,
    modalities: dict[str, list[str]] | None = None,
    placement=None,
) -> Realized:
    """1 つの条にまとめて書く（同じ `group` のルール群）。

    `example_values` は 2 パス目で渡す。1 パス目（`None`）では設例の囲みを作らない。
    `placement` を渡すと、参照表を別表に分けたり、条を特約の中に置いたりする（DESIGN.md §8.5）。
    """
    modalities = modalities or {}
    paras: list[_Para] = []
    article_blocks: list[dict] = []
    out = Realized(article={})
    title = drafts[0].vocab.get("article_title") or drafts[0].benefit

    for draft in drafts:
        pen = _Pen(ctx, draft, rng, aid)
        if placement is not None:
            pen.table_where = placement.table_where
            pen.placement_kind = placement.kind
        _write_rule(ctx, pen, draft, paras, article_blocks, rng, modalities, example_values, out, placement)

    children = [bk.node(p.pid, "paragraph", text=p.text(), blocks=p.blocks or None) for p in paras]
    out.article = bk.node(aid, "article", title=title, blocks=article_blocks or None, children=children)
    _self_check(out.article)
    if out.proviso_article is not None:
        _self_check(out.proviso_article)
    return out


def _self_check(article: dict) -> None:
    """組み上げた条の自己点検。本体 lint に投げる前に、作り方の誤りをここで止める。

    - 条の中のブロックIDが重複していないか（本体 lint L01）
    - `{fn:n}` と条末脚注が双方向に対応しているか（本体 lint L02）
    """
    ids: list[str] = []
    notes: set[int] = set()

    def walk(blocks: list[dict]) -> None:
        for b in blocks or []:
            if b.get("id"):
                ids.append(b["id"])
            if b["type"] == "footnotes":
                notes.update(n["n"] for n in b["notes"])
            walk(b.get("blocks") or [])

    walk(article.get("blocks") or [])
    texts = [article.get("text") or ""]
    for child in article.get("children") or []:
        walk(child.get("blocks") or [])
        texts.append(child.get("text") or "")
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"{article['id']}: ブロックIDが重複している {dup}")
    used = {int(m) for text in texts for m in re.findall(r"\{fn:(\d+)\}", text)}
    if used - notes:
        raise ValueError(f"{article['id']}: 本文の脚注の印に対応する脚注が無い {sorted(used - notes)}")
    if notes - used:
        raise ValueError(f"{article['id']}: 本文から参照されていない脚注がある {sorted(notes - used)}")


def _new_para(paras: list[_Para], aid: str) -> _Para:
    p = _Para(f"{aid}_p{len(paras) + 1}")
    paras.append(p)
    return p


def _write_rule(
    ctx: Context,
    pen: _Pen,
    draft: RuleDraft,
    paras: list[_Para],
    article_blocks: list[dict],
    rng: random.Random,
    modalities: dict[str, list[str]],
    example_values: dict[str, list] | None,
    out: Realized,
    placement=None,
) -> None:
    aid = pen.aid
    # ---- 定数 ----
    for c in draft.consts:
        out.patch_ops.append({"op": "add_constant", "key": c.name, "value": c.surface})

    # ---- 判定（図・号） ----
    decide_steps = [s for s in draft.steps if s.role == "decide"]
    if decide_steps and draft.enumeration is not None:
        para = _new_para(paras, aid)
        s = lex.sentence_enumeration(draft.enumeration.mode, draft.benefit, rng)
        para.sentences.append((s.text, s.satisfies))
        pen.sources.append({"unit": para.pid, "raw": s.text})
        pen.satisfied.update(s.satisfies)
        pen.units.append(para.pid)
        tid = f"tbl_{aid}_items"
        para.blocks.append(
            bk.table(
                tid,
                draft.enumeration.semantic_type,
                [draft.enumeration.header or " ", draft.vocab.get("enum_value_header", "取扱い")],
                [[x, draft.vocab.get("enum_value", "支払いません")] for x in draft.enumeration.items],
                align_body="left",
            )
            if draft.enumeration.semantic_type == "exclusions"
            else bk.table(
                tid,
                draft.enumeration.semantic_type,
                [draft.enumeration.header or " "],
                [[x] for x in draft.enumeration.items],
                align_body="left",
            )
        )
        for i in range(len(draft.enumeration.items)):
            pen.sources.append({"unit": f"{tid}__r{i + 1}c0", "raw": draft.enumeration.items[i]})
        pen.units.append(tid)
        pen.table_id = tid
    elif decide_steps and draft.figure is not None:
        para = _new_para(paras, aid)
        fid = f"fig_{aid}_{draft.figure.kind}"
        pen.figure_id = fid
        what = draft.vocab.get("decision_what") or f"{draft.benefit}を支払うかどうか"
        s = lex.sentence_figure_pointer(what, rng)
        para.sentences.append((s.text, s.satisfies))
        pen.sources.append({"unit": para.pid, "raw": s.text})
        pen.units.append(para.pid)
        if draft.figure.kind == "flowchart":
            para.blocks.append(fg.flowchart(fid, draft.figure.spec))
            for i, d in enumerate(draft.figure.spec.decisions, start=1):
                pen.sources.append({"unit": f"{fid}__n{i}", "raw": d.question})
            pen.units.append(fid)
        elif draft.figure.kind == "timeline":
            para.blocks.append(fg.timeline(fid, draft.figure.spec))
            pen.units.append(fid)
            pen.sources.append({"unit": f"{fid}__alt"})
        elif draft.figure.kind == "matrix":
            para.blocks.append(fg.matrix(fid, draft.figure.spec))
            pen.units.append(fid)
            pen.sources.append({"unit": f"{fid}__alt"})
    elif draft.trigger:
        para = _new_para(paras, aid)
        s = _trigger_sentence(ctx, draft, rng)
        para.sentences.append((s, ()))
        pen.sources.append({"unit": para.pid, "raw": s})

    # ---- 本体（core → 体言、qualify → 但し書き） ----
    main = _new_para(paras, aid) if not (decide_steps and draft.kind == "decision") else paras[-1]
    state = {"emitted": False}
    cur = {"phrase": ""}
    after_main: list[lex.Rendered] = []
    deferred: list[tuple[StepDraft, str]] = []

    def put(para: _Para, s: lex.Rendered) -> None:
        para.sentences.append((s.text, s.satisfies))
        pen.sources.append({"unit": para.pid, "raw": s.text})
        pen.satisfied.update(s.satisfies)

    def emit_main() -> None:
        """「…の額は、…とします。」を 1 度だけ出し、続けて数え方の但し書きを置く。

        金額を出さない規定（判定）には書かない。判定の手順が作った体言は、
        文の中で使われるだけで、それ自体が「…の額」になることはない。
        """
        if state["emitted"] or not cur["phrase"] or draft.kind != "calculation":
            return
        put(main, lex.sentence_amount(draft.benefit, cur["phrase"], rng))
        pen.main_sentence = len(main.sentences) - 1
        state["emitted"] = True
        while after_main:
            put(main, after_main.pop(0))

    for step in draft.steps:
        shape = step.hint.get("shape") or infer_shape(step.expr)
        pen.labels[step.name] = step.hint.get("label") or ""
        if step.role == "silent":
            # 文を出さない手順。体言は hint で指定できる（ほかの文から呼ぶときの呼び方）
            pen.phrases[step.name] = step.hint.get("phrase") or cur["phrase"]
            pen.labels[step.name] = step.hint.get("label") or pen.phrases[step.name]
            continue
        if step.role == "decide":
            pen.phrases[step.name] = draft.vocab.get("decision_phrase", "")
            pen.labels[step.name] = step.hint.get("label") or draft.vocab.get("decision_what", step.name)
            continue
        if step.role == "core":
            cur["phrase"] = _phrase_for(pen, step, shape)
            pen.phrases[step.name] = cur["phrase"]
            pen.labels[step.name] = step.hint.get("label") or cur["phrase"]
            if shape == "ceil_period":
                after_main.append(lex.sentence_ceil_period(step.hint["unit_word"], rng))
            continue
        if step.role == "sentence":
            if shape != "case":
                emit_main()
            s = _sentence_step(pen, step, shape, rng)
            put(main, s)
            phrase = step.hint.get("subject_phrase") or cur["phrase"] or draft.title
            pen.phrases[step.name] = phrase
            pen.labels[step.name] = step.hint.get("label") or phrase
            if shape == "case":
                state["emitted"] = True
                while after_main:
                    put(main, after_main.pop(0))
            continue
        # qualify
        pen.phrases[step.name] = cur["phrase"]
        pen.labels[step.name] = step.hint.get("label") or QUALIFY_LABELS.get(shape) or cur["phrase"]
        if step.hint.get("own_paragraph"):
            deferred.append((step, shape))
            continue
        emit_main()
        put(main, _qualify_sentence(pen, step, shape, rng, subject="この額"))

    emit_main()
    for s in after_main:
        put(main, s)
    if draft.kind != "calculation":
        after_main.clear()
    if main.pid not in pen.units:
        pen.units.append(main.pid)

    # ---- 表（本文の中か、別表に分けるか） ----
    if draft.table is not None:
        in_appendix = placement is not None and placement.kind == "appendix"
        host = placement.appendix_id if in_appendix else aid
        tid = f"tbl_{host}_{draft.table.name.split('_')[-1]}"
        pen.table_id = tid
        # 本体の文がすでに表の在りかに触れているなら、重ねて案内しない
        if pen.table_where not in main.text():
            put(main, lex.sentence_table_pointer(draft.table.value_header, rng, where=pen.table_where))
        block = _table_block(tid, draft.table)
        if in_appendix:
            out.appendix_table = block
        else:
            main.blocks.append(block)
        pen.units.append(tid)
        pen.sources.append(_table_source(tid, draft.table))
        out.spec_tables[draft.table.name] = _table_spec(tid, draft.table)

    # ---- 説明の図（判定の図でないもの。本文が規範で、図は照合に使える） ----
    if draft.figure is not None and not decide_steps:
        fid = f"fig_{aid}_{draft.figure.kind}"
        pen.figure_id = fid
        block = {
            "flowchart": fg.flowchart,
            "timeline": fg.timeline,
            "matrix": fg.matrix,
        }[draft.figure.kind](fid, draft.figure.spec)
        main.blocks.append(block)
        pen.units.append(fid)
        pen.sources.append({"unit": f"{fid}__alt"})

    # ---- 算式 ----
    formula_step = next(
        (
            s
            for s in draft.steps
            if "formula" in modalities.get(s.name, [])
            and (s.hint.get("shape") or infer_shape(s.expr)) in FORMULA_SHAPES
        ),
        None,
    )
    if formula_step is not None:
        shape = formula_step.hint.get("shape") or infer_shape(formula_step.expr)
        terms = _formula_terms(pen, formula_step, shape)
        if terms:
            fml = f"fml_{aid}"
            pen.formula_id = fml
            put(main, lex.sentence_formula_pointer(rng))
            alt = _formula_alt(draft, pen, formula_step, shape)
            main.blocks.append(bk.formula(fml, alt, terms))
            pen.units.append(fml)
            pen.sources.append({"unit": fml})

    # ---- 但し書きの行き先：次の項 / 条末脚注 / 別の条（分散。DESIGN.md §8.5）----
    where = placement.proviso if (placement is not None and deferred) else "paragraph"
    proviso_paras: list[_Para] = []
    for step, shape in deferred:
        if where == "footnote":
            # 本文には印だけを付け、中身は条末脚注に置く（本文と根拠が離れる＝分散）
            s = _qualify_sentence(pen, step, shape, rng, subject="前項の規定により算出した額")
            note = _attach_footnote(pen, main, s.text, aid)
            pen.satisfied.update(s.satisfies)
            pen.units.append(note)
            continue
        if where == "article":
            # 中身を別の条に置き、本文からはその条を `{ref:}` で指す（根拠が条をまたぐ＝分散）
            paid = placement.proviso_article_id
            para = _Para(f"{paid}_p{len(proviso_paras) + 1}")
            proviso_paras.append(para)
            # 別の条から見た主語は「前項」ではなく、元の条そのもの
            subject = f"{{ref:{aid}}}の規定により算出した額"
            put(para, _qualify_sentence(pen, step, shape, rng, subject=subject))
            pen.units.append(para.pid)
            continue
        para = _new_para(paras, aid)
        put(para, _qualify_sentence(pen, step, shape, rng, subject="前項の規定により算出した額"))
        pen.units.append(para.pid)
    if proviso_paras:
        what = _proviso_what(deferred)
        paid = placement.proviso_article_id
        put(main, lex.sentence_proviso_pointer(f"{{ref:{paid}}}", what, rng))
        out.proviso_article = bk.node(
            paid,
            "article",
            title=lex.proviso_article_title(what),
            children=[
                bk.node(q.pid, "paragraph", text=q.text(), blocks=q.blocks or None) for q in proviso_paras
            ],
        )

    # ---- 適用範囲の文（scope:*）----
    scope_ob = next((o for o in draft.obligations if o.startswith("scope:")), None)
    if scope_ob and scope_ob not in pen.satisfied and (draft.vocab.get("scope_amount") or draft.consts):
        para = _new_para(paras, aid)
        amount = draft.vocab.get("scope_amount") or f"{{const:{draft.consts[-1].name}}}"
        put(para, lex.sentence_scope(scope_ob.split(":")[1], draft.benefit, amount, rng))
        pen.units.append(para.pid)

    # ---- 設例の囲み ----
    explanatory: list[str] = []
    if draft.example_sets and example_values is not None:
        bid = f"box_{aid}_note"
        texts = example_values.get(draft.rule_id) or []
        if texts:
            article_blocks.append(
                bk.box(bid, draft.vocab.get("example_title"), texts, "margin_note", anchor=main.pid)
            )
            explanatory = [f"{bid}_p{i}" for i in range(1, len(texts) + 1)]

    # ---- 条末脚注（条のいちばん後ろに置く。本体 lint L02） ----
    if pen.footnotes:
        article_blocks.append(bk.footnotes(f"fn_{aid}", [text for _n, text in pen.footnotes]))

    # ---- 仕様 ----
    out.spec_rules.append(_spec_rule(ctx, pen, draft, explanatory))
    for c in draft.consts:
        out.spec_params[c.name] = _param_spec(c, pen)
    out.answer.append(
        {
            "rule": draft.rule_id,
            "function": draft.function,
            "pattern": draft.pattern,
            "units": list(dict.fromkeys(pen.units)),
            "explanatory_units": explanatory,
            "constants": [c.name for c in draft.consts],
            "modalities": _modalities_used(pen, modalities),
            "difficulty": draft.difficulty,
        }
    )


def _attach_footnote(pen: _Pen, para: _Para, note_text: str, aid: str) -> str:
    """但し書きを条末脚注にし、額を述べた文に `{fn:n}` の印を付ける。

    印を**あとから差し込む**と、根拠として記録した引用が原文と食い違う（G2 が落ちる）。
    印を入れた文で記録も差し替える。
    """
    n = len(pen.footnotes) + 1
    at = pen.main_sentence if pen.main_sentence is not None else len(para.sentences) - 1
    old_text, satisfies = para.sentences[at]
    marked = _mark(old_text, n)
    para.sentences[at] = (marked, satisfies)
    for src in pen.sources:
        if src.get("raw") == old_text:
            src["raw"] = marked
    # 但し書きを前項ではなく「前の文」として書き直す（脚注は条の中にあるため）
    note = note_text.replace("前項の規定により算出した額", "本文の規定により算出した額")
    pen.footnotes.append((n, note))
    uid = f"fn_{aid}__n{n}"
    pen.sources.append({"unit": uid, "raw": note})
    return uid


#: 但し書きの形 → 別の条にしたときの見出し・案内文に使う言い方
PROVISO_WHAT = {
    "round": "端数",
    "floor_zero": "支払わない場合",
    "ceil_period": "期間の端数",
}


def _proviso_what(deferred: list[tuple[StepDraft, str]]) -> str:
    """但し書きを別の条に分けたときの呼び方。複数あれば並べる。"""
    names = list(dict.fromkeys(PROVISO_WHAT.get(shape, "計算") for _step, shape in deferred))
    return "および".join(names)


def _mark(text: str, n: int) -> str:
    """文の終わりの句点の前に脚注の印を入れる。"""
    token = f"{{fn:{n}}}"
    return f"{text[:-1]}{token}。" if text.endswith("。") else f"{text}{token}"


def _trigger_sentence(ctx: Context, draft: RuleDraft, rng: random.Random) -> str:
    clause = ctx.resolve_tokens(draft.trigger)
    return f"当会社は、{clause}に、この条に従い、{draft.benefit}を支払います。"


def _qualify_sentence(
    pen: _Pen, step: StepDraft, shape: str, rng: random.Random, subject: str
) -> lex.Rendered:
    e, d = step.expr, pen.d
    if shape == "cap":
        limit = next(pen.operand(a) for a in e["args"] if "param" in a)
        return lex.sentence_cap(limit, d.benefit, rng, subject=subject)
    if shape == "floor_zero":
        return lex.sentence_floor_zero(d.benefit, rng, subject=subject)
    if shape == "round":
        return lex.sentence_round(pen.operand(e["args"][1]), e["rounding"], rng, subject=subject)
    if shape == "round_unspecified":
        return lex.sentence_round_unspecified(pen.operand(e["args"][1]), rng, subject=subject)
    if shape == "ceil_period":
        return lex.sentence_ceil_period(step.hint["unit_word"], rng)
    if shape == "out_of_range":
        return lex.sentence_table_out_of_range(
            step.hint["key_phrase"], _limit_operand(pen, e), d.benefit, rng
        )
    if shape == "default":
        return lex.sentence_default(pen.operand(e["args"][1]), rng)
    if shape == "policy_limit":
        return lex.sentence_policy_limit(step.hint["limit_phrase"], f"{{const:{step.hint['default']}}}", rng)
    if shape == "min":
        return lex.sentence_cap(pen.operand(e["args"][1]), d.benefit, rng, subject=subject)
    raise ValueError(f"但し書きにできない手順の形: {shape}")


def _span_operand(pen: _Pen, e: dict) -> str:
    """期間の長さを表す定数を式から取り出す（初日算入のために −1 してあることがある）。"""
    if "param" in e or "var" in e or "lit" in e:
        return pen.operand(e)
    for a in e.get("args", []):
        if "param" in a:
            return pen.operand(a)
    raise ValueError("期間を表す定数が式に無い")


def _limit_operand(pen: _Pen, e: dict) -> str:
    """`if(gt(key, limit), 0, x)` の limit を取り出す。"""
    cond = e["args"][0]
    for a in cond.get("args", []):
        if "param" in a:
            return pen.operand(a)
    raise ValueError("表の範囲を示す定数が式に無い")


def _sentence_step(pen: _Pen, step: StepDraft, shape: str, rng: random.Random) -> lex.Rendered:
    e, d = step.expr, pen.d
    if shape == "case":
        cond = _cond_phrase(pen, e["args"][0], step)
        return lex.sentence_case(cond, pen.operand(e["args"][1]), pen.operand(e["args"][2]), d.benefit, rng)
    if shape == "case_vague":
        cond = e["args"][0]
        subject_phrase = pen.operand(cond["args"][0])
        threshold = pen.operand(cond["args"][1])
        return lex.sentence_case_vague(
            threshold, subject_phrase, pen.operand(e["args"][1]), pen.operand(e["args"][2]), d.benefit, rng
        )
    if shape == "out_of_range":
        return lex.sentence_table_out_of_range(
            step.hint["key_phrase"], _limit_operand(pen, e), d.benefit, rng
        )
    if shape == "deadline":
        base = pen.operand(e["args"][0])
        span = _span_operand(pen, e["args"][1])
        included = step.hint.get("first_day_included", True)
        effect = step.hint.get("effect") or ""
        return lex.sentence_period_start(base, span, included, effect, rng)
    if shape == "waiting":
        return lex.sentence_waiting(pen.operand(e["args"][1]), d.benefit, rng)
    if shape == "frame":
        return lex.sentence_frame(step.hint.get("inner", True), step.hint["small"], step.hint["big"], rng)
    if shape == "multi_hit":
        return lex.sentence_multi_hit(step.hint["rule"], d.benefit, rng)
    if shape == "threshold":
        a, b = pen.operands(e)
        return lex.sentence_threshold(a, b, e["op"], step.hint.get("effect", ""), rng)
    if shape == "waiting_rule":
        return lex.sentence_waiting_rule(
            pen.operand(e["args"][1]), step.hint.get("start_phrase", ""), d.benefit, rng
        )
    if shape == "cap_subject":
        return lex.sentence_cap_subject(step.hint["subject_phrase"], pen.operand(e["args"][1]), rng)
    return _qualify_sentence(pen, step, shape, rng, subject="この額")


def _cond_phrase(pen: _Pen, e: dict, step: StepDraft) -> str:
    if e.get("op") in CMP:
        a, b = pen.operands(e)
        return lex._CMP_PRED[e["op"]].format(a=a, b=b)
    if e.get("op") in ("and", "or"):
        return lex.conjunction([], e["op"] == "and")
    return step.hint.get("cond_phrase", pen.operand(e))


def _formula_alt(draft: RuleDraft, pen: _Pen, step: StepDraft, shape: str) -> str:
    a = pen.operands(step.expr)
    if shape == "sub":
        body = f"{a[0]}から{a[1]}を差し引いた額"
    elif shape == "sum":
        body = "、".join(a) + "の合計額"
    elif shape == "mul":
        body = f"{a[0]}に{a[1]}を乗じて得た額"
    elif shape == "table_rate":
        body = f"{a[0]}に{step.hint.get('rate_name', '割合')}を乗じて得た額"
    elif shape == "proration":
        body = f"{a[0]}に{a[1]}の{a[2]}に対する割合を乗じて得た額"
    else:
        body = "算出の方法"
    return f"{body}が、{draft.benefit}の額となることを示す算式。"


# --------------------------------------------------------------------- 表
def _table_block(tid: str, t: TableDraft) -> dict:
    semantic = [
        {t.key_header: k, t.value_header: v} for k, v in zip(t.key_surfaces, t.value_surfaces, strict=True)
    ]
    if t.orientation == "header_keys":
        header = [t.key_header, *t.key_surfaces]
        rows = [[t.value_header, *t.value_surfaces]]
        return bk.table(
            tid,
            t.semantic_type,
            header,
            rows,
            caption=t.caption,
            align_body="center",
            records_rows=semantic,
        )
    header = [t.key_header, t.value_header]
    rows = [[k, v] for k, v in zip(t.key_surfaces, t.value_surfaces, strict=True)]
    return bk.table(tid, t.semantic_type, header, rows, caption=t.caption, records_rows=semantic)


def _table_source(tid: str, t: TableDraft) -> dict:
    return {"unit": f"{tid}__caption"} if t.caption else {"unit": f"{tid}__r0c0"}


def _table_spec(tid: str, t: TableDraft) -> dict:
    out: dict[str, Any] = {
        "from_block": tid,
        "shape": t.orientation,
        "key_parse": t.key_parse,
        "value_parse": t.value_parse,
        "mode": t.mode,
        "key_unit": t.key_unit,
        "value_unit": t.value_unit,
        "expect_keys": list(t.keys),
    }
    if t.orientation == "header_keys":
        out["key_row"], out["value_row"] = 0, 1
    else:
        out["key_col"], out["value_col"] = 0, 1
    if t.monotone:
        out["monotone"] = t.monotone
    return out


# --------------------------------------------------------------------- 仕様
def _spec_rule(ctx: Context, pen: _Pen, draft: RuleDraft, explanatory: list[str]) -> dict:
    steps = []
    for s in draft.steps:
        label = pen.labels.get(s.name) or pen.phrases.get(s.name) or s.name
        steps.append({"name": s.name, "label": label, "expr": s.expr, "role": s.role})
    out = {
        "id": draft.rule_id,
        "title": draft.title,
        "kind": draft.kind,
        "interface": {"function": draft.function},
        "inputs": draft.inputs,
        "collections": draft.collections,
        "steps": steps,
        "output": draft.output,
        "obligations": list(draft.obligations),
        "sources": _dedupe_sources(pen.sources),
        "properties": list(draft.properties),
        "preconditions": list(draft.preconditions),
        "presentation": {
            "pattern": draft.pattern,
            "placement": pen.placement_kind,
            "subject": draft.subject_key,
            "table": pen.table_id,
            "figure": pen.figure_id,
            "formula": pen.formula_id,
            "explanatory_units": explanatory,
        },
        "difficulty": draft.difficulty,
    }
    if draft.kind == "calculation" and draft.output.get("unit"):
        out["scope"] = next(
            (o.split(":")[1] for o in draft.obligations if o.startswith("scope:")), "per_accident"
        )
    return out


def _dedupe_sources(sources: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out = []
    for s in sources:
        key = (s["unit"], s.get("raw"))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _param_spec(c: ConstDraft, pen: _Pen) -> dict:
    src = next((s for s in pen.sources if s.get("raw") and f"{{const:{c.name}}}" in s["raw"]), None)
    if src is None:
        raise ValueError(f"定数 {c.name} を使った文が無い（根拠を示せない）")
    out = {"unit": c.unit, "from_const": c.name, "source": {"unit": src["unit"], "raw": src["raw"]}}
    if c.const_unit:
        out["const_unit"] = c.const_unit
    return out


def _modalities_used(pen: _Pen, modalities: dict) -> list[str]:
    out = ["prose"]
    if pen.formula_id:
        out.append("formula")
    if pen.table_id:
        out.append("table")
    if pen.figure_id:
        out.append("figure")
    return out
