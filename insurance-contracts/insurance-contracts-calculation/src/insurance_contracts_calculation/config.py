"""生成の設定（プロファイル、難易度、件数）。

既定値はここにあり、`icc generate --profile` と設定ファイルで上書きできる。
値をコードに散らさないための置き場である（DESIGN.md §13）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Profile:
    """難易度プロファイル（DESIGN.md §9.2）。"""

    name: str
    rules_min: int
    rules_max: int
    #: 表現手段の出現の重み（0〜1。手順ごとに引く）
    weights: dict[str, float] = field(default_factory=dict)
    #: 図だけが規範のルールを混ぜる割合
    figure_only: float = 0.0
    #: 別表・特約への分離を選ぶ割合
    scatter: float = 0.0
    #: 1 ルールあたりの乱数ケース数
    random_cases: int = 12
    #: 設例の数（囲みに書く件数の上限）
    examples: int = 2


PROFILES: dict[str, Profile] = {
    "basic": Profile(
        "basic", 3, 3, {"formula": 0.8, "table": 0.3, "figure": 0.0}, figure_only=0.0, scatter=0.0
    ),
    "standard": Profile(
        "standard", 3, 5, {"formula": 0.5, "table": 0.6, "figure": 0.3}, figure_only=0.2, scatter=0.3
    ),
    "hard": Profile(
        "hard", 4, 6, {"formula": 0.2, "table": 0.7, "figure": 0.7}, figure_only=0.5, scatter=0.7
    ),
}

DEFAULT_PROFILE = "standard"

#: 種目ごとの「既定のスタイルに足して描けるスタイル」（`--multi-style`。`HITL.md` H3 (c)）。
#: 同じ `policy.json`・同じ `calc/` を別のレイアウトで描き、**文書数を増やさずに**
#: レイアウト頑健性の評価データを増やす。
#:
#: 選定の根拠は本体の実績である。本体 `docs/decisions.md` で、`travel-0005` は
#: `travel-a4-1col-gothic` と `nl-a4-1col-gothic` の 2 style、`group-0004` は
#: `grp-a4land-2col-plain` で描けている。段組の数が既定と同じか、より詰まるものを選ぶ
#: （1 段組にすると 20 ページを超えやすい。`auto-0001` は `nl-a4-1col-gothic` で 23 ページ）。
#: 通らなかったスタイルは**そのスタイルだけ外して記録する**（文書は捨てない）。
EXTRA_STYLES: dict[str, tuple[str, ...]] = {
    "auto": ("nl-b5-2col-dense", "nl-a4-2col-gothic-plain"),
    "quake": ("nl-a4-2col-mincho", "nl-a4-2col-gothic-plain"),
    "health": ("nl-b5-2col-dense", "nl-a4-2col-gothic-plain"),
    "oneday": ("nl-a4-2col-mincho", "nl-b5-2col-dense"),
    "travel": ("nl-a4-1col-gothic", "nl-a4-2col-mincho"),
    "golf": ("nl-b5-2col-dense", "nl-a4-2col-mincho"),
    "group": ("grp-a4land-2col-plain",),
    "life": ("life-a4-1col-gothic",),
}


@dataclass(frozen=True)
class Settings:
    profile: Profile = PROFILES[DEFAULT_PROFILE]
    #: 20 ページを超えないようにする上限（本体の MAX_PAGES を既定にする）
    max_pages: int = 20
    #: 実レンダリングまで行うか（PDF を作らないと verify できない）
    render: bool = True
    #: PNG も出すか（目視確認に使う。遅い）
    png: bool = True
    #: challenge モード（欠落・矛盾・異例をラベル付きで入れる）
    challenge: bool = False
    #: 不明値のケースを作るか
    unknown_cases: bool = True
    #: ルール数の上限を外から下げる（描画で落ちた文書を組み直すときに使う）
    rule_limit: int | None = None
    #: 描くスタイル。空なら blueprint の既定スタイル 1 つだけ。
    #: 2 つ以上渡すと**同じ `policy.json`・同じ `calc/` を複数のレイアウトで描く**
    #: （`HITL.md` H3 (c)。文書数を増やさずレイアウト頑健性の評価データを増やす）
    styles: tuple[str, ...] = ()
    #: `EXTRA_STYLES` の種目ごとの既定を使う（`styles` を明示したときはそちらが優先）
    multi_style: bool = False
    #: 同じ既定の約款から作る何本目か。文書IDの接尾になる（1 なら `-c1`、2 なら `-c2`）。
    #: **乱数には入れない。** 種を変えずに番号だけ変えても中身は同じものになるので、
    #: 別の本を作るときは `seed` も変える（`batch` は `--variant` に応じて種をずらす）。
    variant: int = 1

    @staticmethod
    def of(profile: str = DEFAULT_PROFILE, **kw) -> Settings:
        if profile not in PROFILES:
            raise ValueError(f"知らないプロファイル: {profile}（{'/'.join(PROFILES)}）")
        if "styles" in kw and kw["styles"] is not None:
            kw["styles"] = tuple(kw["styles"])
        return Settings(profile=PROFILES[profile], **kw)
