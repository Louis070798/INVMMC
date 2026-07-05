from dataclasses import dataclass
from decimal import Decimal

from invmmc.domain.entities import BudgetLine


@dataclass(frozen=True)
class BudgetCheck:
    ok: bool
    available_amount: Decimal
    requested_amount: Decimal
    flags: set[str]


class BudgetService:
    def check(self, budget_line: BudgetLine, requested_amount: Decimal) -> BudgetCheck:
        flags: set[str] = set()
        if requested_amount > budget_line.available_amount:
            flags.add("budget_exceeded")
        if requested_amount >= budget_line.budget_amount * Decimal("0.8"):
            flags.add("large_single_spend")

        return BudgetCheck(
            ok="budget_exceeded" not in flags,
            available_amount=budget_line.available_amount,
            requested_amount=requested_amount,
            flags=flags,
        )
