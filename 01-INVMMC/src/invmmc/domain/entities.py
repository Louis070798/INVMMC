from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from invmmc.domain.enums import ExpenseStatus, Role, TransactionDirection


@dataclass(frozen=True)
class UserContext:
    user_id: str
    roles: set[Role]
    project_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class BudgetLine:
    project_id: str
    code: str
    name: str
    budget_amount: Decimal
    committed_amount: Decimal = Decimal("0")
    actual_amount: Decimal = Decimal("0")

    @property
    def available_amount(self) -> Decimal:
        return self.budget_amount - self.committed_amount - self.actual_amount


@dataclass(frozen=True)
class ExpenseRequest:
    request_id: str
    project_id: str
    requester_id: str
    amount: Decimal
    currency: str
    budget_line_code: str
    vendor_id: str | None
    description: str
    status: ExpenseStatus = ExpenseStatus.SUBMITTED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ExternalTransaction:
    provider: str
    external_id: str
    occurred_at: datetime
    amount: Decimal
    currency: str
    direction: TransactionDirection
    description: str
    counterparty_name: str | None = None
    counterparty_account: str | None = None
    raw: dict = field(default_factory=dict)
