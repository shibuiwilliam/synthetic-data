"""Hugging Face で公開するためのリポジトリを組む（`HITL.md` H11）。

`distribution.build()` が「正解つきの配布物」を一般形で組むのに対し、こちらは
**Hugging Face の作法に合わせた形**で組む。足すのは次の 4 つである。

1. **データセットカード**（`README.md` の YAML frontmatter）。これが無いと HF は
   ライセンスを `unknown` と表示し、言語・課題の索引にも載らない。
2. **機械可読ビュー**（`views/*.jsonl`）と `configs`。文書ごとの入れ子の木は
   `load_dataset()` が読めないので、平らにした表を別に置く。
3. **LFS の設定**（`.gitattributes`）。PDF と PNG を通常の git に入れると使えなくなる。
4. **フォントのライセンス**。PDF には Noto（OFL 1.1）と IPAex（IPA v1.0）が
   サブセット埋め込みされているので、配るときは条件に従う義務がある。

**このモジュールはアップロードしない。** push とアップロードは人が行う
（`HITL.md` H4・H11、`DESIGN.md` §10.3 軸 B）。

配らないもの（`EXCLUDE`）:

* `render.html` — 本体が「デバッグ用・配布対象外」と定めている（本体 `CLAUDE.md` §1）。
* `source.json` — 同じ文書の `policy.json` と**バイト単位で同一**な重複である
  （実測 280/280 件）。`check()` が同一性を確かめてから外す。
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from .layout import PRIVATE, PUBLIC, file_hashes, sha256, write_json, write_jsonl

#: 配布物に入れないファイル名（理由はモジュールの docstring）
EXCLUDE = ("render.html", "source.json")

#: `__pycache__` などの作業用ディレクトリ
SKIP_DIRS = ("__pycache__", ".pytest_cache")

#: 選べるライセンス。鍵は HF の `license:` タグ（HF の語彙に無い値を書くと索引に載らない）
LICENSES: dict[str, tuple[str, str]] = {
    "cc-by-4.0": (
        "Creative Commons Attribution 4.0 International",
        "https://creativecommons.org/licenses/by/4.0/",
    ),
    "cc-by-sa-4.0": (
        "Creative Commons Attribution-ShareAlike 4.0 International",
        "https://creativecommons.org/licenses/by-sa/4.0/",
    ),
    "cc-by-nc-4.0": (
        "Creative Commons Attribution-NonCommercial 4.0 International",
        "https://creativecommons.org/licenses/by-nc/4.0/",
    ),
    "cc0-1.0": ("Creative Commons Zero v1.0 Universal", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "mit": ("MIT License", "https://opensource.org/license/mit"),
    "apache-2.0": ("Apache License 2.0", "https://www.apache.org/licenses/LICENSE-2.0"),
    "other": ("未決（公開前に人が決める）", ""),
}

#: 既定のライセンス。**仮決めである**（`HITL.md` H11。人が決めたら `--license` で上書きする）
DEFAULT_LICENSE = "cc-by-4.0"

#: 埋め込みフォントのライセンス本文。本体の `assets/fonts/` から複写する（読むだけ）
FONT_LICENSES = (
    ("LICENSE-NotoSansJP.txt", "Noto Sans JP", "SIL Open Font License 1.1"),
    ("LICENSE-NotoSerifJP.txt", "Noto Serif JP", "SIL Open Font License 1.1"),
    ("IPA_Font_License_Agreement_v1.0.txt", "IPAex ゴシック／明朝", "IPA フォントライセンス v1.0"),
)

#: ビューの並び。**先頭が HF の既定の config になる**ので、正解（`cases`）を先頭にしない
VIEW_ORDER = ("documents", "pages", "rules", "tasks", "cases")

#: HF の課題分類（語彙にある値だけを使う）
TASK_CATEGORIES = (
    "document-question-answering",
    "table-question-answering",
    "visual-question-answering",
    "text-generation",
)


@dataclass(frozen=True)
class Options:
    """組み立ての設定。既定値はすべてここに集める。"""

    version: str
    generator_version: str
    license_id: str = DEFAULT_LICENSE
    include_png: bool = True
    repo_id: str = "<your-account>/yakkan-calc"
    pretty_name: str = "yakkan-calc: 合成日本語保険約款＋計算規定の正解データ"


# --------------------------------------------------------------------------- 組み立て


def build(dataset_dir: Path, out_dir: Path, opts: Options) -> dict:
    """`dataset_dir` を Hugging Face に上げられる形にして `out_dir` に組む。"""
    dataset_dir, out_dir = Path(dataset_dir), Path(out_dir)
    if opts.license_id not in LICENSES:
        raise ValueError(f"知らないライセンス: {opts.license_id}（選べる: {', '.join(sorted(LICENSES))}）")
    docs = sorted(p.parent.parent for p in dataset_dir.glob("*/calc/manifest.json"))
    if not docs:
        raise FileNotFoundError(f"{dataset_dir} に文書が無い（calc/manifest.json が見つからない）")

    check(dataset_dir)  # 外す前に「重複だから外してよい」ことを確かめる

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "documents").mkdir(parents=True)

    entries = [_copy_document(doc, out_dir / "documents" / doc.name, opts) for doc in docs]
    views, schema_notes = _write_views(dataset_dir, docs, entries, out_dir / "views")

    index = {
        "name": "yakkan-calc",
        "version": opts.version,
        "generator_version": opts.generator_version,
        "license": opts.license_id,
        "contains_answers": True,
        "includes_page_images": opts.include_png,
        "excluded_from_distribution": list(EXCLUDE),
        "documents": entries,
        "totals": _totals(entries),
        "views": views,
        "view_schema_notes": schema_notes,
        "page_image_dpi": _dpi_of(docs),
    }
    # カナリアは内容から決める（乱数も時刻も使わない。`CLAUDE.md` 守ること 3）
    index["canary"] = _canary(index)

    _copy_if_present(dataset_dir / "data-card.md", out_dir / "data-card.md")
    _copy_if_present(dataset_dir / "_run_report.json", out_dir / "_run_report.json")
    _write_font_licenses(dataset_dir, out_dir / "licenses-fonts")
    (out_dir / ".gitattributes").write_text(_gitattributes(), encoding="utf-8")
    (out_dir / "LICENSE").write_text(_license(opts), encoding="utf-8")
    (out_dir / "README.md").write_text(_card(index, opts), encoding="utf-8")

    # `index.json` 自身は外す。ハッシュを書き込んだ時点で中身が変わり、記録が嘘になる
    index["files"] = file_hashes(out_dir, skip=("index.json",))
    write_json(out_dir / "index.json", index)
    return index


def check(dataset_dir: Path) -> None:
    """外すファイルが本当に重複であることを確かめる。

    `source.json` を「`policy.json` と同じだから外す」と決め打ちにすると、
    将来どちらかの中身が変わったときに黙って情報を落とす。毎回測る。
    """
    bad: list[str] = []
    for policy in sorted(Path(dataset_dir).glob("*/policy.json")):
        want = sha256(policy)
        for src in sorted(policy.parent.glob("*/source.json")):
            if sha256(src) != want:
                bad.append(str(src))
    if bad:
        raise ValueError(
            "source.json が policy.json と一致しない文書がある。"
            "重複として外せないので、EXCLUDE を見直すこと:\n  " + "\n  ".join(bad[:10])
        )


def _copy_document(doc: Path, dest: Path, opts: Options) -> dict:
    """1 文書を複写し、索引の 1 行を返す。"""
    for src in sorted(doc.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(doc)
        if src.name in EXCLUDE or any(p in SKIP_DIRS for p in rel.parts):
            continue
        if not opts.include_png and src.suffix == ".png":
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)

    man = json.loads((doc / "calc" / "manifest.json").read_text(encoding="utf-8"))
    renders = man.get("renders") or []
    return {
        "doc_id": doc.name,
        "genre": man.get("genre") or doc.name.split("-")[0],
        "base_content_id": man.get("base_content_id"),
        "variant": _variant_of(doc.name),
        "profile": man.get("profile"),
        "seed": man.get("seed"),
        "generator_version": man.get("generator_version"),
        "rules": man["counts"]["rules"],
        "cases": man["counts"]["cases"],
        "cases_by_kind": dict(sorted(man["counts"]["cases_by_kind"].items())),
        "patterns": sorted(man["plan"]["patterns"]),
        "challenge": man.get("challenge") or [],
        "styles": [r["style"] for r in renders],
        "pages": man["pages"].get("rendered"),
        "layouts": len(renders),
    }


def _dpi_of(docs: list[Path]) -> int | None:
    """ページ画像の dpi を `layout.json` から実測する（決め打ちにしない）。"""
    found = set()
    for doc in docs:
        for layout in sorted(doc.glob("*/layout.json")):
            dpi = (_read_json(layout) or {}).get("dpi_png")
            if dpi:
                found.add(int(dpi))
    return sorted(found)[0] if len(found) == 1 else None


def _variant_of(doc_id: str) -> int:
    """`auto-0001-c2` → 2。接尾が無ければ 1。"""
    head, _, tail = doc_id.rpartition("-c")
    return int(tail) if head and tail.isdigit() else 1


def _copy_if_present(src: Path, dest: Path) -> None:
    if src.is_file():
        shutil.copy2(src, dest)


# --------------------------------------------------------------------------- ビュー


def _write_views(dataset_dir: Path, docs: list[Path], entries: list[dict], out: Path) -> dict[str, int]:
    """`load_dataset()` が読める平らな表を書く。

    **型が揺れる欄は JSON の文字列にする。** `expected` は文書によって
    真偽・整数・日付・`None` を取るので、そのまま並べると `datasets` の型推論が
    壊れる。元の型は文書ごとの `calc/cases.jsonl` に残っている。
    """
    out.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[dict]] = {k: [] for k in VIEW_ORDER}

    # `challenge` は中身が入れ子で、challenge モードを使わない限り全行が空になる。
    # 全行が空の列は HF が要素の型を決められないので、文字列にして渡す
    rows["documents"] = [
        {**{k: v for k, v in e.items() if k != "challenge"}, "challenge_json": _json(e["challenge"])}
        for e in entries
    ]

    for doc in docs:
        doc_id = doc.name
        calc = doc / "calc"

        tasks_by_rule: dict[tuple[str, str], dict] = {}
        for name, hint in (("tasks.jsonl", "H0"), ("tasks_H1.jsonl", "H1"), ("tasks_H2.jsonl", "H2")):
            for t in _read_jsonl(calc / name):
                tasks_by_rule.setdefault((t.get("rule_id", ""), hint), t)
                rows["tasks"].append(
                    {
                        "doc_id": doc_id,
                        "task_id": t.get("task_id"),
                        "rule_id": t.get("rule_id"),
                        "function": t.get("function"),
                        "title": t.get("title"),
                        "kind": t.get("kind"),
                        "hint": t.get("hint", hint),
                        "inputs_json": _json(t.get("inputs")),
                        "output_json": _json(t.get("output")),
                        "sources_json": _json(t.get("sources")),
                        "conventions_json": _json(t.get("conventions")),
                    }
                )

        for r in _read_json(calc / "answer_key.json") or []:
            task = tasks_by_rule.get((r.get("rule", ""), "H0")) or {}
            rows["rules"].append(
                {
                    "doc_id": doc_id,
                    "rule_id": r.get("rule"),
                    "function": r.get("function"),
                    "title": task.get("title"),
                    "kind": task.get("kind"),
                    "pattern": r.get("pattern"),
                    "units": r.get("units") or [],
                    "explanatory_units": r.get("explanatory_units") or [],
                    "constants": r.get("constants") or [],
                    "modalities": r.get("modalities") or [],
                    "difficulty_json": _json(r.get("difficulty")),
                }
            )

        for c in _read_jsonl(calc / "cases.jsonl"):
            rows["cases"].append(
                {
                    "doc_id": doc_id,
                    "case_id": c.get("case_id"),
                    "rule_id": c.get("rule_id"),
                    "function": c.get("function"),
                    "kind": c.get("kind"),
                    "inputs_json": _json(c.get("inputs")),
                    "expected_json": _json(c.get("expected")),
                    "expected_type": type(c.get("expected")).__name__,
                }
            )

        for layout in sorted(doc.glob("*/layout.json")):
            lay = _read_json(layout) or {}
            render_dir = layout.parent.name
            for page in lay.get("pages") or []:
                n = page.get("number")
                img = f"documents/{doc_id}/{render_dir}/pages/page-{n:03d}.png" if n else None
                rows["pages"].append(
                    {
                        "doc_id": doc_id,
                        "render_id": render_dir,
                        "style_id": lay.get("style_id"),
                        "page": n,
                        "columns": page.get("columns"),
                        "pdf": f"documents/{doc_id}/{render_dir}/doc.pdf",
                        "image": img,
                        "dpi": lay.get("dpi_png"),
                        "page_size_pt": _json(lay.get("page_size_pt")),
                    }
                )

    counts = {}
    for name, data in rows.items():
        write_jsonl(out / f"{name}.jsonl", data)
        counts[name] = len(data)
    return counts, _schema_notes(rows)


def _schema_notes(rows: dict[str, list[dict]]) -> dict[str, list[str]]:
    """型が決まらない列を挙げる（**隠さずに記録する**）。

    `load_dataset()` が壊れるのは**同じ列にスカラーの型が混ざったとき**だけで、
    そこは `_json()` で防いでいる。残る 2 つは壊れはしないが型が貧弱になる。

    * 全行が空のリスト → `list<null>` になる。後の版で値が入ると schema が変わる。
    * 全行が `null` → `null` 型になる。

    どちらも「その観点を覆う文書がまだ無い」ことの現れなので、黙って潰さず索引に残す
    （データカード §13 の「使っていない観点」と同じ考え方）。
    """
    notes: dict[str, list[str]] = {}
    for name, data in rows.items():
        if not data:
            continue
        weak = []
        for key in data[0]:
            values = [r.get(key) for r in data]
            if all(v is None for v in values):
                weak.append(f"{key}: 全行が null")
            elif all(isinstance(v, list) and not v for v in values):
                weak.append(f"{key}: 全行が空のリスト")
        if weak:
            notes[name] = weak
    return notes


def _json(value) -> str:
    """型が揺れる値を、安定した 1 列に収めるための JSON 文字列。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _totals(entries: list[dict]) -> dict:
    kinds: dict[str, int] = {}
    for e in entries:
        for k, v in e["cases_by_kind"].items():
            kinds[k] = kinds.get(k, 0) + v
    return {
        "documents": len(entries),
        "genres": len({e["genre"] for e in entries}),
        "base_contents": len({e["base_content_id"] for e in entries if e["base_content_id"]}),
        "rules": sum(e["rules"] for e in entries),
        "cases": sum(e["cases"] for e in entries),
        "cases_by_kind": dict(sorted(kinds.items())),
        "layouts": sum(e["layouts"] for e in entries),
        "styles": sorted({s for e in entries for s in e["styles"]}),
        "patterns": sorted({p for e in entries for p in e["patterns"]}),
        "genre_counts": _tally(e["genre"] for e in entries),
        "profile_counts": _tally(e["profile"] for e in entries),
    }


def _tally(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in values:
        out[str(v)] = out.get(str(v), 0) + 1
    return dict(sorted(out.items()))


def _canary(index: dict) -> str:
    """汚染（contamination）検知用の文字列。内容から決めるので版ごとに変わる。

    学習データにこの文字列が混ざっていれば、このデータセットを読み込んだ証拠になる。
    """
    seed = json.dumps(index["totals"], ensure_ascii=False, sort_keys=True) + index["version"]
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"yakkan-calc:canary:{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


# --------------------------------------------------------------------------- 付属文書


def _write_font_licenses(dataset_dir: Path, out: Path) -> None:
    """埋め込みフォントのライセンス本文を複写する。

    本体の `assets/fonts/` にある本文を読むだけで、本体は変更しない
    （`CLAUDE.md` 守ること 10）。見つからないものは一覧に「同梱できなかった」と書く。
    """
    out.mkdir(parents=True, exist_ok=True)
    fonts_dir = _find_fonts_dir(dataset_dir)
    lines = [
        "# 埋め込みフォントのライセンス",
        "",
        "`documents/**/doc.pdf` には、下のフォントが**サブセットで埋め込まれている**。",
        "PDF を再配布するときは、それぞれの条件に従うこと。",
        "",
        "| フォント | ライセンス | 本文 |",
        "|---|---|---|",
    ]
    for filename, font, license_name in FONT_LICENSES:
        src = (fonts_dir / filename) if fonts_dir else None
        if src and src.is_file():
            shutil.copy2(src, out / filename)
            lines.append(f"| {font} | {license_name} | [`{filename}`]({filename}) |")
        else:
            lines.append(f"| {font} | {license_name} | **同梱できなかった**（本文は配布元で確認すること） |")
    lines += [
        "",
        "PNG はラスタライズ済みでフォントのデータを含まない。",
        "`policy.json` / `layout.json` / `calc/*` も同様で、フォントのライセンスは関わらない。",
        "",
        "データセット本体のライセンスは、リポジトリ直下の `LICENSE` を見ること。",
    ]
    (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _find_fonts_dir(dataset_dir: Path) -> Path | None:
    """本体の `assets/fonts/` を探す（拡張の位置から上にたどる）。"""
    here = Path(__file__).resolve()
    for root in (*here.parents, Path(dataset_dir).resolve(), *Path(dataset_dir).resolve().parents):
        cand = root / "assets" / "fonts"
        if cand.is_dir():
            return cand
    return None


def _gitattributes() -> str:
    """LFS の設定。PDF と PNG だけを LFS に入れる。

    JSON を LFS に入れると HF のデータセットビューアが中身を見せられなくなる。
    実測では 10MB を超えるファイルが 1 件も無いので、通常の git で足りる。
    """
    return """# Hugging Face の LFS 設定（PDF と PNG だけ。JSON は 10MB 未満なので通常の git で足りる）
*.pdf filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
# 改行を変換しない（PDF のテキスト層とハッシュが変わる）
* -text
"""


def _license(opts: Options) -> str:
    name, url = LICENSES[opts.license_id]
    head = f"# ライセンス\n\n**{name}**"
    if url:
        head += f"（`{opts.license_id}`）\n\n本文: {url}"
    else:
        head += (
            f"（`{opts.license_id}`）\n\n"
            "**このデータセットのライセンスは未決である。** 公開する前に人が決めること"
            "（`HITL.md` H11）。決まるまで再配布・商用利用の可否は未定とする。"
        )
    return f"""{head}

対象は、このリポジトリに含まれる合成約款（`policy.json`・PDF・PNG・`layout.json`）と
正解データ（`calc/`）、および索引とビュー（`index.json`・`views/`）である。

## 別の条件がかかるもの

* **PDF に埋め込まれたフォント。** Noto 系は SIL Open Font License 1.1、IPAex 系は
  IPA フォントライセンス v1.0 に従う。本文と対応表は `licenses-fonts/` にある。

## 断り書き

* 文書は**完全に架空**であり、実在の保険会社・商品・約款とは関係がない。
  会社名・商品名・連絡先・様式番号・人物名はすべて架空で、法的効力を持たない。
* 実在の約款の文章は**1 文字も含まれていない**。参考にしたのは構造とレイアウトの慣行だけである。
* **正解が含まれる。** 学習データに使うと、このデータセットでの評価が成り立たなくなる。
"""


def _yaml(value: str) -> str:
    """YAML の値として安全に書く。

    YAML は JSON の上位互換なので、二重引用符の JSON 文字列はそのまま妥当な YAML である。
    引用しないと、`pretty_name` のコロンや `n<1K` の記号で壊れる。
    """
    return json.dumps(str(value), ensure_ascii=False)


def _card(index: dict, opts: Options) -> str:
    """HF のデータセットカード（`README.md`）。数値はすべて `index` の実測から書く。"""
    t = index["totals"]
    v = index["views"]
    name, url = LICENSES[opts.license_id]
    license_note = f"[{name}]({url})" if url else f"{name}"

    # 軸 A の「渡してよい」一覧から、公開物に入れていないものを除く
    shipped_public = [f for f in PUBLIC if f not in EXCLUDE]
    n_styles = len(t["styles"])
    genres = "・".join(f"{g} {n}" for g, n in t["genre_counts"].items())
    kinds = "・".join(f"{k} {n:,}" for k, n in t["cases_by_kind"].items())
    dpi = index.get("page_image_dpi")
    png_note = f"ページ画像（PNG・{dpi} dpi）も入っています" if dpi else "ページ画像（PNG）も入っています"
    if not index["includes_page_images"]:
        r = f"-r {dpi} " if dpi else ""
        png_note = (
            "**ページ画像（PNG）は入っていません。** `documents/**/doc.pdf` から "
            f"`pdftoppm {r}-png` で作り直せます（決定的）"
        )

    frontmatter = _frontmatter(index, opts)
    return f"""{frontmatter}

# {opts.pretty_name}

**完全に架空**の日本語保険約款 **{t["documents"]:,}** 文書に、機械生成した**計算・判定の規定**
（条・表・算式・図）を足し、その**正解プログラム**（Python）と**テストケース**を
同じ計算仕様から作ったデータセットです。

「約款のこの条を読んで、支払額を計算する関数を書けるか」を測れます。
文言・正解プログラム・テストの期待値はすべて同じ計算仕様から機械的に作ってあるので、
**三者がずれることが原理的に起きません**。

| 項目 | 実測 |
|---|---|
| 文書 | **{t["documents"]:,}**（{t["genres"]} 種目・既定の約款 {t["base_contents"]} 件） |
| 種目 | {genres} |
| 計算・判定の規定（ルール） | **{t["rules"]:,}** |
| テストケース | **{t["cases"]:,}**（{kinds}） |
| 描画結果（レイアウト） | **{t["layouts"]:,}**（{n_styles} スタイル。同じ内容を別の体裁で描いたもの） |
| パターン（ルールの型） | {len(t["patterns"])} 種（{", ".join(t["patterns"])}） |
| 生成器の版 | `{index["generator_version"]}` / データセットの版 `{index["version"]}` |

正解は**1 文書に 1 組**で、体裁が変わっても変わりません（レイアウト頑健性の評価に使えます）。
{png_note}。

## ⚠ 先に読んでください：正解が入っています

このリポジトリには**正解（計算仕様・正解プログラム・正解表・全テストケース）が入っています**。

* **学習データに使わないでください。** 使った時点で、このデータセットでそのモデルを
  評価できなくなります。
* **採点するときは、評価対象に渡すものを絞ってください。** 渡してよいのは
  `{"`・`".join(shipped_public)}` で、`{"`・`".join(PRIVATE)}` は渡しません。
  生成器の `icc export` が機械的に分けます。
* 汚染が疑われるときは**作り直せます**（下の「作り直し方」）。

汚染検知用のカナリア文字列（学習データを grep するときに使ってください）:

```
{index["canary"]}
```

## 使い方

### 平らな表として読む（`datasets`）

```python
from datasets import load_dataset

docs  = load_dataset("{opts.repo_id}", "documents")   # 文書の一覧（{v["documents"]:,} 行）
rules = load_dataset("{opts.repo_id}", "rules")       # 規定と根拠（{v["rules"]:,} 行）
tasks = load_dataset("{opts.repo_id}", "tasks")       # 出題（{v["tasks"]:,} 行・ヒント 3 水準）
cases = load_dataset("{opts.repo_id}", "cases")       # テストケース（{v["cases"]:,} 行）★正解
pages = load_dataset("{opts.repo_id}", "pages")       # ページと画像（{v["pages"]:,} 行）
```

**型が揺れる欄は JSON の文字列にしてあります**（`inputs_json`・`expected_json`・
`difficulty_json` ほか）。`expected` は文書によって真偽・整数・日付・`None` を取るため、
そのまま列にすると型推論が壊れます。元の型は文書ごとの `calc/cases.jsonl` に残してあります。

```python
import json
row = cases["train"][0]
json.loads(row["inputs_json"]), json.loads(row["expected_json"])
```

### 原本を読む

```python
from huggingface_hub import snapshot_download
path = snapshot_download("{opts.repo_id}", repo_type="dataset")
```

## 中身

```
documents/<doc_id>/
├── policy.json                     # 約款の内容・構造・意味（読み取りの対象）
├── <doc_id>--<style>/              # 体裁ごとの描画結果
│   ├── doc.pdf
│   ├── layout.json                 # bbox・読み順・ヘッダ／フッタ
│   └── pages/page-NNN.png          # ページ画像
└── calc/
    ├── tasks.jsonl                 # 出題（ヒント H0）。tasks_H1 / tasks_H2 は根拠つき
    ├── spec.json                   # ★正解：計算仕様（唯一の正）
    ├── answer_key.json             # ★正解：根拠単位・パターン・難易度
    ├── programs/calc_<id>.py       # ★正解：参照実装（標準ライブラリだけで動く）
    ├── cases.jsonl                 # ★正解：全テストケース
    ├── tests/                      # ★正解：pytest
    ├── patch.json                  # 既定の約款への追加操作の記録
    └── manifest.json               # 版・seed・ハッシュ・検証ゲートの結果

views/*.jsonl                       # 上を平らにした表（load_dataset が読む）
data-card.md                        # 詳しいデータカード（規模・内訳・制限と偏りの実測）
index.json                          # 文書の一覧・合計・全ファイルのハッシュ
_run_report.json                    # 生成時の記録（作れなかった組も載っている）
licenses-fonts/                     # PDF に埋め込んだフォントのライセンス
```

★ の付いたものが正解です。**`data-card.md` に、規模・内訳・正解の中身・検証の結果・
制限と既知の偏りの実測値があります。評価に使う前に読んでください。**

配っていないもの: `render.html`（生成の中間物）と、描画ごとの `source.json`
（同じ文書の `policy.json` とバイト単位で同一の重複）。

## どう作ったか

1. 既定の架空約款（`yakkan-synth` が生成した執筆物）に、計算・判定の規定を機械的に足す。
2. **計算仕様が唯一の正。** 約款の文言・正解プログラム・テストの期待値は、すべて同じ
   仕様から機械的に作る。文言とプログラムを別々に書いていない。
3. **12 の検証ゲートを通す。** 通らない文書は出力しない（仕様の整合・根拠の逐語一致・
   明示性・設例の一致・実装の一致・テストの十分性・名前の衝突・本体の lint と verify・
   決定性・発見可能性・解答可能性）。
4. **生成の経路で LLM を使っていない。** 文言は文型（テンプレート）から組んである。

## 作り直し方

**決定的に生成されます。** 同じ既定の約款・同じ seed・同じ生成器の版なら同じ内容が出ます。
各文書の `calc/manifest.json` に `seed`・`profile`・既定の約款のIDが入っています。

```bash
icc generate --base <既定の約款> --out out --seed <seed> --profile <profile> --multi-style
```

## 架空であること

会社名・商品名・連絡先・様式番号・人物名はすべて架空です。実在の保険会社・商品・約款とは
関係がありません。URL は `example.jp` / `example.co.jp` のみ、電話番号はゼロ埋めのみです。
実在の法令は**名称だけ**を引用し、条番号は書いていません。
実在の約款の文章は**1 文字も含まれていません**。

## 限界

`data-card.md` の「制限と既知の偏り」に実測を載せていますが、主なものは次のとおりです。

* **専門家の校閲を受けていません。** 保険数理・監督規制の妥当性は見ていません。
* **日本語・横書きのみ**です。縦書き・スキャン風の劣化画像は入っていません。
* **既定の約款にある計算規定の一義性は保証しません。** 足した規定は検証ゲートで一義に
  読めることを強制していますが、既定の部分にその保証はありません。
* **検証に通った集合は「通りやすい組」に偏ります。** 落ちた文書は seed をずらして
  組み直されるため、特定の経路が出力に出てこないことがあります
  （`_run_report.json` に「作れなかった組」が理由つきで載っています）。

## ライセンス

{license_note}（`LICENSE`）。

**PDF に埋め込まれたフォント**は別条件です。Noto 系は SIL Open Font License 1.1、
IPAex 系は IPA フォントライセンス v1.0 に従います（`licenses-fonts/`）。
"""


def _frontmatter(index: dict, opts: Options) -> str:
    """HF のデータセットカードの YAML frontmatter。

    `license` が無いと HF は `unknown` と表示し、`configs` が無いと
    `load_dataset()` が入れ子の木を読もうとして失敗する。
    """
    t = index["totals"]
    biggest = max(index["views"].values()) if index["views"] else 0
    size = (
        "n<1K"
        if biggest < 1_000
        else "1K<n<10K"
        if biggest < 10_000
        else "10K<n<100K"
        if biggest < 100_000
        else "100K<n<1M"
    )
    # 先頭を既定の config にする。`cases` は正解なので既定にしない
    names = [n for n in VIEW_ORDER if n in index["views"]]
    names += [n for n in sorted(index["views"]) if n not in names]
    configs = "\n".join(
        f"  - config_name: {name}\n    data_files: views/{name}.jsonl"
        + ("\n    default: true" if i == 0 else "")
        for i, name in enumerate(names)
    )
    tasks = "\n".join(f"  - {c}" for c in TASK_CATEGORIES)
    # 値は必ず引用する。`pretty_name` にコロンが入ると YAML が壊れる
    return f"""---
pretty_name: {_yaml(opts.pretty_name)}
license: {_yaml(opts.license_id)}
language:
  - ja
multilinguality:
  - monolingual
annotations_creators:
  - machine-generated
language_creators:
  - machine-generated
source_datasets:
  - original
size_categories:
  - {_yaml(size)}
task_categories:
{tasks}
tags:
  - insurance
  - japanese
  - synthetic
  - document-understanding
  - layout-analysis
  - ocr
  - table-understanding
  - program-synthesis
  - reasoning
  - contains-answers
configs:
{configs}
---

<!-- このファイルは `icc package <dataset> --format hf` が生成する。手で編集しない
     （`CLAUDE.md` 守ること 2）。直すのは `export/huggingface.py` の側。
     文書 {t["documents"]} / ルール {t["rules"]} / ケース {t["cases"]} -->"""
