from enum import StrEnum


class Role(StrEnum):
    EMPLOYEE = "employee"
    PROJECT_MEMBER = "project_member"
    PROJECT_MANAGER = "project_manager"
    DEPARTMENT_HEAD = "department_head"
    FINANCE_CONTROLLER = "finance_controller"
    FINANCE_MANAGER = "finance_manager"
    ACCOUNTANT = "accountant"
    TREASURY = "treasury"
    CFO = "cfo"
    CEO = "ceo"
    SYSTEM_ADMIN = "system_admin"
    AUDITOR = "auditor"


class ExpenseStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    FINANCE_CHECKED = "finance_checked"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PAID = "paid"
    RECONCILED = "reconciled"
    CLOSED = "closed"
    REJECTED = "rejected"
    NEED_INFO = "need_info"


class TransactionDirection(StrEnum):
    INBOUND = "in"
    OUTBOUND = "out"
