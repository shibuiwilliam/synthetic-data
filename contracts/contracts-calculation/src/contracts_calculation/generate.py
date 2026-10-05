"""追加モードの生成パイプライン（DESIGN.md §5・§12.5・§12.6）。

1 つの既定の契約書（base）に対して：
  コピー → パターン選択 → 抽選 → 実現（条・表・定数） → パッチ →
  本体で fill_records / lint / build / render → 仕様・正解プログラム・正解表 → 検証ゲート

出力（<out_root>/<new_cid>/）:
  contract.json / <doc_id>.pdf / calc/{spec.json, patch.json, answer_key.json,
  programs/calc_<cid>.py, calendar.json, manifest.json}
作業ディレクトリ（パッチ済み content）は <out_root>/_work/<new_cid>/ に残す（再現・デバッグ用）。
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

from . import base_adapter as ba
from .bindings.engine import bind_document
from .bindings.raw import raw_text_map
from .codegen.python import generate_module
from .config import PROFILES, Profile
from .docmodel.index import DocumentIndex
from .docmodel.numbers_ja import format_amount_yen
from .fictionalize import fictionalize_content, load_replacements
from .patterns.base import RuleDraft, fw
from .planning.context import Context
from .planning.selector import select_patterns
from .realize.blocks import make_appendix, make_article, make_example_box, make_table
from .realize.figures import make_renewal_timeline
from .realize.patch import Patcher
from .testgen.cases import build_cases
from .testgen.mutation import measure
from .testgen.pytest_writer import write_tests
from .testgen.taskcards import build_taskcards
from .verify.gates import GateResult, run_gates

GENERATOR_VERSION = (
    # 0.8.3: 全文レビュー（負額防止・不可抗力の時系列・価格指数の単位・文言明確化）
    # 0.8.2: 既知の実在名称との衝突回避、月単位期限の文言明確化
    # 0.8.1: K06 クランプ帯に丸め感応ケースを追加（G7 の運任せを排除）
    # 0.8.0: 文型の変種（§9.3）・営業日定義の分散と definition_units（§11.1）
    # 0.7.0: 頭書分離・challenge 矛盾・bind_only（DESIGN 完全化）
    "0.8.3"
)

#: パターン → 章立て文書での追加先の章タイトルの手がかり
CHAPTER_HINTS: dict[str, tuple[str, ...]] = {
    "K01": ("対価", "支払", "賃金", "委託料", "報酬", "料金"),
    "K02": ("対価", "支払", "賃金", "委託料", "報酬", "料金"),
    "K03": ("対価", "支払", "委託料", "報酬", "料金"),
    "K04": ("対価", "支払", "委託料", "報酬", "料金"),
    "K05": ("対価", "支払", "委託料", "報酬", "料金"),
    "K07": ("対価", "支払", "賃金", "料金"),
    "K08": ("対価", "支払", "料金"),
    "K11": ("対価", "支払", "料金"),
    "K12": ("業務", "遂行", "開発", "総則"),
    "K13": ("業務", "遂行", "開発", "総則"),
    "K14": ("業務", "遂行", "開発"),
    "K17": ("対価", "支払", "一般", "雑則"),
    "K18": ("一般", "雑則", "権利", "義務"),
    "K20": ("一般", "雑則", "権利", "義務"),
    "K23": ("退職", "一般", "雑則"),
    "K25": ("就業", "服務", "一般", "雑則", "権利", "義務"),
}


@dataclass
class GenerateResult:
    content_id: str
    out_dir: Path
    gates: list[GateResult]
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(g.passed for g in self.gates)


def derive_new_cid(base_cid: str, calc_seed: int) -> str:
    m = re.fullmatch(r"([a-z]+)-(\d{4})", base_cid)
    if not m:
        raise ValueError(f"content_id の形式が想定外: {base_cid}")
    return f"{m.group(1)}-{int(m.group(2)) + 100 * calc_seed:04d}"


def generate_one(
    base_dir: Path,
    calc_seed: int,
    out_root: Path,
    profile: Profile | str = "standard",
    rules_min: int | None = None,
    rules_max: int | None = None,
    png: bool = False,
    render: bool = True,
    bind_only: bool = False,
) -> GenerateResult:
    """bind_only=True は付与モードだけを実行する（追加なし・content_id は base のまま。DESIGN.md §15 bind）。"""
    if isinstance(profile, str):
        profile = PROFILES[profile]
    rules_min = profile.rules_min if rules_min is None else rules_min
    rules_max = profile.rules_max if rules_max is None else rules_max
    base_dir = Path(base_dir)
    out_root = Path(out_root)
    base_cid = base_dir.name
    new_cid = base_cid if bind_only else derive_new_cid(base_cid, calc_seed)
    work = out_root / "_work" / new_cid
    if work.exists():
        shutil.rmtree(work)
    work.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(base_dir, work)
    replaced_names = fictionalize_content(work, load_replacements(ba.calc_root()))

    ctx = Context.load(work)
    patcher = Patcher(content_dir=work, doc=ctx.doc)  # doc を共有し、定数の追加が文脈にも見えるようにする
    if not bind_only:
        patcher.set_content_id(new_cid)

    rng_doc = Random(f"calc:{base_cid}:{calc_seed}")
    notes = [f"名称衝突を合成名へ置換: {len(replaced_names)} 件"] if replaced_names else []
    if bind_only:
        patterns = []
        notes.append("bind_only: 追加モードは実行しない（既定の契約書への付与だけ）")
    else:
        exclude_ids = (
            {"K31"} if profile.appendix_weight == 0 else set()
        )  # K31 は別紙が前提（basic では使わない）
        patterns, selection_notes = select_patterns(
            ctx, rng_doc, rules_min, rules_max, exclude_ids=exclude_ids
        )
        notes.extend(selection_notes)

    # 抽選と実現。値の表記が文書内（既定の定数を含む）で重複しないよう、重複時は再抽選する
    used_surfaces: set[str] = set(ctx.constants.values())
    drafts: list[RuleDraft] = []
    chapter_of: dict[str, str | None] = {}
    for p in patterns:
        rng_rule = Random(f"calc:{base_cid}:{calc_seed}:{p.id}")
        draft = None
        for _attempt in range(10):
            cand = p.sample(ctx, rng_rule)
            surfaces = [pd.surface for pd in cand.params.values()]
            conflict = len(set(surfaces)) != len(surfaces) or any(
                a == b or a in b or b in a for a in surfaces for b in used_surfaces
            )
            if not conflict:
                draft = cand
                break
        if draft is None:
            notes.append(f"{p.id}: 値の表記の重複を解消できず、このパターンを見送った")
            continue
        used_surfaces.update(pd.surface for pd in draft.params.values())
        used_surfaces.update(draft.literal_surfaces)
        patcher.add_constants({name: pd.surface for name, pd in draft.params.items()})
        drafts.append(draft)
        chapter_of[draft.rule_id] = ctx.pick_chapter(CHAPTER_HINTS.get(p.id, ())) if ctx.chapters else None

    if not drafts and not bind_only:
        raise ValueError(f"{base_cid}: 追加できるルールが 1 件も無い")

    # 営業日の定義の分散（独立の条へ分離。DESIGN.md §11.1 の分散度・§12.7 definition_units）
    calendar_drafts = [d for d in drafts if d.needs_calendar]
    scatter_def = bool(calendar_drafts) and (
        len(calendar_drafts) >= 2  # 複数ルールが使うなら定義は 1 箇所に置く（二重掲載を防ぐ）
        or rng_doc.random() < profile.scatter_weight
    )
    if scatter_def:
        for d in calendar_drafts:
            d.paragraphs = [p for p in d.paragraphs if not (isinstance(p, str) and "「営業日」とは" in p)]
            d.difficulty["scatter"] = 2

    # 頭書への分離（頭書を持つ文書のみ。DESIGN.md §9.2・§12.5 add_header_row）
    header_plan: dict[str, dict] = {}
    if ctx.head_matter_id:
        head_counter = 0
        for d in drafts:
            if d.header_option and rng_doc.random() < profile.header_weight:
                base_hid = ctx.next_head_item_id()
                prefix = ctx.head_item_prefix
                num = int(base_hid[len(prefix) :]) + head_counter
                head_counter += 1
                hid = f"{prefix}{num}"
                d.paragraphs = list(d.header_option["body_paragraphs"])
                header_plan[d.rule_id] = {
                    "param": d.header_option["param"],
                    "title": d.header_option["title"],
                    "item_id": hid,
                }

    # challenge モード（ラベル付きの難所を 1 件。DESIGN.md §11.3）
    challenge_info: dict | None = None
    if profile.challenge and not bind_only:
        omission = [
            d
            for d in drafts
            if d.pattern_id in ("K06", "K07", "K08")
            and any(ob.startswith("rounding:") for ob in d.obligations)
        ]
        contradiction = [d for d in drafts if d.pattern_id == "K31"]
        anomaly = [d for d in drafts if d.pattern_id in ("K01", "K06")]
        kinds = [
            k
            for k, c in (("omission", omission), ("contradiction", contradiction), ("anomaly", anomaly))
            if c
        ]
        picked_kind = kinds[rng_doc.randrange(len(kinds))] if kinds else None
        target = {"omission": omission, "contradiction": contradiction, "anomaly": anomaly}.get(
            picked_kind, [None]
        )[0]
        if target is None:
            notes.append("challenge: 対象にできるルールが無かった（欠落・矛盾・異例の候補なし）")
        elif picked_kind == "contradiction":
            # 矛盾：本文の単価と別紙の単価が異なるのに、優先順位の条項を落とす（DESIGN.md §11.3）
            target.paragraphs = [
                p.replace("ただし、別紙に異なる定めがあるときは、別紙の定めによる。", "")
                if isinstance(p, str)
                else p
                for p in target.paragraphs
            ]
            target.obligations = [ob for ob in target.obligations if not ob.startswith("priority:")]
            body_param = next(iter(target.params))
            target.challenge = {
                "type": "contradiction",
                "aspect": "value_conflict",
                "note": "本文と別紙で単価が異なり、優先順位の条項が無い（どちらの読みも成り立つ）",
                "body_param": body_param,
                "conflict_table": next(iter(target.tables)),
            }
            challenge_info = {
                "rule": target.rule_id,
                **{k: v for k, v in target.challenge.items() if k in ("type", "aspect", "note")},
            }
        elif picked_kind == "omission":
            target.paragraphs = [
                re.sub(r"この計算により生じた[^。]*。", "", p) if isinstance(p, str) else p
                for p in target.paragraphs
            ]
            target.obligations = [ob for ob in target.obligations if not ob.startswith("rounding:")]
            target.challenge = {
                "type": "omission",
                "aspect": "rounding",
                "note": "端数処理の文を落とした。丸めの方向は本文から決まらない",
            }
            challenge_info = {"rule": target.rule_id, **target.challenge}
        else:
            names = sorted(target.params)
            n_min = next(n for n in names if "min" in n)
            n_cap = next(n for n in names if "cap" in n)
            pmin, pcap = target.params[n_min], target.params[n_cap]
            pmin.value, pcap.value = pcap.value, pmin.value
            pmin.surface, pcap.surface = pcap.surface, pmin.surface
            patcher.doc["meta"]["constants"][n_min] = pmin.surface
            patcher.doc["meta"]["constants"][n_cap] = pcap.surface
            target.challenge = {
                "type": "anomaly",
                "aspect": "floor_above_cap",
                "note": "下限が上限を上回る（計算は定義どおり常に上限に落ちる）",
                # 出力が常に上限値になるため、下限と、クランプ前の計算（raw_fee）に効く変異は現れない
                "inert_params": [n_min],
                "inert_steps": [target.steps[0]["name"]],
            }
            challenge_info = {"rule": target.rule_id, **target.challenge}

    # 図（K13 の時間軸。本文が規範で、図は説明）
    figure_plan: dict | None = None
    if any(d.pattern_id == "K13" for d in drafts) and rng_doc.random() < profile.figure_weight:
        d13 = next(d for d in drafts if d.pattern_id == "K13")
        fig_id = "fig_support_renewal"
        if fig_id not in ctx.idx.figures and fig_id not in ctx.idx.units:
            notice_const = next(iter(d13.params))
            d13.paragraphs[0] = d13.paragraphs[0] + f"期間の関係は{{ref:{fig_id}}}のとおりとする。"
            figure_plan = {"rule": d13.rule_id, "fig_id": fig_id, "notice_const": notice_const}

    # 計算例の箱（説明であり規範ではない。妨害要素を兼ねる）
    box_plan: dict | None = None
    if rng_doc.random() < profile.example_box_weight:
        for d in drafts:
            if d.challenge or d.kind != "calculation" or d.output.get("unit") != "JPY":
                continue
            if any(decl["type"] != "int" for decl in d.inputs.values()):
                continue
            example_inputs = _nice_example_inputs(d)
            if example_inputs is None:
                continue
            expect = _eval_draft(d, example_inputs)
            if not isinstance(expect, int):
                continue
            box_plan = {
                "rule": d.rule_id,
                "box_id": f"box_{d.rule_id}_ex",
                "inputs": example_inputs,
                "expect": expect,
                "text": _example_text(d, example_inputs, expect, ctx.digit_style),
            }
            break

    # 条 ID の払出し（章ごとに連番）。分離した営業日の定義条が先頭に来るようにする
    article_ids: dict[str, str] = {}
    def_article_id: str | None = None
    def_chapter = (ctx.pick_chapter(("総則", "定義")) if ctx.chapters else None) if scatter_def else None
    by_chapter: dict[str | None, list[RuleDraft]] = {}
    for d in drafts:
        by_chapter.setdefault(chapter_of[d.rule_id], []).append(d)
    for ch, ds in by_chapter.items():
        extra = 1 if (scatter_def and ch == def_chapter and def_article_id is None) else 0
        ids = ctx.next_article_ids(len(ds) + extra, ch)
        if extra:
            def_article_id = ids[0]
            ids = ids[1:]
        for d, aid in zip(ds, ids):
            article_ids[d.rule_id] = aid
    if scatter_def and def_article_id is None:  # 既存の条が無い章構成でも必ず割り当てる
        def_article_id = ctx.next_article_ids(1, def_chapter)[0]

    # 他ルールの条への参照（{REF_RULE:<rule_id>} → {ref:<条ID>}）
    for d in drafts:
        d.paragraphs = [
            (
                re.sub(r"\{REF_RULE:([a-z0-9_]+)\}", lambda m: "{ref:" + article_ids[m.group(1)] + "}", p)
                if isinstance(p, str)
                else p
            )
            for p in d.paragraphs
        ]

    # 分離した営業日の定義条を先に足す（使う条より前に現れるようにする）
    added_units: set[str] = set()
    def_unit_id: str | None = None
    seq = 0
    if scatter_def and def_article_id:
        from .patterns.base import calendar_def_paragraph

        def_text = calendar_def_paragraph(ctx.digit_style).replace("本条において", "本契約において")
        def_unit_id = f"{def_article_id}_p1"
        def_node = {
            "id": def_article_id,
            "kind": "article",
            "title": "営業日",
            "children": [{"id": def_unit_id, "kind": "paragraph", "text": def_text}],
        }
        if def_chapter is None:
            patcher.add_article_flat(def_node, seq)
            seq += 1
        else:
            patcher.add_article_to_chapter(def_node, def_chapter)
        added_units.add(def_unit_id)

    # 表 ID の払出しとノード組立・パッチ（表は profile に応じて本文または別紙に置く）
    unit_infos: dict[str, dict] = {}
    table_ids_of: dict[str, dict[str, str]] = {}
    has_tables = False
    appendix_seq = 0
    allocated_sch: set[str] = set()
    for d in drafts:
        aid = article_ids[d.rule_id]
        table_ids: dict[str, str] = {}
        for tname in d.tables:
            tid = f"tbl_{tname}"
            if tid in ctx.idx.tables:
                tid = f"tbl_{tname}_b"
            table_ids[tname] = tid
            has_tables = True
        placement = "body"
        ref_ids = dict(table_ids)
        attach_ids = dict(table_ids)
        appendix_nodes: list[dict] = []
        if d.tables and (d.force_appendix or rng_doc.random() < profile.appendix_weight):
            placement = "appendix"
            attach_ids = {}
            sch_ids = []
            for cand in ctx.next_appendix_ids(len(d.tables) + appendix_seq):
                if cand not in allocated_sch:
                    sch_ids.append(cand)
                if len(sch_ids) == len(d.tables):
                    break
            allocated_sch.update(sch_ids)
            for (tname, tdraft), sch_id in zip(d.tables.items(), sch_ids):
                ref_ids[tname] = sch_id
                # 別紙の表は番号で指さず「次の表」と書く（caption_numbering: chapter の文書では
                # 章の外の表に番号が振られず {ref:} が解決できないため。L26 は番号の無い表を対象外とする）
                intro = f"{d.title}の単価は、次の表のとおりとする。"
                table_block = make_table(table_ids[tname], tdraft)
                table_block["caption"] = None
                appendix_nodes.append(make_appendix(sch_id, f"{d.title}の単価", intro, table_block))
        node, info = make_article(aid, d, attach_ids, ref_ids)
        info["placement"] = placement
        info["explanatory_units"] = []
        info["header_params"] = {}
        if d.rule_id in header_plan:
            plan = header_plan[d.rule_id]
            hid = plan["item_id"]
            # 頭書の項目は見出し語を text に持つ（lea・pur の実物と同じ形。title は描画されない）
            head_item = {
                "id": hid,
                "kind": "item",
                "text": plan["title"],
                "children": [
                    {"id": f"{hid}_d", "kind": "paragraph", "text": "{const:" + plan["param"] + "}"}
                ],
            }
            patcher.add_header_row(ctx.head_matter_id, head_item)
            info["header_params"][plan["param"]] = f"{hid}_d"
            info["param_units"][plan["param"]] = f"{hid}_d"
            info["paragraph_ids"] = info["paragraph_ids"] + [f"{hid}_d"]
        if placement == "appendix":
            for (tname, tdraft), an in zip(d.tables.items(), appendix_nodes):
                tid = table_ids[tname]
                info["table_value_cells"][tname] = [f"{tid}__r{i}c1" for i in range(1, len(tdraft.rows) + 1)]
                intro_pid = f"{an['id']}_s1_p1"
                info["paragraph_ids"] = info["paragraph_ids"] + [intro_pid]
        if d.figure_blocks:
            for _idx, fig in d.figure_blocks:
                info.setdefault("normative_figures", []).append(fig["id"])
        if figure_plan and figure_plan["rule"] == d.rule_id:
            fig = make_renewal_timeline(figure_plan["fig_id"], figure_plan["notice_const"])
            node["children"][0].setdefault("blocks", []).append(fig)
            info["explanatory_units"].append(figure_plan["fig_id"])
        if box_plan and box_plan["rule"] == d.rule_id:
            box = make_example_box(box_plan["box_id"], aid, box_plan["text"])
            node.setdefault("blocks", []).append(box)
            info["explanatory_units"].append(f"{box_plan['box_id']}_p1")
            info["example"] = {"oracle": "manual", "inputs": box_plan["inputs"], "expect": box_plan["expect"]}
        unit_infos[d.rule_id] = info
        table_ids_of[d.rule_id] = table_ids
        added_units.update(info["paragraph_ids"])
        for cells in info["table_value_cells"].values():
            added_units.update(cells)
        for pid, para in zip(info["paragraph_ids"], d.paragraphs):
            if isinstance(para, dict):
                for j in range(1, len(para.get("items", [])) + 1):
                    added_units.add(f"{pid}_i{j}")
        ch = chapter_of[d.rule_id]
        if ch is None:
            patcher.add_article_flat(node, seq)
            seq += 1
        else:
            patcher.add_article_to_chapter(node, ch)
        for an in appendix_nodes:
            patcher.add_appendix(an, appendix_seq)
            appendix_seq += 1
    patcher.write_doc()

    # 本体のツールチェーン（G10）
    toolchain = {"fill_records": True, "lint": True, "build": True, "render": True}
    try:
        if has_tables:
            ba.run_fill_records(work)
    except RuntimeError as exc:
        toolchain["fill_records"] = False
        notes.append(str(exc)[:1000])
    try:
        ba.run_lint(work)
    except RuntimeError as exc:
        toolchain["lint"] = False
        notes.append(str(exc)[:2000])
    try:
        ba.run_build(work)
    except RuntimeError as exc:
        toolchain["build"] = False
        notes.append(str(exc)[:1000])

    out_dir = out_root / new_cid
    out_dir.mkdir(parents=True, exist_ok=True)
    render_root = out_dir / "_render"
    if render and toolchain["build"]:
        # WeasyPrint 70.0 の既知不具合（特定の内容量でレイアウトが破綻する。本体 docs/gotchas.md）への
        # 対処は「別の style で描く」。既定 style で失敗したら、決定的な順で別 style を試す。
        rendered = False
        for style in (None, "ct-a4-1col-form", "ct-a4-1col-gothic"):
            try:
                ba.run_render(work, render_root, style=style, png=png)
                rendered = True
                if style is not None:
                    notes.append(
                        f"既定 style の描画が WeasyPrint の既知不具合で破綻したため {style} で描画した"
                    )
                break
            except RuntimeError as exc:
                last_err = str(exc)
        if not rendered:
            toolchain["render"] = False
            notes.append(last_err[:1000])
    else:
        toolchain["render"] = toolchain["build"] and not render

    if not toolchain["build"]:
        return GenerateResult(
            new_cid, out_dir, [GateResult("G10", False, detail="; ".join(notes)[:500])], notes
        )

    rebuilt = DocumentIndex.load(work)

    # 付与モード：既定の契約書の条項への照合（追加した単位は対象外）
    bound_rules, bound_excluded = bind_document(rebuilt, raw_text_map(work), added_units)

    # 仕様・正解表・正解プログラム
    spec_dict = _assemble_spec(
        new_cid, ctx, drafts, unit_infos, table_ids_of, rebuilt, calc_seed, def_unit_id=def_unit_id
    )
    for b in bound_rules:
        for pname, pdict in b.params.items():
            existing = spec_dict["params"].get(pname)
            if existing is not None and existing != pdict:
                raise ValueError(f"bound の定数が衝突した: {pname}")
            spec_dict["params"][pname] = pdict
        spec_dict["rules"].append(b.rule)
    citations = {uid: u.citation for uid, u in rebuilt.units.items() if u.citation}
    from .spec.model import CalcSpec

    spec_obj = CalcSpec.from_dict(spec_dict)
    module_src = generate_module(spec_obj, citations)
    answer_key = _assemble_answer_key(drafts, unit_infos, table_ids_of, article_ids, def_unit_id)
    for b in bound_rules:
        answer_key.append(
            {
                "rule": b.rule["id"],
                "function": b.rule["interface"]["function"],
                "pattern": b.rule.get("presentation", {}).get("pattern", b.binding),
                "origin": "bound",
                "binding": b.binding,
                "article": None,
                "units": list(b.units),
                "definition_units": [],
                "value_locations": {name: "body" for name in b.params},
                "modalities": ["prose"],
                "difficulty": b.rule.get("difficulty", {}),
            }
        )
    units_by_rule: dict[str, list[str]] = {
        a["rule"]: a["units"] + a.get("definition_units", []) for a in answer_key
    }

    # テストケースと変異の測定（G7・G8 の材料）
    cases_by_rule: dict[str, list] = {}
    mutation_by_rule: dict[str, dict] = {}
    hints_by_rule = {d.rule_id: d.case_hints for d in drafts if d.case_hints}
    for rule in spec_obj.rules:
        rng_cases = Random(f"cases:{base_cid}:{calc_seed}:{rule.id}")
        cases = build_cases(spec_obj, rule, rng_cases, hints=hints_by_rule.get(rule.id))
        rule_dict = next(r for r in spec_dict["rules"] if r["id"] == rule.id)
        case_filter = None
        if (rule_dict.get("challenge") or {}).get("aspect") == "value_conflict":
            cases = _conflict_agnostic_cases(spec_dict, rule, cases, rule_dict["challenge"])
            if len([c for c in cases if c.kind != "unknown"]) < 1:
                notes.append(f"challenge: {rule.id} の読みが割れないケースが無い")
        if (rule_dict.get("challenge") or {}).get("aspect") == "rounding":
            cases = _rounding_agnostic_cases(spec_dict, rule, cases)
            if len([c for c in cases if c.kind != "unknown"]) < 4:
                notes.append(f"challenge: {rule.id} の読みが割れないケースが少ない（{len(cases)} 件）")

            def case_filter(inputs, _spec_dict=spec_dict, _rule=rule):
                probe = build_case_like(_spec_dict, _rule, inputs)
                return bool(_rounding_agnostic_cases(_spec_dict, _rule, [probe]))

        rng_mut = Random(f"mut:{base_cid}:{calc_seed}:{rule.id}")
        mreport, extra = measure(spec_dict, rule, cases, rng_mut, case_filter=case_filter)
        cases.extend(extra)
        cases_by_rule[rule.id] = cases
        mutation_by_rule[rule.id] = mreport.to_dict()
    taskcards = build_taskcards(spec_obj, answer_key, citations)

    gates = run_gates(
        spec_dict,
        rebuilt,
        added_units,
        module_src,
        toolchain,
        cases_by_rule=cases_by_rule,
        mutation_by_rule=mutation_by_rule,
        units_by_rule=units_by_rule,
    )

    # 出力の書き出し
    calc_dir = out_dir / "calc"
    (calc_dir / "programs").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(work / "source.json", out_dir / "contract.json")
    _dump(calc_dir / "spec.json", spec_dict)
    _dump(calc_dir / "patch.json", {"base_content_id": base_cid, "ops": patcher.ops})
    _dump(calc_dir / "answer_key.json", answer_key)
    (calc_dir / "programs" / f"calc_{new_cid.replace('-', '_')}.py").write_text(module_src, encoding="utf-8")
    with (calc_dir / "cases.jsonl").open("w", encoding="utf-8") as f:
        for rule_id in sorted(cases_by_rule):
            for case in cases_by_rule[rule_id]:
                f.write(json.dumps(case.to_dict(), ensure_ascii=False) + "\n")
    with (calc_dir / "tasks.jsonl").open("w", encoding="utf-8") as f:
        for card in taskcards:
            f.write(json.dumps(card, ensure_ascii=False) + "\n")
    write_tests(calc_dir, spec_obj, taskcards)
    shutil.copyfile(ba.calc_root() / "packs" / "calendar" / "holidays_jp.json", calc_dir / "calendar.json")
    if render and toolchain["render"]:
        for pdf in sorted(render_root.glob("*/doc.pdf")):
            shutil.copyfile(pdf, out_dir / f"{pdf.parent.name}.pdf")
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "base_content_id": base_cid,
        "content_id": new_cid,
        "calc_seed": calc_seed,
        "profile": profile.name,
        **({"challenge": challenge_info} if challenge_info else {}),
        "patterns": [d.pattern_id for d in drafts],
        "rules": [d.rule_id for d in drafts],
        "notes": notes,
        "bindings": {
            "included": [{"binding": b.binding, "rule": b.rule["id"], "units": b.units} for b in bound_rules],
            "excluded": [e.to_dict() for e in bound_excluded],
        },
        "mutation": mutation_by_rule,
        "gates": [g.to_dict() for g in gates],
        "hashes": _hashes(out_dir),
    }
    _dump(calc_dir / "manifest.json", manifest)
    return GenerateResult(new_cid, out_dir, gates, notes)


# --- 仕様の組み立て ----------------------------------------------------------------


def _assemble_spec(
    new_cid: str,
    ctx: Context,
    drafts: list[RuleDraft],
    unit_infos: dict[str, dict],
    table_ids_of: dict[str, dict[str, str]],
    rebuilt: DocumentIndex,
    calc_seed: int,
    def_unit_id: str | None = None,
) -> dict:
    params: dict[str, dict] = {}
    tables: dict[str, dict] = {}
    rules: list[dict] = []
    calendar = None
    for d in drafts:
        info = unit_infos[d.rule_id]
        for name, pd in d.params.items():
            unit = info["param_units"].get(name)
            source = {"unit": unit, "quote": pd.surface}
            params[name] = pd.to_spec(source)
        for tname, tdraft in d.tables.items():
            cells = info["table_value_cells"][tname]
            tables[tname] = {
                "kind": "tiers",
                "unit": tdraft.unit,
                "rows": tdraft.to_spec_rows(),
                "source": {"unit": cells[0], "quote": tdraft.rows[0].value_text},
            }
        if d.needs_calendar and calendar is None:
            cal_pid = def_unit_id or next(
                (
                    pid
                    for pid, para in zip(info["paragraph_ids"], d.paragraphs)
                    if isinstance(para, str) and "「営業日」とは" in para
                ),
                info["paragraph_ids"][-1],
            )
            calendar = {
                "weekend": ["SAT", "SUN"],
                "closed": [["12-29", "01-03"]],
                "holidays": "input",
                "source": {"unit": cal_pid, "quote": "土曜日、日曜日、国民の祝日"},
            }
        first_pid = info["paragraph_ids"][0]
        first_text = rebuilt.units[first_pid].text if first_pid in rebuilt.units else ""
        rules.append(
            {
                "id": d.rule_id,
                "title": d.title,
                "kind": d.kind,
                "origin": "added",
                **({"parties": d.parties} if d.parties else {}),
                "interface": {"function": d.function},
                "inputs": d.inputs,
                "steps": d.steps,
                "output": d.output,
                "obligations": d.obligations,
                "presentation": {
                    "pattern": d.pattern_id,
                    "placement": info.get("placement", "body"),
                    "value_location": {
                        name: (
                            "header_sheet"
                            if name in info.get("header_params", {})
                            else ("appendix" if name not in info["param_units"] and d.tables else "body")
                        )
                        for name in d.params
                    },
                },
                "sources": [{"unit": first_pid, "quote": first_text[:20]}] if first_text else [],
                "difficulty": d.difficulty,
                **({"challenge": d.challenge} if d.challenge else {}),
                **({"examples": [info["example"]]} if info.get("example") else {}),
            }
        )
    spec: dict = {
        "spec_version": "0.1",
        "document": {"content_id": new_cid, "doctype": ctx.doctype, "calc_seed": calc_seed},
        "params": params,
        "tables": tables,
        "rules": rules,
    }
    if calendar:
        spec["calendar"] = calendar
    return spec


def _assemble_answer_key(
    drafts: list[RuleDraft],
    unit_infos: dict[str, dict],
    table_ids_of: dict[str, dict[str, str]],
    article_ids: dict[str, str],
    def_unit_id: str | None = None,
) -> list[dict]:
    out = []
    for d in drafts:
        info = unit_infos[d.rule_id]
        units = list(info["paragraph_ids"])
        for cells in info["table_value_cells"].values():
            units.extend(cells)
        info = unit_infos[d.rule_id]
        placement = info.get("placement", "body")
        modalities = ["prose"]
        if d.tables:
            modalities.append("table" if placement == "body" else "appendix_table")
        if any(u.startswith("fig_") for u in info.get("explanatory_units", [])):
            modalities.append("figure_explanatory")
        for fig_id in info.get("normative_figures", []):
            units.append(fig_id)
            modalities.append("figure_normative")
        out.append(
            {
                "rule": d.rule_id,
                "function": d.function,
                "pattern": d.pattern_id,
                "origin": "added",
                "article": article_ids[d.rule_id],
                "units": units,
                "definition_units": [def_unit_id] if (d.needs_calendar and def_unit_id) else [],
                "explanatory_units": info.get("explanatory_units", []),
                "value_locations": {
                    name: (
                        "header_sheet"
                        if name in info.get("header_params", {})
                        else ("appendix" if name not in info["param_units"] and d.tables else "body")
                    )
                    for name in d.params
                },
                "modalities": modalities,
                "difficulty": d.difficulty,
                **({"challenge": d.challenge} if d.challenge else {}),
            }
        )
    return out


def _nice_example_inputs(d) -> dict | None:
    """計算例の入力（きりのよい決定的な値）。int 入力だけのルールが対象。"""
    out: dict = {}
    for name, decl in d.inputs.items():
        lo = decl.get("min", 0) or 0
        hi = decl.get("max", 1000) or 1000
        mid = (lo + hi) // 2
        step_unit = 10 ** max(0, len(str(mid)) - 2)
        out[name] = max(lo, min(hi, (mid // step_unit) * step_unit))
    return out or None


def _eval_draft(d, inputs: dict):
    from .spec.interp import eval_rule
    from .spec.model import CalcSpec

    mini = {
        "spec_version": "0.1",
        "document": {},
        "params": {name: pd.to_spec({"unit": "x", "quote": pd.surface}) for name, pd in d.params.items()},
        "tables": {
            name: {"kind": "tiers", "rows": td.to_spec_rows(), "source": {"unit": "x", "quote": "x"}}
            for name, td in d.tables.items()
        },
        "rules": [
            {
                "id": d.rule_id,
                "title": d.title,
                "kind": d.kind,
                "interface": {"function": d.function},
                "inputs": d.inputs,
                "steps": d.steps,
                "output": d.output,
            }
        ],
    }
    spec = CalcSpec.from_dict(mini)
    return eval_rule(spec, spec.rules[0], dict(inputs))


_UNIT_WORD = {"COUNT": "件", "HOUR": "時間", "DAY": "日", "JPY": "円"}


def _example_text(d, inputs: dict, expect: int, digit_style: str) -> str:
    parts = []
    for name, decl in d.inputs.items():
        unit_word = _UNIT_WORD.get(decl.get("unit", ""), "")
        value = inputs[name]
        shown = format_amount_yen(value, "man") if decl.get("unit") == "JPY" else f"{value}{unit_word}"
        parts.append(f"{decl.get('desc', name)}が{fw(shown, digit_style)}")
    label = d.steps[-1].get("label", "計算の結果") if d.steps else "計算の結果"
    result = fw(format_amount_yen(expect, "man"), digit_style)
    return (
        "たとえば、" + "、".join(parts) + f"の場合、{label}は{result}となる。"
        "この例は理解の助けであり、適用は本条の定めによる。"
    )


def build_case_like(spec_dict: dict, rule, inputs: dict):
    """探索で見つけた入力を、判定用の仮ケースにする。"""
    from .spec.interp import eval_rule
    from .spec.model import CalcSpec
    from .testgen.cases import Case, _jsonable

    spec = CalcSpec.from_dict(spec_dict)
    expected = eval_rule(spec, rule, dict(inputs))
    return Case(
        case_id="probe",
        function=rule.function,
        kind="random",
        inputs=dict(inputs),
        expected=_jsonable(expected),
    )


def _conflict_agnostic_cases(spec_dict: dict, rule, cases: list, challenge: dict) -> list:
    """本文の単価で読んだ場合と別紙の単価で読んだ場合で、同じ結果になるケースだけを残す。"""
    import copy
    from datetime import date as _date

    from .spec.interp import eval_rule
    from .spec.model import CalcSpec

    body_value = spec_dict["params"][challenge["body_param"]]["value"]
    variant_dict = copy.deepcopy(spec_dict)
    for row in variant_dict["tables"][challenge["conflict_table"]]["rows"]:
        row["value"] = body_value
    variant = CalcSpec.from_dict(variant_dict)
    vrule = variant.rule(rule.id)
    base = CalcSpec.from_dict(spec_dict)
    brule = base.rule(rule.id)
    keep = []
    for c in cases:
        if c.kind == "unknown":
            keep.append(c)
            continue
        hol = frozenset(_date.fromisoformat(h) for h in c.holidays)
        if eval_rule(base, brule, dict(c.inputs), hol) == eval_rule(variant, vrule, dict(c.inputs), hol):
            keep.append(c)
    return keep


def _rounding_agnostic_cases(spec_dict: dict, rule, cases: list) -> list:
    """丸めの方向（floor / ceil / half_up）のどれで読んでも同じ結果になるケースだけを残す。"""
    import copy
    from datetime import date as _date

    from .spec.interp import eval_rule
    from .spec.model import CalcSpec

    variants = []
    for rounding in ("floor", "ceil", "half_up"):
        m = copy.deepcopy(spec_dict)
        rule_m = next(r for r in m["rules"] if r["id"] == rule.id)

        def set_rounding(e) -> None:
            if isinstance(e, dict):
                if e.get("op") in ("muldiv", "round_to"):
                    e["rounding"] = rounding  # noqa: B023 — 直後に使い切る
                for a in e.get("args", []):
                    set_rounding(a)

        for st in rule_m["steps"]:
            set_rounding(st["expr"])
        variants.append(CalcSpec.from_dict(m))
    keep = []
    for c in cases:
        if c.kind == "unknown":
            keep.append(c)
            continue
        hol = frozenset(_date.fromisoformat(h) for h in c.holidays)
        values = {str(eval_rule(v, v.rule(rule.id), dict(c.inputs), hol)) for v in variants}
        if len(values) == 1:
            keep.append(c)
    return keep


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _hashes(out_dir: Path) -> dict[str, str]:
    hashes = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.suffix in (".json", ".py") and "_render" not in p.parts:
            rel = str(p.relative_to(out_dir))
            if rel == "calc/manifest.json":
                continue
            hashes[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes
