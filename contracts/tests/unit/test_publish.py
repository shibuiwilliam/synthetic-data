"""`keiyaku/publish.py` — 公開（Hugging Face Hub）用の面（仕様は `docs/publishing.md`）。

ここで縛るのは 5 つ：

- **Arrow に落ちる形を崩さない**（1 列に型を混ぜない。混ぜると Dataset Viewer が落ちる）。
- **人間の決定を代行しない**（ライセンス未決なら frontmatter に `license` を出さず `LICENSE` も作らない）。
- **配布しないものを配らない**（`render.html`・`.DS_Store` は一覧に出さない）。
- **決定論**（2 回書いてバイト一致）。
- **鮮度**（古くなれば `check` が気づく。ただし未決のライセンスは `make check` を赤くしない）。
"""

from __future__ import annotations

import json
from pathlib import Path

from keiyaku.manifest import DocumentEntry
from keiyaku.publish import (
    PROTECTED_HINT,
    PublishSpec,
    blockers,
    check,
    distributed_files,
    document_rows,
    frontmatter,
    load_spec,
    page_rows,
    publish,
    qa_rows,
    write_license_file,
)
from tests.unit.test_datacard import _write_doc, _write_manifest

#: 答えの型が 3 種（string / number / list）とも出るようにした QA。**この混在が Arrow の罠**
QA_ITEMS = [
    {
        "id": "qa_auto_001",
        "type": "count",
        "question": "表には何行あるか。",
        "answer": 4.0,
        "answer_type": "number",
        "evidence": ["tbl1"],
        "page_hint": [1],
        "source": "auto",
    },
    {
        "id": "qa_auto_002",
        "type": "extract",
        "question": "甲の名称は何か。",
        "answer": "架空甲社",
        "answer_type": "string",
        "evidence": ["a1_p1"],
        "page_hint": [1],
        "source": "auto",
    },
    {
        "id": "qa_auth_001",
        "type": "list",
        "question": "秘密情報から除かれるものを挙げよ。",
        "answer": ["公知のもの", "自ら得たもの"],
        "answer_type": "list",
        "evidence": ["a1_p1"],
        "page_hint": [1],
        "source": "authored",
    },
]


def _enrich(dataset_dir: Path, entry: DocumentEntry) -> None:
    """`_write_doc` の最小の成果物に、views が要る中身（ページ本文・QA・PNG）を足す。"""
    doc_dir = dataset_dir / entry.doc_id
    pages = entry.pages
    (doc_dir / "answer.json").write_text(
        json.dumps(
            {
                "doc_id": doc_dir.name,
                "pages": [
                    {
                        "number": n,
                        "text": f"{n} ページの本文",
                        "text_with_furniture": f"{n} ページの本文（ヘッダつき）",
                        "chars": 8,
                    }
                    for n in range(1, pages + 1)
                ],
                "outline": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (doc_dir / "qa.json").write_text(
        json.dumps({"doc_id": doc_dir.name, "items": QA_ITEMS}, ensure_ascii=False), encoding="utf-8"
    )
    pages_dir = doc_dir / "pages"
    pages_dir.mkdir(exist_ok=True)
    for n in range(1, pages + 1):
        (pages_dir / f"page-{n:03d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    # 配布してはいけないもの（デバッグ用の中間 HTML と macOS のごみ）
    (doc_dir / "render.html").write_text("<html></html>", encoding="utf-8")
    (doc_dir / ".DS_Store").write_bytes(b"\x00")


def _dataset(tmp_path: Path) -> Path:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    entries = [
        _write_doc(dataset_dir, "nda-0001", "ct-a4-1col-mincho", pages=2, qa_items=len(QA_ITEMS)),
        _write_doc(dataset_dir, "nda-0001", "ct-a4-1col-form", pages=1, qa_items=len(QA_ITEMS)),
    ]
    _write_manifest(dataset_dir, entries)
    for entry in entries:
        _enrich(dataset_dir, entry)
    return dataset_dir


def _spec(license_id: str = "undecided") -> PublishSpec:
    spec = load_spec()
    return spec.model_copy(update={"license": spec.license.model_copy(update={"id": license_id})})


def _column_types(rows: list[dict]) -> dict[str, set[str]]:
    types: dict[str, set[str]] = {}
    for row in rows:
        for key, value in row.items():
            name = type(value).__name__ if value is not None else "null"
            types.setdefault(key, set()).add(name)
            if isinstance(value, list):
                for item in value:
                    types.setdefault(f"{key}[]", set()).add(type(item).__name__)
    return types


def test_viewsの列に型が混在しない(tmp_path: Path) -> None:
    """1 列に型が混ざると Hub の Dataset Viewer が落ちる（`docs/publishing.md` §4）。"""
    dataset_dir = _dataset(tmp_path)
    for rows in (document_rows(dataset_dir), page_rows(dataset_dir), qa_rows(dataset_dir)):
        assert rows
        for column, found in _column_types(rows).items():
            concrete = found - {"null"}
            assert len(concrete) <= 1 or concrete == {"int", "float"}, f"{column}: {found}"


def test_qaの答えは型ごとの列に分かれ生の値も残る(tmp_path: Path) -> None:
    """採点の正本は `qa.json` なので、views でも**値を失わない**（`answer_json`）。"""
    rows = {row["qa_id"]: row for row in qa_rows(_dataset(tmp_path))}
    number = rows["qa_auto_001"]
    assert (number["answer_number"], number["answer_text"], number["answer_list"]) == (4.0, None, None)
    assert json.loads(number["answer_json"]) == 4.0
    string = rows["qa_auto_002"]
    assert string["answer_text"] == "架空甲社" and string["answer_number"] is None
    listed = rows["qa_auth_001"]
    assert listed["answer_list"] == ["公知のもの", "自ら得たもの"]
    assert json.loads(listed["answer_json"]) == ["公知のもの", "自ら得たもの"]


def test_pagesはページ画像の相対パスを持つ(tmp_path: Path) -> None:
    dataset_dir = _dataset(tmp_path)
    rows = page_rows(dataset_dir)
    assert [r["page"] for r in rows if r["doc_id"].endswith("mincho")] == [1, 2]
    for row in rows:
        assert (dataset_dir / row["image"]).is_file()
        assert not row["image"].startswith("/")


def test_frontmatterは未決ならlicenseを出さず決まれば出す(tmp_path: Path) -> None:
    """**人間が決めるまで嘘のタグを出さない**（`CLAUDE.md` §0.2-1・H13）。"""
    undecided = frontmatter(_spec(), None)
    assert "license:" not in undecided
    assert "configs:" in undecided and "views/documents.jsonl" in undecided
    decided = frontmatter(_spec("cc-by-4.0"), None)
    assert decided.splitlines()[1] == "license: cc-by-4.0"


def test_未決のあいだはLICENSEを作らない(tmp_path: Path) -> None:
    dataset_dir = _dataset(tmp_path)
    assert write_license_file(dataset_dir, _spec()) is None
    assert not (dataset_dir / "LICENSE").exists()
    path = write_license_file(dataset_dir, _spec("cc-by-4.0"))
    assert path is not None and "cc-by-4.0" in path.read_text(encoding="utf-8")
    # 決定が取り消されたら消す（古い条件を配らない）
    assert write_license_file(dataset_dir, _spec()) is None
    assert not (dataset_dir / "LICENSE").exists()


def test_配布一覧とSHA256SUMSは配布しないものを含まない(tmp_path: Path) -> None:
    dataset_dir = _dataset(tmp_path)
    spec = _spec()
    publish(dataset_dir, spec=spec)
    names = {p.name for p in distributed_files(dataset_dir, spec)}
    assert "render.html" not in names and ".DS_Store" not in names
    assert {"source.json", "qa.json", "page-001.png"} <= names
    sums = (dataset_dir / "SHA256SUMS").read_text(encoding="utf-8")
    assert "render.html" not in sums and ".DS_Store" not in sums
    assert "SHA256SUMS" not in sums  # 自分自身は数えない（鮮度検査が収束しない）
    assert "README.md" in sums and ".gitattributes" in sums
    assert "render.html" in (dataset_dir / ".gitignore").read_text(encoding="utf-8")


def test_licensesには埋め込まれていたフォントだけ入れる(tmp_path: Path) -> None:
    """`layout.renderer.fonts` は**描画に登録した候補**で、使われたものとは違う
    （`docs/decisions.md` 140）。この dataset には PDF が無いので 1 本も入らない。"""
    dataset_dir = _dataset(tmp_path)
    publish(dataset_dir, spec=_spec())
    got = {p.name for p in (dataset_dir / "licenses").iterdir()}
    assert got == {"NOTICE.md"}
    notice = (dataset_dir / "licenses" / "NOTICE.md").read_text(encoding="utf-8")
    assert "IPA" not in notice and "転載していない" in notice


def test_publishは決定論(tmp_path: Path) -> None:
    dataset_dir = _dataset(tmp_path)
    watch = ("README.md", "SHA256SUMS", ".gitattributes", "views/qa.jsonl")
    publish(dataset_dir, spec=_spec())
    first = {name: (dataset_dir / name).read_bytes() for name in watch}
    publish(dataset_dir, spec=_spec())
    assert {name: (dataset_dir / name).read_bytes() for name in watch} == first


def test_カードに数値を焼き込まず実測値を入れる(tmp_path: Path) -> None:
    dataset_dir = _dataset(tmp_path)
    publish(dataset_dir, spec=_spec())
    card = (dataset_dir / "README.md").read_text(encoding="utf-8")
    assert "**2 documents**" in card  # 文書 2 本・ページ 3 枚・QA 6 問の dataset
    assert "3 pages in total" in card
    assert "{n_queries}" not in card and "{docs}" not in card
    assert "配布条件は未決" in card and "H13" in card
    assert "約款" not in card  # yakkan（保険約款）の名残を配らない


def test_checkは古さを検出し未決は落とさない(tmp_path: Path) -> None:
    """鮮度の食い違いだけが終了コード 1 の対象（`docs/publishing.md` §8）。"""
    dataset_dir = _dataset(tmp_path)
    spec = _spec()
    publish(dataset_dir, spec=spec)
    problems, blocked = check(dataset_dir, spec)
    assert problems == []
    assert blocked and "未決" in blocked[0]
    # 文書を足したら views と README が古くなる
    entry = _write_doc(dataset_dir, "nda-0002", "ct-a4-1col-mincho", pages=1, qa_items=len(QA_ITEMS))
    _enrich(dataset_dir, entry)
    _write_manifest(dataset_dir, [entry])
    stale, _ = check(dataset_dir, spec)
    assert any("views" in line for line in stale)


def test_ライセンスが決まればふさぐ条件が消える() -> None:
    assert blockers(_spec()) and not blockers(_spec("cc-by-4.0"))


def test_掃除から守るディレクトリに公開用の面が入っている() -> None:
    """`keiyaku clean --stale` は doc_id に無いディレクトリを消す。守らないと `views/` が消える。"""
    from keiyaku.cli import PROTECTED_DIRS

    assert {"search", "views", "licenses"} <= PROTECTED_DIRS
    assert PROTECTED_HINT <= PROTECTED_DIRS
