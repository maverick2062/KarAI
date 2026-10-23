"""Income tax slabs for resident individuals below 60 years, FY 2026-27.

IMPORTANT — these mirror the last publicly documented slabs (Union Budget
2025, carried forward as the assumed FY2026-27 baseline) as known at this
codebase's write time. They are NOT verified against any Finance Bill or CBDT
notification specific to FY2026-27, which may have changed them. Every
consumer of this module must surface ``SLAB_DISCLAIMER``, and this table
must be reconciled against the actual, current Finance Act before being used
for a real filing decision.

Deliberately out of scope for this prototype (would need real slab data and
non-trivial marginal-relief logic, not appropriate to guess at): senior/
super-senior citizen slabs, surcharge (applies above ₹50L income with
marginal relief), and non-resident-specific slabs.
"""

from dataclasses import dataclass
from decimal import Decimal

SLAB_VERSION = "FY2026-27-v1-advisory"

SLAB_DISCLAIMER = (
    "AI-assisted, advisory only. Tax slabs mirror the last publicly known "
    "Finance Bill and are NOT confirmed for FY2026-27. Surcharge and senior-"
    "citizen slabs are not computed. Verify with a Chartered Accountant or "
    "the CBDT notification in force before relying on this for a filing or "
    "payment decision."
)

CESS_RATE = Decimal("0.04")  # Health & Education Cess, applied on tax + surcharge (surcharge not modeled)


@dataclass(frozen=True)
class SlabBand:
    lower: Decimal
    upper: Decimal | None  # None = no upper bound
    rate: Decimal


NEW_REGIME_SLABS: tuple[SlabBand, ...] = (
    SlabBand(Decimal("0"), Decimal("400000"), Decimal("0")),
    SlabBand(Decimal("400000"), Decimal("800000"), Decimal("0.05")),
    SlabBand(Decimal("800000"), Decimal("1200000"), Decimal("0.10")),
    SlabBand(Decimal("1200000"), Decimal("1600000"), Decimal("0.15")),
    SlabBand(Decimal("1600000"), Decimal("2000000"), Decimal("0.20")),
    SlabBand(Decimal("2000000"), Decimal("2400000"), Decimal("0.25")),
    SlabBand(Decimal("2400000"), None, Decimal("0.30")),
)
NEW_REGIME_87A_REBATE_INCOME_LIMIT = Decimal("1200000")  # rebate makes tax nil up to this income
NEW_REGIME_87A_MAX_REBATE = Decimal("60000")

OLD_REGIME_SLABS: tuple[SlabBand, ...] = (
    SlabBand(Decimal("0"), Decimal("250000"), Decimal("0")),
    SlabBand(Decimal("250000"), Decimal("500000"), Decimal("0.05")),
    SlabBand(Decimal("500000"), Decimal("1000000"), Decimal("0.20")),
    SlabBand(Decimal("1000000"), None, Decimal("0.30")),
)
OLD_REGIME_87A_REBATE_INCOME_LIMIT = Decimal("500000")
OLD_REGIME_87A_MAX_REBATE = Decimal("12500")
