"""生成設定：プロファイル（難易度の軸ごとの出現割合。DESIGN.md §11.2）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    """軸ごとの出現割合。割合は 0〜1（文書ごとの乱数で引く）。"""

    name: str
    rules_min: int
    rules_max: int
    appendix_weight: float  # 段階表を別紙に分離する割合
    header_weight: float  # 月額・数量などの定数を頭書へ分離する割合（頭書を持つ文書のみ）
    scatter_weight: float  # 営業日の定義を独立の条へ分離する割合（複数ルールが使うときは常に分離）
    example_box_weight: float  # 計算例の箱（妨害・説明）を置く割合
    figure_weight: float  # K13 に時間軸の図（説明）を添える割合
    challenge: bool  # ラベル付きの難所を 1 件入れるか


PROFILES: dict[str, Profile] = {
    "basic": Profile("basic", 3, 4, 0.0, 0.0, 0.0, 0.0, 0.0, False),
    "standard": Profile("standard", 3, 6, 0.5, 0.5, 0.5, 0.3, 0.5, False),
    "hard": Profile("hard", 4, 6, 0.8, 0.8, 0.8, 0.6, 0.8, False),
    "challenge": Profile("challenge", 3, 6, 0.5, 0.5, 0.5, 0.3, 0.5, True),
}
