from decimal import Decimal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str


class ExpenseCreateRequest(BaseModel):
    project_id: str
    requester_id: str
    amount: Decimal = Field(gt=0)
    currency: str = "VND"
    budget_line_code: str
    vendor_id: str | None = None
    description: str


class ExpenseCreateResponse(BaseModel):
    request_id: str
    status: str
    required_roles: list[str]


class ApprovalPreviewRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    flags: set[str] = Field(default_factory=set)


class ApprovalPreviewResponse(BaseModel):
    required_roles: list[str]


class ProjectCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=30)
    name: str
    owner: str
    department: str
    budget_amount: Decimal = Field(gt=0)


class ProjectResponse(BaseModel):
    id: str
    code: str
    name: str
    owner: str
    department: str
    budget_amount: Decimal
    status: str


class IntegrationUpdateRequest(BaseModel):
    enabled: bool | None = None
    status: str | None = None
    config: dict = Field(default_factory=dict)


class IntegrationResponse(BaseModel):
    key: str
    provider: str
    display_name: str
    enabled: bool
    status: str
    config: dict


class AttachmentUpdateRequest(BaseModel):
    transaction_type: str | None = Field(default=None, pattern="^(thu|chi|unknown)$")
    amount_hint: Decimal | None = Field(default=None, ge=0)
    project_code: str | None = None  # "" de bo gan du an
    counterparty: str | None = Field(default=None, max_length=240)
    bank_name: str | None = Field(default=None, max_length=120)
    reference: str | None = Field(default=None, max_length=240)
    transacted_at: str | None = Field(default=None, max_length=60)
    note: str | None = None
    review_status: str | None = Field(default=None, pattern="^(pending_review|confirmed)$")
    status: str | None = Field(default=None, pattern="^(unmatched|matched|rejected)$")


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthUserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    roles: list[str]
