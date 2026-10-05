"""contracts-calc CLI（標準ライブラリの argparse。DESIGN.md §15）。

実行例（contracts-calculation ディレクトリで）:
    PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli generate --all-bases --calc-seed 1 --out data
    PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli verify data/ots-0101
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import base_adapter as ba
from .generate import generate_one


def _refresh_exports(out_root: Path) -> None:
    """データを足したら README とデータカードを書き直す（docs/data_card.md §5）。"""
    from .export.datacard import write_card
    from .export.datasheet import write_datasheet

    if not any(out_root.glob("*/calc/manifest.json")):
        return
    print(f"{write_datasheet(out_root)} を書き直した")
    print(f"{write_card(out_root)} を書き直した")


def _cmd_generate(args: argparse.Namespace) -> int:
    bases: list[Path]
    if args.all_bases:
        bases = ba.list_v1_base_contents()
    elif args.base:
        bases = [Path(args.base)]
    else:
        print("ERROR: --base か --all-bases を指定する", file=sys.stderr)
        return 2
    out_root = Path(args.out)
    failed = 0
    for base in bases:
        result = generate_one(
            base,
            calc_seed=args.calc_seed,
            out_root=out_root,
            profile=args.profile,
            rules_min=args.rules_min,
            rules_max=args.rules_max,
            png=args.png,
            render=not args.no_render,
        )
        status = "OK " if result.ok else "NG "
        gate_summary = " ".join(
            f"{g.gate}:{'skip' if g.skipped else ('ok' if g.passed else 'NG')}" for g in result.gates
        )
        print(f"{status}{base.name} -> {result.content_id}  {gate_summary}")
        for note in result.notes:
            print(f"    note: {note.splitlines()[0][:160]}")
        if not result.ok:
            failed += 1
    _refresh_exports(out_root)
    return 1 if failed else 0


def _cmd_bind(args: argparse.Namespace) -> int:
    bases = ba.list_v1_base_contents() if args.all_bases else ([Path(args.base)] if args.base else [])
    if not bases:
        print("ERROR: --base か --all-bases を指定する", file=sys.stderr)
        return 2
    failed = 0
    for base in bases:
        result = generate_one(
            base,
            calc_seed=1,
            out_root=Path(args.out),
            png=args.png,
            render=not args.no_render,
            bind_only=True,
        )
        status = "OK " if result.ok else "NG "
        n_rules = len(json.loads((result.out_dir / "calc" / "answer_key.json").read_text(encoding="utf-8")))
        print(f"{status}{base.name}: bound ルール {n_rules} 件")
        if not result.ok:
            failed += 1
    _refresh_exports(Path(args.out))
    return 1 if failed else 0


def _cmd_verify(args: argparse.Namespace) -> int:
    out_dir = Path(args.dir)
    manifest = json.loads((out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))
    bad = [g for g in manifest["gates"] if not g["passed"]]
    for g in manifest["gates"]:
        mark = "skip" if g["skipped"] else ("ok" if g["passed"] else "NG")
        print(f"{g['gate']}: {mark}  {g['detail'][:120]}")
    return 1 if bad else 0


def _cmd_eval(args: argparse.Namespace) -> int:
    from .evalkit.discovery import score_discovery
    from .evalkit.report import aggregate, format_summary
    from .evalkit.runner import run_submission

    data_root = Path(args.data)
    docs = sorted(p for p in data_root.iterdir() if (p / "calc" / "manifest.json").is_file())
    if not docs:
        print("ERROR: 計算パックが見つからない", file=sys.stderr)
        return 2

    if args.track == "discovery":
        if not args.submission:
            print("ERROR: discovery には --submission <dir>（<cid>.json）が要る", file=sys.stderr)
            return 2
        total = {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        n = 0
        for doc in docs:
            sub = Path(args.submission) / f"{doc.name}.json"
            if not sub.is_file():
                print(f"{doc.name}: 提出なし")
                continue
            answer_key = json.loads((doc / "calc" / "answer_key.json").read_text(encoding="utf-8"))
            pred = json.loads(sub.read_text(encoding="utf-8"))
            score = score_discovery(pred.get("rules", []), answer_key)
            print(f"{doc.name}: P={score['precision']} R={score['recall']} F1={score['f1']}")
            for k in total:
                total[k] += score[k]
            n += 1
        if n:
            print("平均: " + " ".join(f"{k}={total[k] / n:.4f}" for k in total))
        return 0

    # track=impl
    doc_results: dict[str, dict] = {}
    for doc in docs:
        calc = doc / "calc"
        if args.oracle:
            module = min((calc / "programs").glob("calc_*.py"))
        else:
            module = Path(args.submission) / f"{doc.name}.py"
            if not module.is_file():
                print(f"{doc.name}: 提出なし（{module}）")
                continue
        rows = run_submission(calc, module, timeout=args.timeout)
        answer_key = json.loads((calc / "answer_key.json").read_text(encoding="utf-8"))
        doc_results[doc.name] = {"cases": rows, "answer_key": answer_key}
    agg = aggregate(doc_results)
    print(format_summary(agg))
    if args.report:
        Path(args.report).write_text(json.dumps(agg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"詳細: {args.report}")
    return 0 if agg["functions_passed"] == agg["functions_total"] else 1


def _cmd_datasheet(args: argparse.Namespace) -> int:
    """README とデータカードを対で書き出す（README だけ作り直す経路を塞ぐ）。"""
    from .export.datacard import write_card
    from .export.datasheet import write_datasheet

    print(f"{write_datasheet(Path(args.data))} を書き出した")
    print(f"{write_card(Path(args.data))} を書き出した")
    return 0


def _cmd_datacard(args: argparse.Namespace) -> int:
    from .export.datacard import check_card, write_card

    data_root = Path(args.data)
    if args.action == "update":
        print(f"{write_card(data_root)} を書き出した")
        return 0
    ok, detail = check_card(data_root)
    print(detail)
    return 0 if ok else 1


def _cmd_publish(args: argparse.Namespace) -> int:
    """Hugging Face 公開形を組み立てる（docs/hf_publish.md）。アップロードはしない。"""
    from .export.hf import build

    result = build(
        Path(args.data),
        Path(args.out),
        license_id=args.license,
        repo_id=args.repo_id,
        include_answers=not args.no_answers,
    )
    mb = result.total_bytes / 1024 / 1024
    answers = "同梱" if result.include_answers else "なし"
    print(
        f"{result.out_root}: {result.n_docs} 文書・{len(result.files)} ファイル・{mb:.1f} MB（正解: {answers}）"
    )
    for gate, passed, detail in result.gates:
        print(f"{gate}: {'ok' if passed else 'NG'}  {detail[:160]}")
    if result.license_id == "other":
        print("ライセンスは未決（HITL HC-3）。決まるまで公開しない。--license <id> で指定する。")
    if not result.ok:
        print("ERROR: 公開前ゲートが通っていない。公開しない。", file=sys.stderr)
        return 1
    print("アップロードは人間が行う（HITL HC-1）。")
    return 0


def _cmd_lint_base(args: argparse.Namespace) -> int:
    """既定の契約書の計算条項を点検する（読むだけ）。付与モードの照合と明示性の欠落を報告する。"""
    from .bindings.engine import bind_document
    from .bindings.raw import raw_text_map
    from .docmodel.index import DocumentIndex

    targets = [Path(args.content)] if args.content else ba.list_v1_base_contents()
    n_inc = n_exc = 0
    for content_dir in targets:
        idx = DocumentIndex.load(content_dir)
        included, excluded = bind_document(idx, raw_text_map(content_dir), set())
        print(f"== {content_dir.name}")
        for b in included:
            print(f"  [OK] {b.binding} @ {','.join(b.units)}（一義に計算できる）")
            n_inc += 1
        for e in excluded:
            print(f"  [欠] {e.binding} @ {e.unit}")
            for m in e.missing:
                print(f"       - {m}")
            n_exc += 1
    print(f"\n照合できて計算可能: {n_inc} 件 ／ 明示性が欠けて除外: {n_exc} 件")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="contracts-calc")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="既定の契約書に計算条項を追加して計算パックを作る")
    g.add_argument("--base", help="base の content ディレクトリ（本体の content/<cid>）")
    g.add_argument("--all-bases", action="store_true", help="v1 の 20 基準契約すべて")
    g.add_argument("--calc-seed", type=int, default=1)
    g.add_argument("--profile", choices=["basic", "standard", "hard", "challenge"], default="standard")
    g.add_argument("--out", default="data")
    g.add_argument("--rules-min", type=int, default=None)
    g.add_argument("--rules-max", type=int, default=None)
    g.add_argument("--png", action="store_true", help="PNG も出す（目視レビュー用）")
    g.add_argument("--no-render", action="store_true", help="PDF 描画を省く（テスト高速化用）")
    g.set_defaults(func=_cmd_generate)

    b = sub.add_parser(
        "bind", help="付与モードだけを実行する（追加なし。既定の契約書の条項に仕様を紐づける）"
    )
    b.add_argument("--base", help="base の content ディレクトリ（本体の content/<cid>）")
    b.add_argument("--all-bases", action="store_true", help="v1 の 20 基準契約すべて")
    b.add_argument("--out", default="data_bind")
    b.add_argument("--png", action="store_true")
    b.add_argument("--no-render", action="store_true")
    b.set_defaults(func=_cmd_bind)

    v = sub.add_parser("verify", help="生成済みの計算パックのゲート結果を表示する")
    v.add_argument("dir")
    v.set_defaults(func=_cmd_verify)

    e = sub.add_parser("eval", help="提出プログラム（または正解プログラム）を採点する")
    e.add_argument("--data", default="data")
    e.add_argument("--track", choices=["impl", "discovery"], default="impl")
    e.add_argument("--submission", help="提出ディレクトリ（impl: <cid>.py ／ discovery: <cid>.json）")
    e.add_argument("--oracle", action="store_true", help="正解プログラムを提出とみなして採点（満点の検査）")
    e.add_argument("--hint", choices=["H0", "H1", "H2"], default="H1", help="出題時のヒント水準（記録用）")
    e.add_argument("--timeout", type=int, default=60)
    e.add_argument("--report", help="集計 JSON の出力先")
    e.set_defaults(func=_cmd_eval)

    ds = sub.add_parser(
        "datasheet", help="データセットの説明書（README.md）とデータカードを実測値から生成する"
    )
    ds.add_argument("--data", default="data")
    ds.set_defaults(func=_cmd_datasheet)

    dc = sub.add_parser("datacard", help="データカード（data-card.md）の書き出しと鮮度の検査")
    dc.add_argument("action", choices=["update", "check"])
    dc.add_argument("--data", default="data")
    dc.set_defaults(func=_cmd_datacard)

    pb = sub.add_parser("publish", help="Hugging Face 公開形を組み立てる（アップロードはしない）")
    pb.add_argument("--data", default="dataset")
    pb.add_argument("--out", default="dist/hf")
    pb.add_argument("--license", default=None, help="SPDX 風の識別子（例 cc-by-4.0）。省略すると未決のまま")
    pb.add_argument("--repo-id", default="<owner>/<dataset>", help="カードの使用例に書く HF のリポジトリ名")
    pb.add_argument("--no-answers", action="store_true", help="正解（answers/・cases）を含めない")
    pb.set_defaults(func=_cmd_publish)

    lb = sub.add_parser("lint-base", help="既定の契約書の計算条項を点検する（読むだけ）")
    lb.add_argument("--content", help="本体の content/<cid>（省略時は v1 の 20 基準契約）")
    lb.set_defaults(func=_cmd_lint_base)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
