"""yakkan コマンド（CLAUDE.md §11）。

P0 では `doctor` のみ。以降のフェーズで scaffold / lint / build / render / verify / review / qa を足す。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="日本語保険約款の合成データ生成（yakkan-synth）", no_args_is_help=True)
console = Console()


@app.callback()
def main() -> None:
    """サブコマンド群（doctor / 以降のフェーズで追加）。"""


@app.command()
def doctor(
    chars: Annotated[
        bool, typer.Option("--chars/--no-chars", help="フォントの代表文字被覆表を表示する")
    ] = True,
) -> None:
    """実行環境（Python・WeasyPrint・Pango・フォント・pypdfium2）を検査する。"""
    from yakkan.env import run_all

    report, coverage_table = run_all()

    table = Table(title="yakkan doctor — 環境検査", title_justify="left", header_style="bold")
    table.add_column("項目", no_wrap=True)
    table.add_column("結果", no_wrap=True, justify="center")
    table.add_column("詳細")
    for check in report.checks:
        mark = "[green]OK[/green]" if check.ok else "[red]NG[/red]"
        detail = (
            check.detail if check.ok or not check.hint else f"{check.detail}\n[yellow]→ {check.hint}[/yellow]"
        )
        table.add_row(check.name, mark, detail)
    console.print(table)

    if chars and coverage_table:
        from yakkan.fonts import REPRESENTATIVE_CHARS

        n = len(REPRESENTATIVE_CHARS)
        cov = Table(
            title=f"フォント別 cmap 被覆（代表文字 {n} 字：{''.join(REPRESENTATIVE_CHARS)}）",
            title_justify="left",
            header_style="bold",
        )
        cov.add_column("フォント", no_wrap=True)
        cov.add_column("ファイル", no_wrap=True)
        cov.add_column("被覆", justify="right", no_wrap=True)
        cov.add_column("欠落文字")
        for spec, covered in coverage_table:
            missing = [c for c, ok in covered.items() if not ok]
            hit = n - len(missing)
            color = "green" if not missing else "yellow"
            cov.add_row(
                spec.family,  # type: ignore[attr-defined]
                spec.filename,  # type: ignore[attr-defined]
                f"[{color}]{hit}/{n}[/{color}]",
                " ".join(missing) if missing else "[dim]なし[/dim]",
            )
        console.print(cov)
        console.print(
            "[dim]記号フォントは記号専用のため欠落が多いのが正常。本文フォントが全字を持てば豆腐は出ない。[/dim]"
        )

    if report.failed:
        console.print(f"[red]NG {len(report.failed)} 件[/red]：" + "、".join(c.name for c in report.failed))
        raise typer.Exit(code=1)
    console.print("[green]すべて OK[/green]")


if __name__ == "__main__":
    app()


@app.command("schema")
def schema_cmd(
    action: Annotated[str, typer.Argument(help="export のみ")] = "export",
    out_dir: Annotated[Path, typer.Option("--out", help="出力先ディレクトリ")] = Path("schema"),
) -> None:
    """JSON Schema（2020-12）を `schema/*.schema.json` に書き出す。"""
    import json

    from yakkan.models import EXPORTED_SCHEMAS, json_schema

    if action != "export":
        console.print(f"[red]未知の操作: {action}[/red]（export のみ）")
        raise typer.Exit(code=2)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, model in EXPORTED_SCHEMAS.items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(
            json.dumps(json_schema(model), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        console.print(f"書き出し: {path}")


@app.command()
def lint(
    content_dir: Annotated[Path, typer.Argument(help="content/<content_id> のパス")],
    quick: Annotated[bool, typer.Option("--quick", help="重いルール（フォント被覆）を飛ばす")] = False,
    only: Annotated[
        list[str] | None, typer.Option("--only", help="実行するルール番号（例 --only L01 --only L03）")
    ] = None,
    skip: Annotated[
        list[str] | None, typer.Option("--skip", help="外すルール番号（抜粋の検査では --skip L04 など）")
    ] = None,
    similarity: Annotated[
        bool,
        typer.Option(
            "--similarity/--no-similarity",
            help="L15（既存 content との文単位の重複率）を実行する。既定は実行する",
        ),
    ] = True,
) -> None:
    """執筆物を検査する（CLAUDE.md §8）。error が 1 件でもあれば非ゼロ終了。"""
    from yakkan.lint.runner import lint_content, summarize

    exclude = list(skip) if skip else []
    if not similarity:
        exclude.append("L15")
    findings = lint_content(
        content_dir,
        quick=quick,
        only=list(only) if only else None,
        exclude=exclude or None,
    )
    for finding in findings:
        color = "red" if finding.severity == "error" else "yellow"
        console.print(f"[{color}]{finding.format()}[/{color}]")
    errors, warnings = summarize(findings)
    if errors:
        console.print(f"[red]error {errors} 件[/red] / warn {warnings} 件")
        raise typer.Exit(code=1)
    console.print(f"[green]error 0 件[/green] / warn {warnings} 件")


@app.command()
def build(
    content_dir: Annotated[Path, typer.Argument(help="content/<content_id> のパス")],
) -> None:
    """執筆物に derived を付けて `source.json` を書き出す。"""
    from yakkan.build import build_content

    source = build_content(content_dir)
    d = source.derived
    console.print(
        f"[green]build 完了[/green] {content_dir / 'source.json'}\n"
        f"  ラベル {len(d.labels)} / 参照 {len(d.refs)} / 用語 {len(d.term_uses)}"
        f" / 脚注 {len(d.footnote_index)}\n"
        f"  平文 {len(d.plain_text)} / 表 {len(d.tables)} / 図 {len(d.figures)} / 目次 {len(d.toc)} 行"
    )


@app.command()
def render(
    content_dir: Annotated[Path, typer.Argument(help="content/<content_id> のパス")],
    style: Annotated[
        str | None,
        typer.Option("--style", help="styles/<style_id>.yaml。省略すると blueprint の default_style"),
    ] = None,
    out_root: Annotated[Path, typer.Option("--out", help="出力先の親（既定 dataset/）")] = Path("dataset"),
    report: Annotated[bool, typer.Option("--report", help="章ごとの使用ページを表示する")] = False,
    png: Annotated[bool, typer.Option("--png/--no-png", help="150dpi の PNG を出す")] = True,
) -> None:
    """content を描画して `dataset/<doc_id>/` を作る。"""
    import json as _json

    from yakkan.build import build_content
    from yakkan.models import Source
    from yakkan.render.weasy import page_report, render_source
    from yakkan.styles import load_style

    source_path = content_dir / "source.json"
    if source_path.is_file():
        source = Source.model_validate(_json.loads(source_path.read_text(encoding="utf-8")))
    else:
        console.print("[yellow]source.json が無いので build から実行する[/yellow]")
        source = build_content(content_dir)

    # style を省いたら **そのジャンルの blueprint の default_style** を使う。
    # 固定値を既定にしていたため、B5 のジャンルが A4 で描かれる事故が起きた。
    if style is None:
        from yakkan.blueprints import load_blueprint

        style = load_blueprint(source.genre).default_style
        console.print(f"[dim]style 未指定のため blueprint の既定を使う: {style}[/dim]")
    style_obj = load_style(style)
    doc_id = f"{source.content_id}--{style_obj.style_id}"
    from yakkan.render.weasy import RenderLayoutError

    try:
        result = render_source(source, style_obj, out_root / doc_id, render_png=png)
    except RenderLayoutError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[green]render 完了[/green] {result.out_dir} / {result.page_count} ページ")
    for note in result.notes:
        console.print(f"  [yellow]note[/yellow] {note}")
    if result.page_count > 20:
        console.print("[red]ページ数が 20 を超えている（CLAUDE.md §0.4-5）[/red]")
        raise typer.Exit(code=1)

    if report:
        table = Table(title="章ごとの使用ページ", title_justify="left", header_style="bold")
        table.add_column("id", no_wrap=True)
        table.add_column("見出し")
        table.add_column("開始", justify="right")
        table.add_column("終了", justify="right")
        table.add_column("ページ数", justify="right")
        for element_id, heading, start, end in page_report(result, source):
            table.add_row(element_id, heading, str(start), str(end), str(end - start + 1))
        console.print(table)


@app.command()
def verify(
    dataset_dir: Annotated[Path, typer.Argument(help="dataset/<doc_id> のパス")],
    determinism: Annotated[
        bool, typer.Option("--determinism/--no-determinism", help="2 回描画して一致を見る")
    ] = True,
) -> None:
    """生成物を検証する（docs/rendering.md §6.9）。"""
    import json as _json
    import tempfile

    from yakkan.models import Source
    from yakkan.styles import load_style
    from yakkan.verify.checks import check_determinism, verify_dataset

    results = verify_dataset(dataset_dir)
    if determinism:
        source = Source.model_validate(_json.loads((dataset_dir / "source.json").read_text(encoding="utf-8")))
        layout = _json.loads((dataset_dir / "layout.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            results += check_determinism(source, load_style(layout["style_id"]), Path(tmp))

    for r in results:
        color = "red" if r.severity == "error" else "yellow"
        console.print(f"[{color}]{r.format()}[/{color}]")
    errors = sum(1 for r in results if r.severity == "error")
    warns = len(results) - errors
    if errors:
        console.print(f"[red]error {errors} 件[/red] / warn {warns} 件")
        raise typer.Exit(code=1)
    console.print(f"[green]verify 通過[/green]（error 0 件 / warn {warns} 件）")


def _localize_authored(items: list, answer) -> list:
    """執筆 QA の**スタイル依存の値**を、この描画結果に合わせて付け直す。

    執筆 QA は content 側（スタイル非依存）に置くが、`page_hint` と
    `locate` の答え（ページ番号）は描画するスタイルによって変わる。
    書かれた値をそのまま使うと、別スタイルで描いたときに L14 が warn を出す。
    どちらも `evidence` から機械的に決まるので、ここで上書きする。
    """
    for item in items:
        pages: set[int] = set()
        for element_id in item.evidence:
            element = answer.layout.elements.get(element_id)
            if element:
                pages.update(f.page for f in element.fragments)
        if pages:
            item.page_hint = sorted(pages)
            if item.type == "locate" and item.answer_type == "number":
                item.answer = float(min(pages))
    return items


def _load_authored(content_id: str, qa_path: Path, content_root: Path = Path("content")) -> list:
    """執筆 QA を読む。`content/<cid>/qa_authored.json` が正、無ければ既存 qa.json から引き継ぐ。"""
    from yakkan.models import QA, QASet

    authored_path = content_root / content_id / "qa_authored.json"
    if authored_path.exists():
        data = json.loads(authored_path.read_text(encoding="utf-8"))
        items = data.get("items", data) if isinstance(data, dict) else data
        out = []
        for index, raw in enumerate(items, start=1):
            raw.setdefault("source", "authored")
            raw.setdefault("id", f"qa_auth_{index:03d}")
            out.append(QA.model_validate(raw))
        return out
    if qa_path.exists():
        existing = QASet.model_validate_json(qa_path.read_text(encoding="utf-8"))
        return [item for item in existing.items if item.source == "authored"]
    return []


@app.command()
def qa(
    doc_dir: Annotated[Path, typer.Argument(help="dataset/<doc_id> のパス")],
    count: Annotated[int, typer.Option("--count", help="自動生成する問数")] = 30,
    seed: Annotated[int, typer.Option("--seed", help="出題の選択に使う乱数種")] = 0,
    validate_only: Annotated[
        bool, typer.Option("--validate", help="生成せず、既存の qa.json を検証するだけ")
    ] = False,
    report: Annotated[bool, typer.Option("--report", help="種別ごとに作れる候補の数を表示する")] = False,
) -> None:
    """`answer.json` を作り、自動 QA を生成して検証する（CLAUDE.md §11）。

    執筆 QA は **`content/<content_id>/qa_authored.json`** に置く。
    `dataset/` は生成物で手編集を禁じている（§0.4-3）ので、執筆した問いは content 側に持ち、
    ここで自動 QA と合流させる。content 側に無ければ、既存 `qa.json` の
    `source: "authored"` を引き継ぐ（移行のための後方互換）。
    """
    from yakkan.answer import build_answer
    from yakkan.models import Layout, QASet, Source, dump_json
    from yakkan.qa.auto import generate, pool_sizes
    from yakkan.qa.validate import validate as run_validate

    source_path = doc_dir / "source.json"
    layout_path = doc_dir / "layout.json"
    if not source_path.exists() or not layout_path.exists():
        console.print(f"[red]{doc_dir} に source.json / layout.json が無い[/red]")
        raise typer.Exit(code=2)

    source = Source.model_validate_json(source_path.read_text(encoding="utf-8"))
    layout = Layout.model_validate_json(layout_path.read_text(encoding="utf-8"))
    answer = build_answer(source, layout)

    qa_path = doc_dir / "qa.json"
    if validate_only:
        if not qa_path.exists():
            console.print(f"[red]{qa_path} が無い[/red]")
            raise typer.Exit(code=2)
        qa_set = QASet.model_validate_json(qa_path.read_text(encoding="utf-8"))
    else:
        dump_json(answer, doc_dir / "answer.json")
        authored = _localize_authored(_load_authored(source.content_id, qa_path), answer)
        generated = generate(answer, count=count, seed=seed)
        qa_set = QASet(doc_id=answer.doc_id, items=generated.items + authored)
        dump_json(qa_set, qa_path)

    if report:
        table = Table(title="種別ごとの候補数", title_justify="left", header_style="bold")
        table.add_column("type")
        table.add_column("候補", justify="right")
        table.add_column("採用", justify="right")
        picked: dict[str, int] = {}
        for item in qa_set.items:
            picked[item.type] = picked.get(item.type, 0) + 1
        for key, size in sorted(pool_sizes(answer, seed=seed).items()):
            table.add_row(key, str(size), str(picked.get(key, 0)))
        console.print(table)

    findings = run_validate(qa_set, answer)
    for finding in findings:
        color = "red" if finding.severity == "error" else "yellow"
        console.print(f"[{color}]{finding}[/{color}]")
    errors = sum(1 for f in findings if f.severity == "error")
    warns = len(findings) - errors
    auto = sum(1 for i in qa_set.items if i.source == "auto")
    authored_count = len(qa_set.items) - auto
    summary = f"QA {len(qa_set.items)} 問（自動 {auto} / 執筆 {authored_count}）"
    if errors:
        console.print(f"[red]{summary} / error {errors} 件 / warn {warns} 件[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]{summary} / error 0 件 / warn {warns} 件[/green]")


@app.command()
def scaffold(
    genre: Annotated[str, typer.Option("--genre", help="blueprints/<genre>.yaml")],
    content_id: Annotated[str, typer.Option("--content-id", help="例 auto-0001")],
    seed: Annotated[int, typer.Option("--seed", help="バリアントの選択に使う乱数種")] = 1,
) -> None:
    """blueprint から執筆用スケルトンを作る（CLAUDE.md §7.2-1）。"""
    from yakkan.scaffold import scaffold as run

    result = run(genre, content_id, seed)
    console.print(
        f"[green]scaffold 完了[/green] {result.content_dir}\n"
        f"  埋める箇所 {result.todo_count} 件 / part {len(result.parts)} ファイル"
    )
    for note in result.notes:
        console.print(f"  [yellow]note[/yellow] {note}")


@app.command()
def batch(
    spec: Annotated[Path, typer.Argument(help="specs/<name>.yaml")],
    only: Annotated[str | None, typer.Option("--only", help="この content_id だけ処理する")] = None,
    content_root: Annotated[Path, typer.Option("--content", help="content/ のパス")] = Path("content"),
    dataset_root: Annotated[Path, typer.Option("--dataset", help="dataset/ のパス")] = Path("dataset"),
) -> None:
    """spec に並べた content を lint → build → render → verify → qa で一括生成する。

    **失敗しても止まらない。** 最後に段別・原因別の内訳を出すので、
    そのまま `docs/progress.md` に転記できる（CLAUDE.md §12 P5）。
    """
    from yakkan.batch import run as run_batch

    result = run_batch(spec, content_root=content_root, dataset_root=dataset_root, only=only)

    table = Table(title=f"batch {result.name}", title_justify="left", header_style="bold")
    for column, justify in (
        ("content_id", "left"),
        ("genre", "left"),
        ("style", "left"),
        ("頁", "right"),
        ("QA", "right"),
        ("status", "left"),
        ("落ちた段/理由", "left"),
    ):
        table.add_column(column, justify=justify)
    for row in result.results:
        color = {"ready": "green", "failed": "red"}.get(row.status, "yellow")
        note = ""
        if row.status != "ready":
            note = f"{row.stage}: {row.reason[:70]}"
        table.add_row(
            row.content_id,
            row.genre,
            row.style_id,
            str(row.pages or ""),
            str(row.qa_count or ""),
            f"[{color}]{row.status}[/{color}]",
            note,
        )
    console.print(table)

    if result.failed:
        stages = Table(title="失敗の内訳", title_justify="left", header_style="bold")
        stages.add_column("段")
        stages.add_column("件数", justify="right")
        for stage, count in result.by_stage().most_common():
            stages.add_row(stage, str(count))
        console.print(stages)
        reasons = Table(title="原因別", title_justify="left", header_style="bold")
        reasons.add_column("原因")
        reasons.add_column("件数", justify="right")
        for reason, count in result.by_reason().most_common():
            reasons.add_row(reason, str(count))
        console.print(reasons)

    ready = len(result.ready)
    total = len(result.results)
    skipped = sum(1 for r in result.results if r.status == "skipped")
    summary = f"ready {ready}/{total}（skipped {skipped}）"
    if result.failed:
        console.print(f"[red]{summary} / failed {len(result.failed)}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]{summary}[/green]")


@app.command()
def clean(
    doc_ids: Annotated[
        list[str] | None,
        typer.Argument(help="消す doc_id（例 quake-0001--nl-a4-2col-mincho）。省略時は --stale が必要"),
    ] = None,
    dataset_dir: Annotated[Path, typer.Option("--dataset", help="dataset/ のパス")] = Path("dataset"),
    stale: Annotated[
        bool,
        typer.Option("--stale", help="content/ と blueprint の宣言スタイルから外れた生成物をすべて消す"),
    ] = False,
) -> None:
    """`dataset/<doc_id>/` を消す（生成物の掃除）。

    スタイルを差し替えたり content を消したりすると、古い `dataset/<doc_id>/` が残る。
    手で消すと `dataset/` の手編集禁止（CLAUDE.md §0.4-3）と区別がつかないので、
    **掃除もコマンドで行う**。消すのはディレクトリ単位だけで、中身の部分編集はしない。
    """
    import shutil

    from yakkan.blueprints import load_blueprint

    targets: list[Path] = []
    if stale:
        wanted: set[str] = set()
        for doc_json in sorted(Path("content").glob("*/doc.json")):
            data = json.loads(doc_json.read_text(encoding="utf-8"))
            content_id = data["content_id"]
            try:
                blueprint = load_blueprint(data["genre"])
            except FileNotFoundError:
                continue
            styles = list(getattr(blueprint.variants, "styles", None) or [blueprint.default_style])
            wanted.update(f"{content_id}--{style}" for style in styles)
        for path in sorted(dataset_dir.iterdir()):
            if path.is_dir() and path.name not in wanted:
                targets.append(path)
    for doc_id in doc_ids or []:
        # `dataset/<doc_id>` と打たれても効くようにする（黙って何も消さないと事故になる）
        name = Path(doc_id).name if Path(doc_id).parent.name == dataset_dir.name else doc_id
        path = dataset_dir / name
        if not path.is_dir():
            console.print(f"[yellow]見つからない: {path}[/yellow]")
        if path.is_dir() and path not in targets:
            targets.append(path)

    if not targets:
        console.print("消すものはない")
        return
    for path in targets:
        shutil.rmtree(path)
        console.print(f"削除: {path}")
    console.print(
        f"[green]{len(targets)} 件削除した。`yakkan manifest update` で一覧を作り直すこと。[/green]"
    )


@app.command()
def manifest(
    action: Annotated[str, typer.Argument(help="update のみ")] = "update",
    dataset_dir: Annotated[Path, typer.Option("--dataset", help="dataset/ のパス")] = Path("dataset"),
    verify_each: Annotated[
        bool, typer.Option("--verify/--no-verify", help="各文書を verify して status を決める")
    ] = True,
) -> None:
    """dataset/manifest.json を作り直す（CLAUDE.md §11）。"""
    from yakkan.manifest import update as run

    if action != "update":
        console.print(f"[red]未知の操作: {action}[/red]（update のみ）")
        raise typer.Exit(code=2)
    result = run(dataset_dir, verify=verify_each)
    table = Table(title="dataset/manifest.json", title_justify="left", header_style="bold")
    for column in ("doc_id", "genre", "style", "頁", "字数", "表", "図", "脚注", "参照", "status"):
        table.add_column(
            column, justify="right" if column in ("頁", "字数", "表", "図", "脚注", "参照") else "left"
        )
    for d in result.manifest.documents:
        color = {"ready": "green", "failed": "red"}.get(d.status, "yellow")
        table.add_row(
            d.doc_id,
            d.genre,
            d.style_id,
            str(d.pages),
            str(d.chars),
            str(d.tables),
            str(d.figures),
            str(d.footnotes),
            str(d.refs),
            f"[{color}]{d.status}[/{color}]",
        )
    console.print(table)
    console.print(f"{result.path} / ready {result.manifest.ready}/{len(result.manifest.documents)} 件")


@app.command()
def export(
    dataset_dir: Annotated[Path, typer.Option("--dataset", help="dataset/ のパス")] = Path("dataset"),
    only: Annotated[str | None, typer.Option("--only", help="doc_id を 1 つだけ処理する")] = None,
) -> None:
    """評価向けの派生成果物を書き出す（docs/eval_dataset_plan.md P5・P8）。

    各文書に `elements.jsonl` と `passages.jsonl`、コーパス全体に
    `dataset/search/{passages,queries,qrels}.jsonl` を作る。
    """
    import json as _json

    from yakkan.export import export_dataset, write_jsonl, write_readme
    from yakkan.models import Answer
    from yakkan.search_set import build_passages, build_search_set

    dirs = sorted(d for d in dataset_dir.iterdir() if d.is_dir() and (d / "answer.json").exists())
    if only:
        dirs = [d for d in dirs if d.name == only]
        if not dirs:
            console.print(f"[red]見つからない: {only}[/red]")
            raise typer.Exit(code=2)

    table = Table(title="export", title_justify="left", header_style="bold")
    for column in ("doc_id", "elements", "passages"):
        table.add_column(column, justify="right" if column != "doc_id" else "left")
    per_content: dict[str, Path] = {}
    for directory in dirs:
        counts = export_dataset(directory)
        table.add_row(directory.name, str(counts["elements"]), str(counts["passages"]))
        # 検索コーパスは content ごとに 1 スタイルだけ使う（別スタイルは本文が同一で重複になる）
        content_id = directory.name.split("--")[0]
        per_content.setdefault(content_id, directory)
    console.print(table)

    if only:
        return

    corpus: list[dict] = []
    qa_by_doc: dict[str, list[dict]] = {}
    for directory in per_content.values():
        answer = Answer.model_validate_json((directory / "answer.json").read_text(encoding="utf-8"))
        corpus.extend(build_passages(answer))
        qa_path = directory / "qa.json"
        if qa_path.exists():
            qa_by_doc[answer.doc_id] = _json.loads(qa_path.read_text(encoding="utf-8"))["items"]
    queries, qrels = build_search_set(corpus, qa_by_doc)
    search_dir = dataset_dir / "search"
    write_jsonl(corpus, search_dir / "passages.jsonl")
    write_jsonl(queries, search_dir / "queries.jsonl")
    write_jsonl(qrels, search_dir / "qrels.jsonl")
    write_readme(dataset_dir)
    console.print(
        f"[green]検索評価セット[/green] {search_dir} / "
        f"パッセージ {len(corpus)} 件・クエリ {len(queries)} 件・qrels {len(qrels)} 件"
        f"（コーパスは content ごとに 1 スタイル＝{len(per_content)} 文書）"
    )


@app.command("eval")
def eval_command(
    dataset_doc: Annotated[
        Path | None, typer.Argument(help="dataset/<doc_id> のパス（読み取りの採点）")
    ] = None,
    pred: Annotated[Path | None, typer.Option("--pred", help="予測 JSON")] = None,
    search_run: Annotated[
        Path | None, typer.Option("--search-run", help="検索結果 JSON（--qrels と併用）")
    ] = None,
    qrels_path: Annotated[Path, typer.Option("--qrels", help="qrels.jsonl")] = Path(
        "dataset/search/qrels.jsonl"
    ),
    queries_path: Annotated[Path, typer.Option("--queries", help="queries.jsonl")] = Path(
        "dataset/search/queries.jsonl"
    ),
    out: Annotated[Path | None, typer.Option("--out", help="採点結果の書き出し先 JSON")] = None,
    oracle: Annotated[
        bool, typer.Option("--oracle", help="満点の予測を自分で作って採点する（自己評価）")
    ] = False,
) -> None:
    """予測 JSON または検索結果を採点する（CLAUDE.md §9・docs/evaluation.md）。"""
    import json as _json

    from yakkan.eval import build_prediction, evaluate, evaluate_run, load_qrels, oracle_run
    from yakkan.models import Answer

    result: dict
    if search_run is not None or (oracle and dataset_doc is None):
        qrels = load_qrels(qrels_path)
        queries = [
            _json.loads(line)
            for line in queries_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        runs = (
            oracle_run(qrels)
            if search_run is None
            else _json.loads(search_run.read_text(encoding="utf-8"))["runs"]
        )
        result = evaluate_run(qrels, runs, queries=queries)
        console.print(f"[bold]検索[/bold] 採点したクエリ {result['queries_scored']} 件")
        table = Table(title="検索（クエリ種別ごと）", title_justify="left", header_style="bold")
        table.add_column("kind")
        columns = ["queries", "ndcg@1", "ndcg@5", "ndcg@10", "recall@10", "mrr"]
        for column in columns:
            table.add_column(column, justify="right")
        for kind, values in result["by_kind"].items():
            table.add_row(kind, *[str(values.get(c, "")) for c in columns])
        table.add_row(
            "**全体**",
            str(result["queries_scored"]),
            *[str(result["overall"].get(c, "")) for c in columns[1:]],
        )
        console.print(table)
        result.pop("per_query", None)
    else:
        if dataset_doc is None:
            console.print("[red]dataset/<doc_id> を指定するか --search-run を使う[/red]")
            raise typer.Exit(code=2)
        if oracle:
            answer = Answer.model_validate_json((dataset_doc / "answer.json").read_text(encoding="utf-8"))
            qa_file = dataset_doc / "qa.json"
            items = _json.loads(qa_file.read_text(encoding="utf-8"))["items"] if qa_file.exists() else []
            prediction = build_prediction(answer, items)
        else:
            if pred is None:
                console.print("[red]--pred か --oracle が要る[/red]")
                raise typer.Exit(code=2)
            prediction = _json.loads(pred.read_text(encoding="utf-8"))
        result = evaluate(dataset_doc, prediction)
        table = Table(title=f"読み取り評価 {result['doc_id']}", title_justify="left", header_style="bold")
        table.add_column("観点")
        table.add_column("指標", justify="right")
        rows = [
            ("本文 CER（低いほど良い）", result["text"]["cer_macro"]),
            ("見出し F1", result["outline"]["f1"]),
            ("見出しの種別 正解率", result["outline"]["kind_acc"]),
            ("構造位置 citation 正解率", result["citation"]["citation_acc"]),
            ("構造位置 カバー率", result["citation"]["coverage"]),
            ("表 TEDS", result["tables"]["teds_macro"]),
            ("表セル F1", result["tables"]["cell_f1"]["f1"]),
            ("図ノード F1", result["figures"]["node_f1"]["f1"]),
            ("図エッジ F1", result["figures"]["edge_f1"]["f1"]),
            ("図経路 F1", result["figures"]["path_f1"]["f1"]),
            ("列挙の順番一致", result["enumerations"]["order_exact"]),
            ("bbox の IoU 平均", result["layout"]["iou_mean"]),
            ("bbox 当たり率（IoU≥0.5）", result["layout"]["hit@iou0.5"]),
            ("読み順 Kendall τ", result["reading_order"]["tau_macro"]),
            ("QA 完全一致", result["qa"]["exact_match"]),
        ]
        for name, value in rows:
            table.add_row(name, str(value))
        console.print(table)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        console.print(f"[green]書き出した[/green] {out}")
