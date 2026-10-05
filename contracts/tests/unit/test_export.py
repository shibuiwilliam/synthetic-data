"""`keiyaku/export.py` の `write_readme`（docs/remaining_issues.md Z 系）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from keiyaku.export import write_readme


def test_write_readmeはqueriesの実測値を埋め込む(tmp_path: Path) -> None:
    """クエリ数・打ち切り件数を固定値で焼き込まない。

    以前は README のテンプレートに「1,944 クエリ中 28 件」と直書きしており、
    文書構成が変わって実際の件数が動いても `keiyaku export` を再実行するだけでは
    更新されなかった（auto-0001 等の caption 修正だけで 1,944→1,946 に動いた）。
    """
    queries = [
        SimpleNamespace(related_truncated=True, query="個別契約"),
        SimpleNamespace(related_truncated=False, query="秘密情報"),
        SimpleNamespace(related_truncated=False, query="検収"),
    ]
    path = write_readme(tmp_path, queries)
    text = path.read_text(encoding="utf-8")
    assert "3 クエリ中" in text
    assert "1 件" in text
    # **例に挙げる語も実測から出す**（保険の「事故」が焼き込まれていた。docs/decisions.md 105）
    assert "「個別契約」" in text
    assert "事故" not in text
    assert "{n_queries}" not in text
    assert "{n_truncated}" not in text
    assert "{truncated_examples}" not in text


def test_write_readmeはqueriesが空でも書ける(tmp_path: Path) -> None:
    path = write_readme(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "0 クエリ中" in text
    assert "0 件" in text
