"""パターンの登録。追加しても既存文書の出力が変わらないよう、選択は ID 順で安定させる。"""

from __future__ import annotations

from .base import PatternDef
from .k01_unit_price import PATTERN as K01
from .k02_fixed_metered import PATTERN as K02
from .k03_tiered_all import PATTERN as K03
from .k04_tiered_marginal import PATTERN as K04
from .k05_band import PATTERN as K05
from .k06_rate_on_base import PATTERN as K06
from .k07_proration import PATTERN as K07
from .k08_tax import PATTERN as K08
from .k09_rebate import PATTERN as K09
from .k10_price_revision import PATTERN as K10
from .k11_payment_due import PATTERN as K11
from .k12_period_end import PATTERN as K12
from .k13_renewal_notice import PATTERN as K13
from .k14_inspection import PATTERN as K14
from .k15_warranty_claim import PATTERN as K15
from .k16_survival import PATTERN as K16
from .k17_late_interest import PATTERN as K17
from .k18_breach_penalty import PATTERN as K18
from .k19_early_termination import PATTERN as K19
from .k20_liability_cap import PATTERN as K20
from .k21_indemnity_basket import PATTERN as K21
from .k22_sla_refund import PATTERN as K22
from .k23_termination import PATTERN as K23
from .k24_acceleration import PATTERN as K24
from .k25_confidential import PATTERN as K25
from .k26_force_majeure import PATTERN as K26
from .k27_minimum_purchase import PATTERN as K27
from .k28_procedure_figure import PATTERN as K28
from .k29_invoice_total import PATTERN as K29
from .k30_deposit_settlement import PATTERN as K30
from .k31_precedence import PATTERN as K31

_ALL: tuple[PatternDef, ...] = (
    K01,
    K02,
    K03,
    K04,
    K05,
    K06,
    K07,
    K08,
    K09,
    K10,
    K11,
    K12,
    K13,
    K14,
    K15,
    K16,
    K17,
    K18,
    K19,
    K20,
    K21,
    K22,
    K23,
    K24,
    K25,
    K26,
    K27,
    K28,
    K29,
    K30,
    K31,
)

#: 他のパターンの選択を前提にするもの（例：K13 は K12 の保守サポート期間に言い張る）
REQUIRES: dict[str, tuple[str, ...]] = {
    "K11": ("K01", "K02", "K03", "K04", "K05"),  # いずれか 1 つが選ばれていること（追加した手数料の支払期日）
    "K13": ("K12",),
    "K19": ("K02",),  # データ保管の手数料（月額）に付く
}

#: 同時に選ばない組（同じ事項の二重定義になる）
MUTEX: tuple[frozenset[str], ...] = (
    frozenset({"K03", "K04"}),
    frozenset({"K02", "K03"}),
    frozenset({"K02", "K04"}),
    frozenset({"K08", "K29"}),  # 消費税の加算の二重定義
    frozenset({"K06", "K29"}),  # どちらも対価の算定を組み替える
)


def all_patterns() -> tuple[PatternDef, ...]:
    return _ALL


def by_id(pattern_id: str) -> PatternDef:
    for p in _ALL:
        if p.id == pattern_id:
            return p
    raise KeyError(pattern_id)
