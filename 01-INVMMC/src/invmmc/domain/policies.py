from dataclasses import dataclass
from decimal import Decimal

from invmmc.domain.enums import Role


@dataclass(frozen=True)
class ApprovalRequirement:
    max_amount: Decimal | None
    required_roles: tuple[Role, ...]


APPROVAL_MATRIX: tuple[ApprovalRequirement, ...] = (
    ApprovalRequirement(Decimal("2000000"), (Role.PROJECT_MANAGER,)),
    ApprovalRequirement(
        Decimal("20000000"),
        (Role.PROJECT_MANAGER, Role.FINANCE_CONTROLLER),
    ),
    ApprovalRequirement(
        Decimal("100000000"),
        (Role.DEPARTMENT_HEAD, Role.FINANCE_MANAGER),
    ),
    ApprovalRequirement(Decimal("500000000"), (Role.CFO,)),
    ApprovalRequirement(None, (Role.CEO,)),
)


ESCALATION_FLAGS = {
    "budget_exceeded",
    "new_vendor",
    "advance_payment",
    "cash_or_personal_wallet",
    "split_transaction_risk",
    "duplicate_risk",
}


def required_roles_for_amount(amount: Decimal, flags: set[str] | None = None) -> tuple[Role, ...]:
    flags = flags or set()
    if flags & ESCALATION_FLAGS:
        return (Role.CFO,)

    for row in APPROVAL_MATRIX:
        if row.max_amount is None or amount <= row.max_amount:
            return row.required_roles
    return (Role.CEO,)
