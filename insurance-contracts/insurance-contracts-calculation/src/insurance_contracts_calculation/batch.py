"""複数の文書をまとめて生成する。

失敗した文書は**黙って外さず**、原因と再現コマンドを記録する（TASK.md S6-1）。
ページ余裕の足りない content は最初から対象に入れない。
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from . import base_adapter as ba
from . import config as cfg
from .generate import generate
from .verify.gates import GateFailure

#: 1 ルールが使うおおよその字数（実測の平均。候補の選別にだけ使う）
CHARS_PER_RULE = 420


@dataclass
class Target:
    content_id: str
    base: Path
    genre: str
    slack: float
    char_slack: int = 0


def candidates(genres: list[str] | None, content_ids: list[str] | None, min_slack: float) -> list[Target]:
    """ページ余裕で候補を選別する（`TASK.md` §2.2・§5 R2）。"""
    ids = content_ids or [
        cid for cid in ba.available_bases() if not genres or cid.rsplit("-", 1)[0] in genres
    ]
    out: list[Target] = []
    for cid in ids:
        try:
            base = ba.load_base(ba.find_base(cid))
            b = ba.budget(base.data, base.genre)
            if any(f.severity == "error" for f in ba.lint(base.data)):
                continue  # 既定の約款そのものが未完成（執筆途中）なら対象にしない
        except Exception:  # noqa: BLE001  読めない content は候補から外す（理由は呼び出し側で記録）
            continue
        slack = b["page_max"] - b["pages"]
        char_slack = b["chars_max"] - b["chars"]
        # ページにも字数にも、ルールを 2 件足せるだけの余裕があるものだけを対象にする
        if slack >= min_slack and char_slack >= 2 * CHARS_PER_RULE:
            out.append(Target(cid, base.path, base.genre, round(slack, 2), char_slack))
    return out


def _profile_for(args, genre: str, index: int) -> str:
    """この文書に使うプロファイル。`--profile-mix` を渡すと順に配る。

    1 つのプロファイルだけで作ると、難易度の軸（分散・図だけが規範）が `scatter` の値に
    縛られる。種目ごとに順に配ると、どの種目にも 3 水準が入り、配り方が決定的になる。
    """
    mix = getattr(args, "profile_mix", None)
    if not mix:
        return args.profile
    return mix[index % len(mix)]


def run_batch(args) -> dict:
    settings = cfg.Settings.of(
        args.profile,
        render=not args.no_render,
        png=not args.no_png,
        styles=tuple(getattr(args, "styles", None) or ()),
        multi_style=bool(getattr(args, "multi_style", False)),
        variant=int(getattr(args, "variant", 1) or 1),
    )
    targets = candidates(args.genres, args.content_ids, args.min_slack)
    by_genre: dict[str, list[Target]] = {}
    for t in targets:
        by_genre.setdefault(t.genre, []).append(t)

    ok, failed = [], []
    tried: list[str] = []
    for genre in sorted(by_genre):
        made = 0
        for t in by_genre[genre]:
            # 目標の本数に達したら、残りの候補には手を付けない
            if made >= args.per_genre:
                break
            tried.append(t.content_id)
            profile = _profile_for(args, genre, made)
            doc_settings = replace(settings, profile=cfg.PROFILES[profile])
            try:
                result = _generate_with_retry(t, args, doc_settings)
                made += 1
                ok.append(
                    {
                        "content_id": result.content_id,
                        "genre": t.genre,
                        "seed": result.manifest["seed"],
                        "profile": profile,
                        "rules": len(result.manifest["plan"]["rules"]),
                        "cases": result.manifest["counts"]["cases"],
                        "pages": result.manifest["pages"],
                    }
                )
            except GateFailure as e:
                failed.append(
                    {
                        "content_id": t.content_id,
                        "genre": t.genre,
                        "reason": "gate",
                        "gates": [r.code for r in e.failed],
                        "detail": str(e)[:400],
                        "repro": _repro(t, args, profile),
                    }
                )
            except Exception as e:  # noqa: BLE001
                failed.append(
                    {
                        "content_id": t.content_id,
                        "genre": t.genre,
                        "reason": type(e).__name__,
                        "detail": str(e)[:400],
                        "repro": _repro(t, args, profile),
                    }
                )
    skipped = [t.content_id for t in targets if t.content_id not in tried]
    considered = set(args.content_ids or []) or {
        cid for cid in ba.available_bases() if not args.genres or cid.rsplit("-", 1)[0] in args.genres
    }
    excluded = sorted(considered - {t.content_id for t in targets})
    report = {
        "generated": len(ok),
        "failed": len(failed),
        "documents": ok,
        "failures": failed,
        "skipped_for_count": skipped,
        "excluded_for_budget": excluded,
    }
    if ok and not getattr(args, "no_datacard", False):
        # データを足したらデータカードを更新する（`docs/data_card.md` §5）
        from .export.datacard import write_card

        report["data_card"] = str(write_card(Path(args.out)))
    return report


#: 描画で落ちたときに組み直す条件（ルール数の上限, seed のずらし幅）。
#: 本体の描画は内容の長さに敏感で、同じ内容でも数十字ぶん変えると通ることがある
#: （段の境目に脚注が乗ると、その脚注がPDFに出ない）。seed を変えると語や値が変わり長さが動く。
RETRIES: tuple[tuple[int | None, int], ...] = (
    (None, 0),
    (None, 100),
    (None, 200),
    (4, 0),
    (4, 300),
    (3, 0),
    (3, 400),
    (2, 500),
)


#: 同じ既定の約款から 2 本目以降を作るときに、種をずらす幅。
#: 乱数の鍵は「既定の約款のID : seed : 用途」なので、**種を変えないと番号だけ変えても同じ本になる**。
VARIANT_SEED_STEP = 1000


def _generate_with_retry(t: Target, args, settings: cfg.Settings):
    """描画・検証で落ちた文書は、条件を変えて組み直す。

    黙って減らさない。使った条件は manifest の `seed` と `plan.skipped` に残る。
    2 本目以降（`--variant`）は、**先に作った本と同じ規定になっていないこと**も確かめる。
    """
    base_seed = args.seed + (settings.variant - 1) * VARIANT_SEED_STEP
    last: Exception | None = None
    for limit, seed_shift in RETRIES:
        try:
            result = generate(t.base, args.out, base_seed + seed_shift, replace(settings, rule_limit=limit))
        except (GateFailure, AssertionError, RuntimeError) as e:
            last = e
            continue
        if settings.variant > 1 and _duplicates_earlier_variant(Path(args.out), t, settings.variant, result):
            shutil.rmtree(result.out_dir, ignore_errors=True)
            last = RuntimeError(
                f"{result.content_id}: 先に作った本と同じ規定になった（種をずらして組み直す）"
            )
            continue
        return result
    raise last if last is not None else RuntimeError("生成できなかった")


def _duplicates_earlier_variant(out: Path, t: Target, variant: int, result) -> bool:
    """同じ既定の約款から先に作った本と、規定の顔ぶれが同じかどうか。

    同じなら本が 1 冊増えただけで中身は増えないので、種をずらして組み直す。
    """
    from .generate import doc_suffix

    mine = set(result.manifest["plan"]["rules"])
    for n in range(1, variant):
        path = out / f"{t.content_id}-{doc_suffix(n)}" / "calc" / "manifest.json"
        if not path.is_file():
            continue
        if set(json.loads(path.read_text(encoding="utf-8"))["plan"]["rules"]) == mine:
            return True
    return False


def _repro(t: Target, args, profile: str) -> str:
    variant = int(getattr(args, "variant", 1) or 1)
    seed = args.seed + (variant - 1) * VARIANT_SEED_STEP
    return (
        "PYTHONPATH=src python -m insurance_contracts_calculation.cli generate "
        f"--base {t.base} --out {args.out} --seed {seed} --profile {profile} --variant {variant}"
    )
