"""`keiyaku/export.py` の `write_readme`（docs/remaining_issues.md Z 系）。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from keiyaku.export import write_readme
from keiyaku.publish import PublishSpec, load_spec
from keiyaku.publish import write_readme as write_card


def _merged_spec() -> PublishSpec:
    """検索評価セットを**本体に同梱する**宣言（切り出しを止めた場合）。"""
    spec = load_spec()
    return spec.model_copy(
        update={"search_dataset": spec.search_dataset.model_copy(update={"enabled": False})}
    )


def test_同梱するときは打ち切り件数を実測して埋める(tmp_path: Path) -> None:
    """クエリ数・打ち切り件数を固定値で焼き込まない。

    以前は README のテンプレートに「1,944 クエリ中 28 件」と直書きしており、
    文書構成が変わって実際の件数が動いても `keiyaku export` を再実行するだけでは
    更新されなかった（auto-0001 等の caption 修正だけで 1,944→1,946 に動いた）。
    検索評価セットを**別データセットに切り出した**いまは、この件数は検索側のカードが持つ
    （`docs/publishing.md` §12）ので、同梱する設定で縛る。
    """
    queries = [
        SimpleNamespace(related_truncated=True, query="個別契約"),
        SimpleNamespace(related_truncated=False, query="秘密情報"),
        SimpleNamespace(related_truncated=False, query="検収"),
    ]
    path = write_card(tmp_path, queries, spec=_merged_spec())
    text = path.read_text(encoding="utf-8")
    assert "3 クエリ中" in text
    assert "1 件" in text
    # **例に挙げる語も実測から出す**（保険の「事故」が焼き込まれていた。docs/decisions.md 105）
    assert "「個別契約」" in text
    assert "事故" not in text
    assert "{n_queries}" not in text
    assert "{n_truncated}" not in text
    assert "{truncated_examples}" not in text
    assert "search/passages.jsonl" in text, "同梱するなら本体の configs が指す"


def test_切り出したら本体のカードは検索の公開先を案内する(tmp_path: Path) -> None:
    """本体のカードから検索評価セットの行き先が分からないと、使う人が見つけられない。"""
    spec = load_spec()
    assert spec.search_split
    path = write_readme(tmp_path, [SimpleNamespace(related_truncated=True, query="個別契約")])
    text = path.read_text(encoding="utf-8")
    assert spec.search_dataset.hub.repo_id in text
    assert "クエリ中" not in text, "打ち切りの説明は検索側のカードが持つ（二重に書かない）"
    assert "search/passages.jsonl" not in text, "本体の configs は配らない面を指さない"


def test_write_readmeはqueriesが空でも書ける(tmp_path: Path) -> None:
    text = write_readme(tmp_path).read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "{n_queries}" not in text
    merged = write_card(tmp_path, (), spec=_merged_spec()).read_text(encoding="utf-8")
    assert "0 クエリ中" in merged
    assert "0 件" in merged
