"""図の組立（v1 は K13 の時間軸のみ。本文が規範で、図は説明）。"""

from __future__ import annotations


def make_renewal_timeline(fig_id: str, notice_const: str) -> dict:
    """保守サポートの更新の時間軸（本体の timeline スキーマ）。"""
    ticks = ["期間の開始", "通知の期限", "期間の満了", "更新後の満了"]
    return {
        "type": "figure",
        "id": fig_id,
        "caption": "保守サポートの期間と更新の通知期限",
        "alt": (
            "保守サポートの期間の開始から更新後の満了までを一本の時間軸で示した図。"
            f"更新しない旨の通知の期限は、期間の満了の{{const:{notice_const}}}前に置かれる。"
            "通知が無い場合は、満了の後も同一の期間が続く。"
        ),
        "facts": [
            "起点は期間の開始である。",
            "通知の期限は期間の満了より前にある。",
            "通知が無いときは、満了の後に更新後の期間が続く。",
        ],
        "diagram": {
            "kind": "timeline",
            "unit": "label",
            "axis": {"start": ticks[0], "end": ticks[-1], "ticks": ticks},
            "spans": [
                {"id": "s1", "from": ticks[0], "to": ticks[2], "label": "当初の期間", "lane": 0},
                {"id": "s2", "from": ticks[0], "to": ticks[1], "label": "通知ができる期間", "lane": 1},
                {"id": "s3", "from": ticks[2], "to": ticks[3], "label": "更新後の期間", "lane": 2},
            ],
            "events": [
                {"id": "e1", "at": ticks[1], "label": "更新しない旨の通知"},
                {"id": "e2", "at": ticks[2], "label": "更新の成立"},
            ],
        },
    }
