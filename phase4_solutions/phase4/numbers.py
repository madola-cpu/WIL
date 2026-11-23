"""Exact money and rounding helpers.

All money math runs in Decimal so results match the reference reports to the
dollar (float math turns 60 x 48 x 90 x 0.7 into 181439.99999999997).
Rounding is always half-up, like a spreadsheet, never Python's half-to-even.
"""
from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Optional, Union

Number = Union[int, float, Decimal]
SCENARIOS = ("low", "base", "high")


def D(x: Number) -> Decimal:
    """Convert to Decimal without float noise."""
    if isinstance(x, Decimal):
        return x
    if isinstance(x, bool):
        raise TypeError("booleans are not numbers here")
    if isinstance(x, int):
        return Decimal(x)
    return Decimal(str(x))


def round_half_up(x: Number, places: int = 0) -> Decimal:
    return D(x).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def round_to_step(x: Number, step: Number = 1, mode: str = "nearest") -> Decimal:
    """Round to a multiple of step ('nearest' is half-up)."""
    step_d = D(step)
    units = D(x) / step_d
    rounding = {"nearest": ROUND_HALF_UP, "up": ROUND_CEILING, "down": ROUND_FLOOR}[mode]
    return units.quantize(Decimal(1), rounding=rounding) * step_d


def to_int(x: Number) -> int:
    return int(round_half_up(x, 0))


def to_1dp(x: Number) -> float:
    return float(round_half_up(x, 1))


def clean(x: Number) -> Union[int, float]:
    """Return an int when the value is whole, else a float (for JSON)."""
    d = D(x)
    if d == d.to_integral_value():
        return int(d)
    return float(d)


def payback_months(year_one_cost: Number, annual_savings: Number) -> Optional[float]:
    """Months of savings needed to repay the year-one cost (1 decimal).

    0.0 means immediate (no cost); None means it never pays back.
    """
    savings = D(annual_savings)
    cost = D(year_one_cost)
    if cost <= 0:
        return 0.0
    if savings <= 0:
        return None
    return to_1dp(cost / (savings / 12))


def fmt_money(x: Optional[Number], currency: str = "USD") -> str:
    if x is None:
        return "n/a"
    symbol = "$" if currency == "USD" else currency + " "
    value = to_int(x)
    sign = "-" if value < 0 else ""
    return f"{sign}{symbol}{abs(value):,}"


def fmt_num(x: Optional[Number]) -> str:
    if x is None:
        return "n/a"
    v = clean(x)
    if isinstance(v, int):
        return f"{v:,}"
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def fmt_pct(x: Number, places: int = 0) -> str:
    return f"{float(round_half_up(D(x) * 100, places)):.{places}f}%"


def fmt_payback(months: Optional[float]) -> str:
    if months is None:
        return "Does not pay back"
    if months == 0:
        return "Immediate (no cost)"
    return f"{months:.1f}"
