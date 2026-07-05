from dataclasses import dataclass

from invmmc.domain.entities import ExpenseRequest, UserContext
from invmmc.domain.enums import Role
from invmmc.domain.policies import required_roles_for_amount


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    required_roles: tuple[Role, ...]
    reason: str


class ApprovalService:
    def evaluate(
        self,
        expense: ExpenseRequest,
        approver: UserContext,
        flags: set[str] | None = None,
    ) -> ApprovalDecision:
        if expense.requester_id == approver.user_id:
            return ApprovalDecision(False, (), "requester_cannot_self_approve")

        required_roles = required_roles_for_amount(expense.amount, flags)
        has_required_role = any(role in approver.roles for role in required_roles)
        if not has_required_role:
            return ApprovalDecision(False, required_roles, "missing_required_role")

        project_scoped_roles = {
            Role.PROJECT_MANAGER,
            Role.PROJECT_MEMBER,
            Role.DEPARTMENT_HEAD,
        }
        if approver.roles & project_scoped_roles and expense.project_id not in approver.project_ids:
            return ApprovalDecision(False, required_roles, "approver_not_in_project_scope")

        return ApprovalDecision(True, required_roles, "approved_by_policy")
