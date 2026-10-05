"""`icc` コマンド（DESIGN.md §13）。

    python -m insurance_contracts_calculation.cli generate --base ../content/auto-0001 --out out --seed 1
    python -m insurance_contracts_calculation.cli verify out/auto-0001-c1
    python -m insurance_contracts_calculation.cli eval --submission impl.py --data out/auto-0001-c1
    python -m insurance_contracts_calculation.cli lint-base ../content/auto-0001

`--base` は `content/<content_id>/` でも、描画済みの `source.json` でもよい。
省略したときは `--content-id` から本体のリポジトリを探す。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _add_generate(sub) -> None:
    p = sub.add_parser("generate", help="計算規定を足して計算パックを書き出す")
    p.add_argument("--base", help="既定の約款（content ディレクトリ か source.json）")
    p.add_argument("--content-id", help="--base を省くときの content_id")
    p.add_argument("--out", default="out", help="出力先（既定: out/）")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--profile", default="standard", help="basic / standard / hard")
    p.add_argument("--max-pages", type=int, default=20)
    p.add_argument("--no-render", action="store_true", help="PDF を描かない（検証の一部が飛ぶ）")
    p.add_argument("--no-png", action="store_true", help="PNG を出さない（速い）")
    p.add_argument("--challenge", action="store_true", help="ラベル付きの難所を入れる（DESIGN §9.3）")
    p.add_argument(
        "--variant",
        type=int,
        default=1,
        help="同じ既定の約款から作る何本目か（文書IDの接尾 -c1 / -c2 …）。"
        "番号だけでは中身が変わらないので、別の本にするには --seed も変える",
    )
    p.add_argument(
        "--styles",
        nargs="+",
        metavar="STYLE",
        help="描くレイアウト（例: nl-a4-2col-mincho nl-b5-2col-dense）。"
        "複数渡すと同じ内容を複数のレイアウトで描く（正解は共通）",
    )
    p.add_argument(
        "--multi-style",
        action="store_true",
        help="種目ごとの既定の追加スタイル（config.EXTRA_STYLES）でも描く",
    )
    p.add_argument(
        "--no-datacard",
        action="store_true",
        help="データカード（`dataset/data-card.md`）を更新しない。"
        "既定では、出力先に既にカードがあるときだけ書き直す",
    )
    p.add_argument("--quiet", action="store_true")


def _add_batch(sub) -> None:
    p = sub.add_parser("batch", help="複数の文書をまとめて生成する")
    p.add_argument("--content-ids", nargs="*", help="対象の content_id（省略すると種目から探す）")
    p.add_argument("--genres", nargs="*", help="対象の種目")
    p.add_argument("--per-genre", type=int, default=5, help="種目あたりの文書数")
    p.add_argument("--out", default="out")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--profile", default="standard")
    p.add_argument(
        "--profile-mix",
        nargs="+",
        metavar="PROFILE",
        help="種目ごとに順に配るプロファイル（例: basic standard hard）。難易度の 3 水準を入れる",
    )
    p.add_argument("--min-slack", type=float, default=3.0, help="必要なページ余裕")
    p.add_argument(
        "--styles",
        nargs="+",
        metavar="STYLE",
        help="描くレイアウト。複数渡すと同じ内容を複数のレイアウトで描く（正解は共通）",
    )
    p.add_argument(
        "--multi-style",
        action="store_true",
        help="種目ごとの既定の追加スタイル（config.EXTRA_STYLES）でも描く",
    )
    p.add_argument("--no-render", action="store_true")
    p.add_argument("--no-png", action="store_true")
    p.add_argument(
        "--variant",
        type=int,
        default=1,
        help="同じ既定の約款から作る何本目か（文書IDの接尾 -c1 / -c2 …）。"
        "2 以上では種を VARIANT_SEED_STEP ずつずらし、1 本目と中身が変わることを確かめる",
    )
    p.add_argument(
        "--no-datacard",
        action="store_true",
        help="データカード（`<出力先>/data-card.md`）を更新しない。既定では最後に書き直す",
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="icc", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    _add_generate(sub)
    _add_batch(sub)
    v = sub.add_parser("verify", help="出力に検証ゲートを再実行する")
    v.add_argument("target", help="出力先（out/<content_id>）")
    e = sub.add_parser("eval", help="提出プログラムを採点する")
    e.add_argument("--submission", required=True)
    e.add_argument("--data", required=True, help="出力先（out/<content_id>）")
    e.add_argument("--track", default="impl", choices=("discover", "impl", "e2e"))
    e.add_argument("--hint", default="H0", choices=("H0", "H1", "H2"))
    e.add_argument("--timeout", type=float, default=10.0)
    e.add_argument("--reading", help="読取結果JSON（--track e2e で要る。本体の prediction 形式）")
    e.add_argument("--report", help="レポートの書き出し先（.json / .md）")
    lb = sub.add_parser("lint-base", help="既定の約款にある計算規定を一覧にする")
    lb.add_argument("base", help="content ディレクトリ か source.json")
    pk = sub.add_parser("package", help="配布パッケージを組む（正解を含む。HITL.md H4 (c)。配布はしない）")
    pk.add_argument("target", help="データセットのディレクトリ（例: out/v2・dataset）")
    pk.add_argument("--out", required=True, help="出力先")
    pk.add_argument("--version", default="v2.0", help="配布物の版（既定: v2.0）")
    pk.add_argument(
        "--format",
        default="plain",
        choices=("plain", "hf"),
        help="plain=一般形 / hf=Hugging Face の作法に合わせる（既定: plain）",
    )
    pk.add_argument(
        "--license",
        dest="license_id",
        default=hf_default_license(),
        help=f"--format hf のライセンスタグ（既定: {hf_default_license()}。仮決め。HITL.md H11）",
    )
    pk.add_argument("--repo-id", default=None, help="--format hf の HF リポジトリID（カードの例文に出る）")
    pk.add_argument(
        "--no-png", action="store_true", help="--format hf でページ画像を同梱しない（約 1.7GB 減る）"
    )

    ex = sub.add_parser("export", help="公開パッケージを書き出す")
    ex.add_argument("target")
    ex.add_argument("--out", required=True)

    dc = sub.add_parser("datacard", help="データカード（dataset/data-card.md）を書く／鮮度を見る")
    dc.add_argument("action", choices=("update", "check"), help="update=書き出す / check=書き換えずに見る")
    dc.add_argument(
        "dataset", nargs="?", default="dataset", help="データセットのディレクトリ（既定: dataset）"
    )
    args = ap.parse_args(argv)

    if args.cmd == "generate":
        return _cmd_generate(args)
    if args.cmd == "batch":
        return _cmd_batch(args)
    if args.cmd == "verify":
        return _cmd_verify(args)
    if args.cmd == "eval":
        return _cmd_eval(args)
    if args.cmd == "lint-base":
        return _cmd_lint_base(args)
    if args.cmd == "package":
        return _cmd_package(args)
    if args.cmd == "export":
        return _cmd_export(args)
    if args.cmd == "datacard":
        return _cmd_datacard(args)
    return 1


def hf_default_license() -> str:
    """`--license` の既定値（`export/huggingface.py` が唯一の正）。"""
    from .export.huggingface import DEFAULT_LICENSE

    return DEFAULT_LICENSE


def _settings(args):
    from .config import Settings

    return Settings.of(
        args.profile,
        max_pages=args.max_pages if hasattr(args, "max_pages") else 20,
        render=not args.no_render,
        png=not args.no_png,
        challenge=bool(getattr(args, "challenge", False)),
        styles=tuple(getattr(args, "styles", None) or ()),
        multi_style=bool(getattr(args, "multi_style", False)),
        variant=int(getattr(args, "variant", 1) or 1),
    )


def _resolve_base(args) -> str:
    from . import base_adapter as ba

    if args.base:
        return args.base
    if args.content_id:
        return str(ba.find_base(args.content_id))
    raise SystemExit(
        "--base か --content-id のどちらかが必要（候補: " + ", ".join(ba.available_bases()[:5]) + " …）"
    )


def _cmd_generate(args) -> int:
    from .generate import generate
    from .verify.gates import GateFailure

    try:
        result = generate(_resolve_base(args), args.out, args.seed, _settings(args))
    except GateFailure as e:
        print(str(e), file=sys.stderr)
        return 2
    m = result.manifest
    if not args.no_datacard:
        # 出力先に既にカードがあるときだけ書き直す（`examples/` を汚さない）
        from .export.datacard import refresh_if_present

        refresh_if_present(Path(args.out))
    if args.quiet:
        print(result.content_id)
        return 0
    print(
        json.dumps(
            {k: m[k] for k in ("content_id", "seed", "profile", "plan", "added", "pages", "counts", "gates")},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _cmd_batch(args) -> int:
    from .batch import run_batch

    report = run_batch(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["failed"] == 0 else 2


def _cmd_verify(args) -> int:
    from .verify.recheck import recheck

    results = recheck(Path(args.target))
    for r in results:
        print(r)
    return 0 if all(r.ok for r in results) else 2


def _cmd_eval(args) -> int:
    from .evalkit.report import run_eval

    try:
        report = run_eval(
            Path(args.data),
            Path(args.submission),
            track=args.track,
            hint=args.hint,
            timeout=args.timeout,
            reading_path=Path(args.reading) if args.reading else None,
        )
    except (ValueError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 2
    if args.report:
        out = Path(args.report)
        if out.suffix == ".md":
            out.write_text(report["markdown"], encoding="utf-8")
        else:
            out.write_text(json.dumps(report["json"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(report["markdown"])
    return 0


def _cmd_lint_base(args) -> int:
    from .verify.lint_base import lint_base

    print(json.dumps(lint_base(args.base), ensure_ascii=False, indent=2))
    return 0


def _cmd_package(args) -> int:
    """配布パッケージを組む。**配布はしない**（push・アップロードは人の作業）。"""
    import json

    from .generate import GENERATOR_VERSION

    if args.format == "hf":
        from .export import huggingface as hf

        opts = hf.Options(
            version=args.version,
            generator_version=GENERATOR_VERSION,
            license_id=args.license_id,
            include_png=not args.no_png,
            **({"repo_id": args.repo_id} if args.repo_id else {}),
        )
        index = hf.build(Path(args.target), Path(args.out), opts)
        print(
            json.dumps(
                {
                    "out": args.out,
                    "format": "hf",
                    "license": index["license"],
                    "includes_page_images": index["includes_page_images"],
                    "canary": index["canary"],
                    **index["totals"],
                    "views": index["views"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if index["license"] == "other":
            print("※ ライセンスが未決（license: other）。公開前に人が決める（HITL.md H11）", flush=True)
        else:
            print(f"※ ライセンスは仮決めの {index['license']}。人が確認する（HITL.md H11）", flush=True)
    else:
        from .export.distribution import build

        index = build(
            Path(args.target), Path(args.out), version=args.version, generator_version=GENERATOR_VERSION
        )
        print(json.dumps({"out": args.out, **index["totals"]}, ensure_ascii=False, indent=2))
    print("※ 配布（push・アップロード）は行っていない。人が判断する（HITL.md H4）", flush=True)
    return 0


def _cmd_datacard(args) -> int:
    """データカードを書く（update）／鮮度を見る（check）。

    `check` は**書き換えない**。文書が無いディレクトリは「検査するものが無い」として
    0 で抜ける（`make check` を `dataset/` の無い環境でも通すため）。
    """
    from .export import datacard

    target = Path(args.dataset)
    if args.action == "update":
        if not datacard.documents_in(target):
            print(f"{target} に文書が無いのでカードを書かない", file=sys.stderr)
            return 1
        print(datacard.write_card(target))
        return 0
    if not datacard.documents_in(target):
        print(f"{target} に文書が無いので検査を飛ばす")
        return 0
    problems = datacard.check(target)
    for line in problems:
        print(line, file=sys.stderr)
    if problems:
        print(
            f"→ `python -m insurance_contracts_calculation.cli datacard update {target}` で作り直す",
            file=sys.stderr,
        )
        return 1
    print(f"{target}/{datacard.CARD_NAME} は最新")
    return 0


def _cmd_export(args) -> int:
    from .export.datasheet import export_public

    out = export_public(Path(args.target), Path(args.out))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
