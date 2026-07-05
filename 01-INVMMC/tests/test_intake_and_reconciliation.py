from datetime import UTC, datetime
from decimal import Decimal

from invmmc.domain.entities import ExpenseRequest, ExternalTransaction
from invmmc.domain.enums import TransactionDirection
from invmmc.services.expense_intake import ExpenseIntakeService
from invmmc.services.reconciliation import ReconciliationService


def test_parse_new_expense_text() -> None:
    parsed = ExpenseIntakeService().parse_text("1200000 PRJ001 marketing ads Meta")

    assert parsed.amount == Decimal("1200000")
    assert parsed.project_code == "PRJ001"


def test_reconciliation_matches_reference_and_amount() -> None:
    expense = ExpenseRequest(
        request_id="REQ-2026-0001",
        project_id="PRJ001",
        requester_id="u1",
        amount=Decimal("1200000"),
        currency="VND",
        budget_line_code="MKT",
        vendor_id="vendor-1",
        description="Marketing ads",
    )
    transaction = ExternalTransaction(
        provider="bank",
        external_id="txn-1",
        occurred_at=datetime.now(UTC),
        amount=Decimal("1200000"),
        currency="VND",
        direction=TransactionDirection.OUTBOUND,
        description="INVMMC-PRJ001-REQ-2026-0001",
    )

    result = ReconciliationService().match(expense, transaction)

    assert result.matched is True
    assert result.reason == "amount_and_reference_match"
