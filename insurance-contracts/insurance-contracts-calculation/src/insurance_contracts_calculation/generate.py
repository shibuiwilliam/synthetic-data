"""既定の約款JSONに計算・判定の規定を足し、正解プログラムと評価データを書き出す。

    python -m insurance_contracts_calculation.cli generate --base <約款 or content> --out <出力先> --seed 1

工程（DESIGN.md §5）:

1. 既定の約款を読み、文脈（章・用語・定数・特約・既存の保険金）を取る
2. 題材とパターンを選び、ルールごとに独立した乱数でパラメータを抽選する
3. 下書き（`RuleDraft`）を文・算式・表・図に展開し、追加操作（パッチ）にする
4. パッチを当て、本体で `derived` を再計算する
5. 仕様から正解プログラムとテストケースを作る
6. 検証ゲートを通す。通らない文書は出力しない
7. 本体でPDFを描画し、計算パックを書き出す

設例の数値は仕様から計算するので、3〜4 を 2 回まわす（1 回目は囲みを作らず、
値を求めてから 2 回目で囲みを入れる）。乱数は各回で同じ列を使うため、出力は決定的である。
"""

from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import base_adapter as ba
from . import config as cfg
from .codegen import python as codegen
from .core.docindex import Doc
from .export import layout as lay
from .planning import challenge, placement, presentation, selector
from .planning.context import Context, build_context
from .realize import discourse, examples
from .realize import lexicon_ja as lex
from .realize import patch as patch_ops
from .spec import interp
from .spec.validate import RuleSet
from .testgen import cases as tc
from .testgen import mutation, pytest_writer, taskcards
from .verify import gates

#: 出力を意図して変えたときに上げる（`examples/` の差分の理由をコミットメッセージに書く）
GENERATOR_VERSION = "0.7.0"

#: 追加後の文書IDの接尾（既定のデータセットと併存させる。DESIGN.md §10.3）
DOC_SUFFIX = "c1"


def doc_suffix(variant: int = 1) -> str:
    """文書IDの接尾。同じ既定の約款から 2 本目を作るときは `c2`、3 本目は `c3` になる。

    接尾は**乱数に入らない**（乱数の鍵は既定の約款のIDと seed で作る）。番号だけ変えても
    同じ内容になるので、別の本を作るときは seed も変える。
    """
    if variant < 1:
        raise ValueError(f"variant は 1 以上（受け取った値: {variant}）")
    return DOC_SUFFIX if variant == 1 else f"c{variant}"


@dataclass
class Result:
    content_id: str
    out_dir: Path
    manifest: dict
    gate_results: list[gates.GateResult] = field(default_factory=list)


# --------------------------------------------------------------------- 本体
def generate(
    base_path: str | Path,
    out_dir: str | Path,
    seed: int = 1,
    settings: cfg.Settings | None = None,
) -> Result:
    """1 文書を生成する。検証ゲートに落ちたら、**途中まで書いた出力は残さない**。"""
    out_root = Path(out_dir)
    suffix = doc_suffix((settings or cfg.Settings.of()).variant)
    doc_dir = out_root / f"{ba.load_base(base_path).content_id}-{suffix}"
    try:
        return _generate(base_path, out_dir, seed, settings)
    except BaseException:
        # 中途半端な文書をデータセットに残さない（描画だけ済んだ状態など）
        if doc_dir.is_dir():
            shutil.rmtree(doc_dir, ignore_errors=True)
        raise


def _generate(
    base_path: str | Path,
    out_dir: str | Path,
    seed: int = 1,
    settings: cfg.Settings | None = None,
) -> Result:
    settings = settings or cfg.Settings.of()
    base = ba.load_base(base_path)
    content_id = f"{base.content_id}-{doc_suffix(settings.variant)}"
    paths = lay.Paths(Path(out_dir), content_id).prepare()

    pages_before = ba.estimate_pages(base.data, base.genre)
    ctx = build_context(base, page_slack=settings.max_pages - pages_before)

    plan = selector.plan(ctx, seed, settings)
    if not plan.items:
        raise gates.GateFailure(
            [gates.GateResult("G0", "題材の選定", False, "この文書に足せる題材が無い: " + _why(plan))]
        )
    groups = selector.sample(ctx, seed, plan)
    traps: list[challenge.Trap] = []
    if settings.challenge:
        traps = challenge.inject(
            [d for g in groups for d in g], random.Random(f"{ctx.content_id}:{seed}:challenge")
        )
    groups, dropped = _fit_pages(ctx, base, groups, settings, pages_before)
    for key in dropped:
        plan.skipped.append((key, "ページの余裕が足りないので外した（G9b）"))
    if not groups:
        raise gates.GateFailure(
            [gates.GateResult("G0", "題材の選定", False, "下書きを作れた題材が無い: " + _why(plan))]
        )
    places = _allocate(ctx, groups, seed, settings)
    mods = {
        d.rule_id: presentation.assign(
            d,
            selector.presentation_rng(ctx, seed, _subj(plan, i), _pat(plan, i)),
            settings.profile.weights,
        )
        for i, g in enumerate(groups)
        for d in g
    }

    # --- 2 回に分けて組む（設例の値は仕様から計算するので、1 回目は囲みを作らない） ---
    # 分量の上限は**設例まで入れた最終形**で測り、超えていればルールを減らして組み直す。
    # 見積りではなく本体 lint の判定を使うので、「通るはずが通らない」が起きない。
    while True:
        first = _build_pass(ctx, groups, places, seed, mods, None, content_id)
        example_texts, example_pairs = _make_examples(ctx, first, groups, seed, settings)
        built = _build_pass(ctx, groups, places, seed, mods, example_texts, content_id)
        if len(groups) <= 1 or not _over_budget(built.draft):
            break
        dropped.append(groups[-1][0].subject_key)
        plan.skipped.append((groups[-1][0].subject_key, "本体 lint L09（分量の上限）に当たるので外した"))
        groups, places = groups[:-1], places[:-1]
    rs, doc, policy, draft = built.rs, built.doc, built.policy, built.draft

    results: list[gates.GateResult] = []
    results += gates.spec_gates(rs)
    results.append(gates.explicitness(rs, doc))
    results.append(
        gates.examples_match(
            rs, doc, example_pairs, {a["rule"]: a["explanatory_units"] for a in built.answer}
        )
    )
    results.append(
        gates.no_clash(
            base.data,
            {c.name: c.surface for g in groups for d in g for c in d.consts},
            {op["node"]["id"] for op in built.ops if op["op"] == "add_node"} | built.added_node_ids,
            built.added_block_ids,
            {d.benefit for g in groups for d in g},
            built.added_texts,
            ctx,
        )
    )
    gates.raise_if_failed(results)

    # --- 正解プログラムとテスト -------------------------------------------------
    module = f"calc_{content_id.replace('-', '_')}"
    source = codegen.compile_module(rs)
    ns: dict = {}
    exec(compile(source, f"{module}.py", "exec"), ns)  # noqa: S102
    case_rows, stats, mismatches = build_cases(content_id, rs, ns, settings, example_pairs)
    if traps:
        # 難所を入れた文書では、2 通りの読みで同じ結果になるケースだけを残す
        case_rows = challenge.filter_cases(rs, case_rows, traps)
    results.append(gates.implementation_matches(mismatches, len(case_rows)))
    results.append(gates.test_sufficiency(stats))
    gates.raise_if_failed(results)

    # --- 本体の検査 -------------------------------------------------------------
    findings = ba.lint(draft)
    results.append(gates.base_lint(findings, draft=draft))
    pages_after = ba.estimate_pages(draft, base.genre)
    rendered: int | None = None
    renders: list[dict] = []
    if settings.render:
        # 同じ `policy.json`・同じ `calc/` を、指定されたすべてのスタイルで描く（H3 (c)・S10-5）。
        #
        # **先頭（既定のスタイル）が通らなければ文書ごと失敗**にする。これが代表であり、
        # `layout.json` と回帰の基準になる。
        # **2 つ目以降が通らなかったら、そのスタイルだけ外して記録する。** 1 つの style が
        # 20 ページを超えるだけで文書を捨てると、スタイルを増やすほど文書が減ってしまい、
        # H3 (c)（文書数を増やさずデータを増やす）と逆になる。黙って外さず `plan.skipped`
        # と manifest に残す（DESIGN §2 の原則 7）。
        styles = _styles_for(base, settings)
        for i, style in enumerate(styles):
            info = ba.render(policy, paths.render_dir(f"{content_id}--{style}"), style, png=settings.png)
            checks = [
                gates.page_budget(pages_before, pages_after, info.pages, settings.max_pages),
                gates.base_verify(ba.verify(info.out_dir), info.notes),
            ]
            bad = [c for c in checks if not c.ok]
            if i == 0 or not bad:
                renders.append({"style": style, "pages": info.pages, "dir": info.out_dir})
                results += checks
                continue
            shutil.rmtree(info.out_dir, ignore_errors=True)
            plan.skipped.append((style, "このスタイルでは通らない: " + "; ".join(c.detail for c in bad)))
        # 代表（既定のスタイル）のページ数を manifest の `pages.rendered` に入れる
        rendered = renders[0]["pages"]
    else:
        results.append(gates.page_budget(pages_before, pages_after, rendered, settings.max_pages))
    results.append(gates.discoverable(doc, built.answer))
    gates.raise_if_failed(results)

    # --- 書き出し ---------------------------------------------------------------
    (paths.calc / "programs" / f"{module}.py").write_text(source, encoding="utf-8")
    lay.write_json(paths.policy, policy)
    lay.write_json(paths.calc / "spec.json", built.spec)
    lay.write_json(paths.calc / "patch.json", built.ops)
    answer = built.answer
    for tr in traps:
        for a in answer:
            if a["rule"] == tr.rule_id:
                a["trap"] = {"kind": tr.kind, "expect": tr.expect, "dropped": tr.dropped_obligation}
    lay.write_json(paths.calc / "answer_key.json", answer)
    lay.write_jsonl(paths.calc / "cases.jsonl", case_rows)
    for hint in taskcards.HINT_LEVELS:
        rows = taskcards.cards(rs, doc, content_id, hint, built.answer)
        name = "tasks.jsonl" if hint == "H0" else f"tasks_{hint}.jsonl"
        lay.write_jsonl(paths.calc / name, rows)
    (paths.calc / "tests" / "conftest.py").write_text(pytest_writer.conftest(module), encoding="utf-8")
    (paths.calc / "tests" / f"test_{module}.py").write_text(
        pytest_writer.test_module(policy["meta"]["title"], _date_args(rs)), encoding="utf-8"
    )

    manifest = {
        "content_id": content_id,
        "base_content_id": base.content_id,
        "genre": base.genre,
        "seed": seed,
        "generator_version": GENERATOR_VERSION,
        "spec_version": rs.version,
        "profile": settings.profile.name,
        "base": {"path": str(base.path.name), "style": base.style_id},
        "plan": {
            "rules": [d.rule_id for g in groups for d in g],
            "patterns": sorted({d.pattern for g in groups for d in g}),
            "skipped": [{"what": w, "why": y} for w, y in plan.skipped],
        },
        "added": patch_ops.summarize(built.ops),
        "pages": {"before": round(pages_before, 2), "after": round(pages_after, 2), "rendered": rendered},
        # 描いたスタイルとそのページ数（複数スタイルのときは全部入る。H3 (c)・S10-5）
        "renders": [{"style": r["style"], "pages": r["pages"]} for r in renders],
        "counts": {
            "rules": len(rs.rules),
            "cases": len(case_rows),
            "cases_by_kind": {
                k: sum(1 for c in case_rows if c["kind"] == k)
                for k in ("example", "boundary", "unknown", "random")
            },
        },
        "challenge": [
            {
                "rule": tr.rule_id,
                "kind": tr.kind,
                "expect": tr.expect,
                "dropped_obligation": tr.dropped_obligation,
                "note": tr.note,
            }
            for tr in traps
        ],
        "gates": gates.summarize(results),
        "files": lay.file_hashes(paths.doc),
    }
    lay.write_json(paths.calc / "manifest.json", manifest)
    return Result(content_id, paths.doc, manifest, results)


def _over_budget(draft: dict) -> bool:
    """本体 lint の L09（ページ数・文字数の上限）に当たっているか。"""
    return any(f.code == "L09" for f in ba.lint(draft))


def _fit_pages(
    ctx, base, groups: list[list], settings: cfg.Settings, before: float
) -> tuple[list[list], list[str]]:
    """ページ予算に収まるまでルールを減らす（減らしたことは必ず記録する。TASK.md S1-3）。

    黙って縮めない。収まらなければ空を返し、呼び出し側が明示的に失敗させる。
    """
    # 本体 lint L09 は「19 ページ超は error、genre の目標ページ超は warning」。どちらも出さない
    budget = min(settings.max_pages - 1, ba.target_pages(base.genre)[1])
    dropped: list[str] = []
    current = list(groups)
    while current:
        estimate = before + sum(_group_pages(g) for g in current)
        if estimate <= budget:
            return current, dropped
        last = current.pop()
        dropped.append(last[0].subject_key)
    return [], dropped


#: 1 ルールが使うページ数の見込み（本体の `estimate_pages` の係数に合わせた概算）
def _group_pages(group: list) -> float:
    pages = 0.0
    for d in group:
        pages += 0.22 + 0.05 * len(d.steps)
        if d.table is not None:
            pages += 0.12
        if d.figure is not None:
            pages += 0.18
        if d.example_sets:
            pages += 0.08
    return pages


# --------------------------------------------------------------------- 工程の部品
@dataclass
class _Built:
    ops: list[dict]
    spec: dict
    answer: list[dict]
    draft: dict
    policy: dict
    doc: Doc
    rs: RuleSet
    added_texts: list[str]
    added_node_ids: set[str]
    added_block_ids: set[str]


def _build_pass(
    ctx: Context,
    groups: list[list],
    places: list,
    seed: int,
    mods: dict[str, dict],
    example_texts: dict[str, list[str]] | None,
    content_id: str,
) -> _Built:
    """下書き → 条・別表・特約の実現 → パッチ適用 → `derived` 再計算 → 索引 → 仕様。"""
    ops: list[dict] = []
    spec: dict = {
        "spec_version": "0.2",
        "document": {"content_id": content_id, "genre": ctx.genre, "calc_seed": seed},
        "params": {},
        "tables": {},
        "rules": [],
    }
    answer: list[dict] = []
    rider_parent = patch_ops.rider_parent(ctx.data)
    for g, place in zip(groups, places, strict=True):
        rng = random.Random(f"{ctx.content_id}:{seed}:realize:{g[0].subject_key}:{g[0].pattern}")
        rz = discourse.realize(
            ctx,
            g,
            place.article_id,
            rng,
            example_values=example_texts,
            modalities=_merge_mods(mods, g),
            placement=place,
        )
        ops += rz.patch_ops
        ops += _place_ops(ctx, g, place, rz, rng, rider_parent)
        spec["params"].update(rz.spec_params)
        spec["tables"].update(rz.spec_tables)
        spec["rules"] += rz.spec_rules
        answer += rz.answer

    # 目的別もくじ・特約一覧は手書きの表なので、足した条を載せる行を加える（S3-5・S7-2）
    ops += placement.index_rows(
        ctx.data,
        [g[0] for g in groups],
        [p.article_id for p in places],
        [_place_title(ctx, g, p) for g, p in zip(groups, places, strict=True)],
    )
    ops += placement.rider_index_rows(ctx.data, places, [g[0] for g in groups])
    draft = patch_ops.apply(ctx.data, ops)
    draft["content_id"] = content_id
    policy = ba.rebuild(draft)
    doc = Doc.from_dict(policy)
    # 本文に書いた文を逐語の引用に直す（プレースホルダを解いたもの）
    spec = _resolve_sources(spec, doc)
    rs = RuleSet(spec, doc)
    added_texts, nodes, blocks = _added_strings(ops)
    return _Built(ops, spec, answer, draft, policy, doc, rs, added_texts, nodes, blocks)


def _place_ops(
    ctx: Context, group: list, place, rz, rng: random.Random, rider_parent: str | None
) -> list[dict]:
    """配置に応じた追加操作（条を章へ／別表を足す／特約として足す）。"""
    ops: list[dict] = []
    body = [rz.article] if rz.proviso_article is None else [rz.article, rz.proviso_article]
    if place.kind == "rider":
        scope = _rider_scope_article(place, group[0], rng)
        tail = _rider_tail_article(place, rng, n=2 + len(body))
        node = placement.rider_node(place.rider_id, place.rider_title, scope, [*body, tail])
        ops.append(patch_ops.add_node(rider_parent, node, target="body"))
        return ops
    chapter = ctx.anchor_node(group[0].anchor)
    for node in body:
        ops.append(patch_ops.add_node(chapter["id"], node))
    if place.kind == "appendix" and rz.appendix_table is not None:
        table = group[0].table
        # 別表の見出しは「◯◯表」、中の節の見出しは「キーと値」にする（既定の約款と同じ付け方）
        title = f"{table.value_header}表" if table else place.appendix_id
        section_title = f"{table.key_header}と{table.value_header}" if table else title
        lead = lex.sentence_appendix_lead(table.caption if table else title, rng)
        ops.append(
            patch_ops.add_node(
                None,
                placement.appendix_node(
                    place.appendix_id, title, section_title, "別表", rz.appendix_table, lead
                ),
                target="appendices",
            )
        )
    return ops


def _rider_scope_article(place, draft, rng: random.Random) -> dict:
    """特約の第1条（適用条件）。既定の約款の特約が必ず持つ形にそろえる。"""
    from .realize import blocks as bk

    aid = f"{place.rider_id}_a1"
    s = lex.sentence_rider_scope(draft.benefit, rng)
    return bk.node(
        aid,
        "article",
        title="この特約の適用条件",
        children=[bk.node(f"{aid}_p1", "paragraph", text=s.text)],
    )


def _rider_tail_article(place, rng: random.Random, n: int = 3) -> dict:
    """特約の末尾の条（主約款の準用）。`n` は特約の中で何番目の条か。

    但し書きを別の条に分けると条が 1 本増えるので、準用の条は 1 つ繰り下がる
    （IDが `_a3` でぶつかり、G2 で「引用が原文に無い」として出ていた）。
    """
    from .realize import blocks as bk

    aid = f"{place.rider_id}_a{n}"
    s = lex.sentence_rider_fallback(rng)
    return bk.node(
        aid,
        "article",
        title="普通保険約款の準用",
        children=[bk.node(f"{aid}_p1", "paragraph", text=s.text)],
    )


def _place_title(ctx: Context, group: list, place) -> str:
    """目的別もくじの「お読みいただく条項」欄に書く見出し。"""
    if place.kind == "rider":
        return place.rider_title
    return (ctx.anchor_node(group[0].anchor) or {}).get("title", "")


def _merge_mods(mods: dict[str, dict], group: list) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for d in group:
        out.update(mods.get(d.rule_id, {}))
    return out


def _resolve_sources(spec: dict, doc: Doc) -> dict:
    """`raw`（プレースホルダつきの原文）→ `quote`（表示文字列）に直す。"""

    def fix(src: dict) -> dict:
        out = {"unit": src["unit"]}
        if "raw" in src:
            # `{ref:}` の表示はその単位から見た相対表記なので、単位を渡して解決する
            out["quote"] = doc.resolve(src["raw"], from_id=src["unit"])
        return out

    spec = json.loads(json.dumps(spec, ensure_ascii=False))
    for p in spec["params"].values():
        if "source" in p:
            p["source"] = fix(p["source"])
    for r in spec["rules"]:
        r["sources"] = [fix(s) for s in r["sources"]]
        for ex in r.get("examples", []):
            if "source" in ex:
                ex["source"] = fix(ex["source"])
        _resolve_input_descs(r, doc)
    return spec


def _resolve_input_descs(rule: dict, doc: Doc) -> None:
    """入力の説明文に残ったプレースホルダを表示文字列に直す。

    説明文は `{t:車}` → `{term:insured_car}` の形で作られる。約款本文なら本体の build が
    解決するが、**`spec.json` と `tasks.jsonl` は RichText ではない**ので誰も解決しない。
    放っておくと、評価対象システムに渡すタスクカードに
    「`{term:insured_car}`が自力で走行できない状態にあるかどうか」と出てしまう。
    表示文字列にならないだけでなく、**内部IDが漏れる**（`CLAUDE.md` 守ること 4）。
    G12（S10-3）で解き手に渡した出題を読んで見つけた。
    """
    for spec in rule.get("inputs", {}).values():
        if "desc" in spec:
            spec["desc"] = doc.resolve(spec["desc"])
    for coll in rule.get("collections", {}).values():
        for item in coll.get("fields", {}).values():
            if "desc" in item:
                item["desc"] = doc.resolve(item["desc"])


def _added_strings(ops: list[dict]) -> tuple[list[str], set[str], set[str]]:
    texts: list[str] = []
    nodes: set[str] = set()
    blocks: set[str] = set()

    def walk(v) -> None:
        if isinstance(v, str):
            texts.append(v)
        elif isinstance(v, dict):
            if v.get("kind") and v.get("id"):
                nodes.add(v["id"])
            if v.get("type") and v.get("id"):
                blocks.add(v["id"])
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    for op in ops:
        if op["op"] == "add_node":
            walk(op["node"])
        elif op["op"] == "add_block":
            walk(op["block"])
    return texts, nodes, blocks


def _allocate(
    ctx: Context, groups: list[list], seed: int, settings: cfg.Settings
) -> list[placement.Placement]:
    """条・別表・特約のIDを前もって払い出す（既定の命名規則に従う）。

    配置はプロファイルの `scatter` で決める。分散させるほど根拠単位が離れ、難しくなる
    （DESIGN.md §8.5・§9.1）。
    """
    counters: dict[str, int] = {}
    used_appendix: list[str] = []
    out: list[placement.Placement] = []
    data = ctx.data
    can_rider = patch_ops.rider_parent(data) is not None or True
    for g in groups:
        chapter = ctx.anchor_node(g[0].anchor)
        if chapter is None:
            raise gates.GateFailure(
                [gates.GateResult("G0", "追加先の章", False, f"{g[0].anchor} に対応する章が無い")]
            )
        rng = random.Random(f"{ctx.content_id}:{seed}:placement:{g[0].subject_key}")
        kind = placement.choose(g[0], rng, settings.profile.scatter, can_rider)
        proviso = placement.choose_proviso(g, rng, settings.profile.scatter)
        if kind == "rider":
            try:
                rider_id = patch_ops.next_rider_id(data, g[0].subject_key)
            except patch_ops.PatchError:
                kind = "article"
            else:
                out.append(
                    placement.Placement(
                        kind="rider",
                        article_id=f"{rider_id}_a2",
                        parent_id=rider_id,
                        rider_id=rider_id,
                        rider_title=lex.rider_title(g[0].benefit),
                        proviso=proviso,
                        # 特約の中は 第1条=適用条件 / 第2条=本体 / 第3条=但し書き / 末尾=準用
                        proviso_article_id=f"{rider_id}_a3" if proviso == "article" else None,
                    )
                )
                continue
        cid = chapter["id"]
        if cid not in counters:
            _aid, n = patch_ops.next_article_id(chapter)
            counters[cid] = n
        aid = f"{cid}_a{counters[cid]}"
        counters[cid] += 1
        # 但し書きを別の条に分けるなら、その条のIDも同じ章から払い出す（分散。DESIGN §8.5）
        proviso_aid = None
        if proviso == "article":
            proviso_aid = f"{cid}_a{counters[cid]}"
            counters[cid] += 1
        app_id = None
        if kind == "appendix":
            app_id = _next_appendix(data, used_appendix, ba.reserved_appendix_ids(ctx.genre))
            used_appendix.append(app_id)
        out.append(
            placement.Placement(
                kind=kind,
                article_id=aid,
                parent_id=cid,
                appendix_id=app_id,
                proviso=proviso,
                proviso_article_id=proviso_aid,
            )
        )
    return out


def _next_appendix(data: dict, used: list[str], reserved: set[str]) -> str:
    """まだ使っていない別表のID。blueprint が予約しているIDは避ける（本体 lint L04）。"""
    n = int(patch_ops.next_appendix_id(data)[3:])
    while f"app{n}" in used or f"app{n}" in reserved:
        n += 1
    return f"app{n}"


def _make_examples(
    ctx: Context, built: _Built, groups: list[list], seed: int, settings: cfg.Settings
) -> tuple[dict[str, list[str]], dict[str, list[tuple[dict, object]]]]:
    """設例の文と (入力, 期待値) を作る。表記が既存の定数とぶつかる候補は捨てる。"""
    texts: dict[str, list[str]] = {}
    pairs: dict[str, list[tuple[dict, object]]] = {}
    skipped_examples: list[str] = []
    own = {c.name: c.surface for g in groups for d in g for c in d.consts}
    surfaces = set(ctx.const_surfaces) | set(own.values())
    for g in groups:
        for d in g:
            if not d.example_sets or d.rule_id not in built.rs.rules:
                continue
            chosen = None
            fallback = None
            for k, candidate in enumerate(_example_candidates(d, settings)):
                rng = random.Random(f"{ctx.content_id}:{seed}:example:{d.rule_id}:{k}")
                cand_texts, cand_pairs = examples.texts_for(built.rs, d.rule_id, candidate, own, rng)
                if examples.collides(cand_texts, surfaces) is not None:
                    continue
                fallback = fallback or (cand_texts, cand_pairs)
                # 設例は違う結果になる組を選ぶ（同じ額ばかりでは説明にならない）
                if len({v for _c, v in cand_pairs}) == len(cand_pairs):
                    chosen = (cand_texts, cand_pairs)
                    break
            chosen = chosen or fallback
            if chosen is None:
                # 表記の衝突（本体 lint L11）を避けられない題材は設例を付けない。黙って落とさず記録する
                skipped_examples.append(d.rule_id)
                continue
            texts[d.rule_id], pairs[d.rule_id] = chosen
    return texts, pairs


def _example_candidates(draft, settings: cfg.Settings) -> list[list[dict]]:
    """設例の入力の候補。パターンが並べた候補に、金額を少しずつずらした候補を足す。

    本体 lint L11 は「定数の表記が素の文字列で現れる」ことを警告する。
    表記は部分文字列で当たる（定数「5万円」に対して「375万円」が当たる）ので、
    当たらない数値に行き当たるまで候補を変える。
    """
    n = max(1, settings.profile.examples)
    out = [c[:n] for c in draft.example_sets]
    base = out[0] if out else []
    for delta in (1_000, 2_000, 3_000, -1_000, -2_000, 5_000, -5_000, 7_000, -7_000, 11_000):
        shifted = []
        for case in base:
            row = dict(case)
            for name, value in case.items():
                spec = draft.inputs.get(name, {})
                if value is not None and spec.get("type") == "int" and spec.get("unit") == "JPY":
                    lo, hi = int(spec.get("min", 0)), int(spec.get("max", 10**9))
                    row[name] = max(lo, min(hi, value + delta))
            shifted.append(row)
        out.append(shifted)
    return out


def build_cases(
    content_id: str,
    rs: RuleSet,
    ns: dict,
    settings: cfg.Settings,
    example_pairs: dict[str, list[tuple[dict, object]]],
) -> tuple[list[dict], dict, list[str]]:
    """境界値・不明値・乱数・設例のケースを作り、正解プログラムとの一致を確かめる。"""
    rows: list[dict] = []
    stats: dict[str, dict] = {}
    mismatches: list[str] = []
    for rid, rule in rs.rules.items():
        rng = random.Random(f"{content_id}:{rid}:cases")
        expr = rs.full_expr(rid)
        fname = rs.function_of(rid)
        fn = ns[fname]
        pool = tc.boundary_cases(rs, rid, expr)
        known = [c for c in pool if all(v is not None for v in c.values())]
        unknown = [c for c in pool if any(v is None for v in c.values())]
        muts = mutation.mutants(rs, rid)
        alive, chosen = list(range(len(muts))), []
        # 不明値を含むケースも使う（「既定値を無視する」誤りは不明でないと見分けられない）
        for c in known + unknown:  # 変異をすべて検出できる境界値を貪欲に選ぶ
            if not alive:
                break
            y = interp._ev(rs, expr, c, None)
            killed = {m for m in alive if interp._ev(rs, muts[m][1], c, None) != y}
            if killed:
                chosen.append(c)
                alive = [m for m in alive if m not in killed]
        if alive:  # 境界値で検出できない変異は、乱数探索で検出できる入力を足す
            for c in tc.random_cases(rs, rid, 4000, seed=97):
                if any(v is None for v in c.values()):
                    continue
                y = interp._ev(rs, expr, c, None)
                killed = {m for m in alive if interp._ev(rs, muts[m][1], c, None) != y}
                if killed:
                    chosen.append(c)
                    alive = [m for m in alive if m not in killed]
                if not alive:
                    break
        for m in list(alive):  # それでも残る変異は、1 入力だけを densely 振って探す
            hit = tc.kill_search(rs, rid, expr, muts[m][1], chosen + known[:5])
            if hit is None:
                continue
            chosen.append(hit)
            y = interp._ev(rs, expr, hit, None)
            alive = [x for x in alive if interp._ev(rs, muts[x][1], hit, None) == y]
        plan: list[tuple[str, dict]] = [("example", c) for c, _v in example_pairs.get(rid, [])]
        plan += [("boundary", c) for c in chosen + rng.sample(known, min(6, len(known)))]
        if settings.unknown_cases:
            plan += [("unknown", c) for c in rng.sample(unknown, min(4, len(unknown)))]
        plan += [
            ("unknown" if any(v is None for v in c.values()) else "random", c)
            for c in tc.random_cases(rs, rid, settings.profile.random_cases)
        ]
        seen: set[str] = set()
        for kind, c in plan:
            key = tc._key(c)
            if key in seen:
                continue
            seen.add(key)
            expected = interp._ev(rs, expr, c, None)
            got = fn(**c)
            if got != expected:
                mismatches.append(f"{rid}: 正解プログラム {got} と参照インタプリタ {expected}（入力 {c}）")
            rows.append(
                {
                    "case_id": f"{content_id}:{fname}:{kind[0]}{len(seen):03d}",
                    "rule_id": rid,
                    "function": fname,
                    "kind": kind,
                    "inputs": _jsonable(c),
                    "expected": _jsonable(expected),
                    **({"expected_type": "date"} if rule["output"]["type"] == "date" else {}),
                }
            )
        stats[rid] = {
            "cases": len(seen),
            "mutants": len(muts),
            "killed": len(muts) - len(alive),
            "survivors": [muts[m][0] for m in alive],
        }
    return rows, stats, mismatches


def _jsonable(value):
    import datetime as dt

    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _date_args(rs: RuleSet) -> dict[str, list[str]]:
    out = {}
    for rid, r in rs.rules.items():
        dates = [n for n, s in r.get("inputs", {}).items() if s["type"] == "date"]
        if dates:
            out[rs.function_of(rid)] = dates
    return out


def _doc_id(content_id: str, base) -> str:
    style = base.style_id or ba.default_style(base.genre)
    return f"{content_id}--{style}"


def _styles_for(base, settings: cfg.Settings) -> list[str]:
    """描くスタイルの一覧。

    既定は 1 つ（既定の約款と同じスタイル、無ければ blueprint の既定）。
    `settings.styles` を渡すと**同じ内容を複数のレイアウトで描く**（`HITL.md` H3 (c)）。
    文書数を増やさずにレイアウト頑健性の評価データを増やすための軸である。
    """
    default = base.style_id or ba.default_style(base.genre)
    wanted = settings.styles or (cfg.EXTRA_STYLES.get(base.genre, ()) if settings.multi_style else ())
    if not wanted:
        return [default]
    # 既定のスタイルを先頭にそろえる（`layout.json` の代表と回帰の基準を固定するため）
    out = [default]
    out += [s for s in wanted if s != default]
    return out


def _why(plan: selector.Plan) -> str:
    return "; ".join(f"{w}: {y}" for w, y in plan.skipped) or "理由の記録なし"


def _subj(plan: selector.Plan, i: int):
    return plan.used[i][0]


def _pat(plan: selector.Plan, i: int):
    return plan.used[i][1]
