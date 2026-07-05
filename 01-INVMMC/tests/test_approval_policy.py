from decimal import Decimal

from invmmc.domain.entities import ExpenseRequest, UserContext
from invmmc.domain.enums import Role
from invmmc.services.approval import ApprovalService


def make_expense(amount: str = "1000000") -> ExpenseRequest:
    return ExpenseRequest(
        request_id="REQ-2026-0001",
        project_id="PRJ001",
        requester_id="u-requester",
        amount=Decimal(amount),
        currency="VND",
        budget_line_code="OPS",
        vendor_id="vendor-1",
        description="Office expense",
    )


def test_project_manager_can_approve_small_project_expense() -> None:
    expense = make_expense("1000000")
    approver = UserContext(
        user_id="u-pm",
        roles={Role.PROJECT_MANAGER},
        project_ids={"PRJ001"},
    )

    decision = ApprovalService().evaluate(expense, approver)

    assert decision.allowed is True
    assert decision.reason == "approved_by_policy"


def test_requester_cannot_self_approve() -> None:
    expense = make_expense("1000000")
    approver = UserContext(
        user_id="u-requester",
        roles={Role.PROJECT_MANAGER},
        project_ids={"PRJ001"},
    )

    decision = ApprovalService().evaluate(expense, approver)

    assert decision.allowed is False
    assert decision.reason == "requester_cannot_self_approve"


def test_budget_exception_escalates_to_cfo() -> None:
    expense = make_expense("1000000")
    approver = UserContext(
        user_id="u-pm",
        roles={Role.PROJECT_MANAGER},
        project_ids={"PRJ001"},
    )

    decision = ApprovalService().evaluate(expense, approver, flags={"budget_exceeded"})

    assert decision.allowed is False
    assert decision.required_roles == (Role.CFO,)
