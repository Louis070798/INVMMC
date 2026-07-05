from dataclasses import dataclass
from decimal import Decimal

from invmmc.domain.entities import ExpenseRequest, ExternalTransaction


@dataclass(frozen=True)
class ReconciliationResult:
    matched: bool
    score: Decimal
    reason: str


class ReconciliationService:
    def match(self, expense: ExpenseRequest, transaction: ExternalTransaction) -> ReconciliationResult:
        reference = expense.request_id.upper()
        description = transaction.description.upper()
        amount_matches = expense.amount == transaction.amount
        reference_matches = reference in description

        if amount_matches and reference_matches:
            return ReconciliationResult(True, Decimal("1.0"), "amount_and_reference_match")
        if amount_matches:
            return ReconciliationResult(False, Decimal("0.6"), "amount_match_reference_missing")
        if reference_matches:
            return ReconciliationResult(False, Decimal("0.5"), "reference_match_amount_mismatch")
        return ReconciliationResult(False, Decimal("0.0"), "no_match")
