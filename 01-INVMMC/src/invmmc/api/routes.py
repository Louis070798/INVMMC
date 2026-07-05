import csv
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse, RedirectResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from invmmc.api.schemas import (
    ApprovalPreviewRequest,
    ApprovalPreviewResponse,
    AttachmentUpdateRequest,
    AuthUserResponse,
    ExpenseCreateRequest,
    ExpenseCreateResponse,
    HealthResponse,
    IntegrationResponse,
    IntegrationUpdateRequest,
    LoginRequest,
    ProjectCreateRequest,
    ProjectResponse,
)
from invmmc.core.config import settings
from invmmc.core.database import get_db
from invmmc.core.security import verify_shared_secret
from invmmc.domain.enums import Role
from invmmc.domain.policies import required_roles_for_amount
from invmmc.integrations.bank import GenericBankAdapter
from invmmc.integrations.momo import MomoAdapter
from invmmc.integrations.telegram import (
    TelegramBotClient,
    TelegramUpdateHandler,
    attachment_keyboard,
    duplicate_keyboard,
)
from invmmc.core.imaging import dhash_hex
from invmmc.persistence.models import (
    ExpenseRequestModel,
    IntegrationConfigModel,
    ProjectModel,
    TransferAttachmentModel,
)
from invmmc.services.auth import (
    CONFIG_ROLES,
    FINANCE_READ_ROLES,
    FINANCE_WRITE_ROLES,
    SESSION_COOKIE_NAME,
    AuthUser,
    authenticate_user,
    create_session,
    get_current_user,
    optional_current_user,
    require_roles,
    revoke_session,
)
from invmmc.services.integration_health import enrich_integration_status
from invmmc.services.report_export import (
    build_project_report_xlsx,
    build_transfer_report_xlsx,
    period_display_label,
)
from invmmc.services.reporting import (
    attachment_dict,
    dashboard_summary,
    project_report_rows,
    resolve_report_range,
    transfer_report_rows,
)
from invmmc.services.telegram_commands import TelegramCommandService
from invmmc.services.telegram_intake import (
    TelegramAttachmentService,
    build_duplicate_warning,
    build_intake_reply,
)

router = APIRouter()


@router.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/dashboard")


@router.get("/login", include_in_schema=False, response_model=None)
async def login_page(user: AuthUser | None = Depends(optional_current_user)):
    if user:
        return RedirectResponse(url="/dashboard")
    return FileResponse(Path(__file__).resolve().parents[1] / "static" / "login.html")


@router.get("/dashboard", include_in_schema=False, response_model=None)
async def dashboard(user: AuthUser | None = Depends(optional_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    return FileResponse(Path(__file__).resolve().parents[1] / "static" / "dashboard.html")


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name)


@router.post("/api/v1/auth/login", response_model=AuthUserResponse)
async def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthUserResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    token = create_session(db, user)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7 * 24 * 60 * 60,
    )
    roles = json.loads(user.roles_json or "[]")
    return AuthUserResponse(id=user.id, email=user.email, full_name=user.full_name, roles=roles)


@router.post("/api/v1/auth/logout")
async def logout(
    response: Response,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    revoke_session(db, session_token)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/api/v1/auth/me", response_model=AuthUserResponse)
async def me(user: AuthUser = Depends(get_current_user)) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=sorted(role.value for role in user.roles),
    )


@router.post("/api/v1/approval/preview", response_model=ApprovalPreviewResponse)
async def approval_preview(payload: ApprovalPreviewRequest) -> ApprovalPreviewResponse:
    roles = required_roles_for_amount(payload.amount, payload.flags)
    return ApprovalPreviewResponse(required_roles=[role.value for role in roles])


@router.get("/api/v1/dashboard/summary")
async def get_dashboard_summary(
    period: str = Query(default="month", pattern="^(day|week|month)$"),
    project_id: str | None = None,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_READ_ROLES)),
) -> dict:
    return dashboard_summary(db, period, project_id)


@router.get("/api/v1/projects", response_model=list[ProjectResponse])
async def list_projects(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_READ_ROLES)),
) -> list[ProjectResponse]:
    projects = db.scalars(select(ProjectModel).order_by(ProjectModel.code)).all()
    return [
        ProjectResponse(
            id=project.id,
            code=project.code,
            name=project.name,
            owner=project.owner,
            department=project.department,
            budget_amount=project.budget_amount,
            status=project.status,
        )
        for project in projects
    ]


@router.post("/api/v1/projects", response_model=ProjectResponse)
async def create_project(
    payload: ProjectCreateRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_WRITE_ROLES)),
) -> ProjectResponse:
    existing = db.scalar(select(ProjectModel).where(ProjectModel.code == payload.code.upper()))
    if existing:
        raise HTTPException(status_code=409, detail="project_code_exists")

    project = ProjectModel(
        id=f"prj-{uuid4().hex[:12]}",
        code=payload.code.upper(),
        name=payload.name,
        owner=payload.owner,
        department=payload.department,
        budget_amount=payload.budget_amount,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse(
        id=project.id,
        code=project.code,
        name=project.name,
        owner=project.owner,
        department=project.department,
        budget_amount=project.budget_amount,
        status=project.status,
    )


@router.post("/api/v1/expenses", response_model=ExpenseCreateResponse)
async def create_expense(
    payload: ExpenseCreateRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_WRITE_ROLES)),
) -> ExpenseCreateResponse:
    project = db.get(ProjectModel, payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project_not_found")

    request_id = f"REQ-{uuid4().hex[:12].upper()}"
    roles = required_roles_for_amount(payload.amount)
    db.add(
        ExpenseRequestModel(
            id=request_id,
            project_id=project.id,
            requester_id=payload.requester_id,
            amount=payload.amount,
            currency=payload.currency,
            budget_line_code=payload.budget_line_code,
            vendor_id=payload.vendor_id,
            description=payload.description,
            status="submitted",
        )
    )
    db.commit()
    return ExpenseCreateResponse(
        request_id=request_id,
        status="submitted",
        required_roles=[role.value for role in roles],
    )


@router.get("/api/v1/attachments")
async def list_attachments(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_READ_ROLES)),
) -> list[dict]:
    rows = db.scalars(
        select(TransferAttachmentModel)
        .order_by(TransferAttachmentModel.received_at.desc())
        .limit(limit)
    ).all()
    return [attachment_dict(row) for row in rows]


@router.post("/api/v1/attachments")
async def create_attachment(
    project_code: str = Form(default=""),
    transaction_type: str = Form(default="unknown"),
    amount: str = Form(default=""),
    counterparty: str = Form(default=""),
    bank_name: str = Form(default=""),
    reference: str = Form(default=""),
    transacted_at: str = Form(default=""),
    note: str = Form(default=""),
    caption: str = Form(default=""),
    force: bool = Form(default=False),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_WRITE_ROLES)),
) -> dict:
    if transaction_type not in {"thu", "chi", "unknown"}:
        raise HTTPException(status_code=400, detail="invalid_transaction_type")

    amount_value: Decimal | None = None
    if amount.strip():
        try:
            amount_value = Decimal(amount.strip().replace(",", "").replace(".", ""))
        except InvalidOperation as error:
            raise HTTPException(status_code=400, detail="invalid_amount") from error

    project = None
    if project_code.strip():
        project = db.scalar(
            select(ProjectModel).where(ProjectModel.code == project_code.strip().upper())
        )
        if not project:
            raise HTTPException(status_code=404, detail="project_not_found")

    file_path: str | None = None
    file_name = "manual-entry"
    file_sha256: str | None = None
    file_dhash: str | None = None
    if file and file.filename:
        content = await file.read()
        if content:
            target_dir = Path(settings.upload_dir) / "dashboard"
            target_dir.mkdir(parents=True, exist_ok=True)
            extension = Path(file.filename).suffix or ".jpg"
            local = target_dir / f"{uuid4().hex}{extension}"
            local.write_bytes(content)
            file_path = str(local)
            file_name = file.filename
            file_sha256 = hashlib.sha256(content).hexdigest()
            file_dhash = dhash_hex(local)

            if not force:
                from invmmc.services.telegram_intake import TelegramAttachmentService

                if TelegramAttachmentService._is_visual_duplicate(db, file_sha256, file_dhash):
                    local.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=409,
                        detail="duplicate_image",
                    )

    attachment = TransferAttachmentModel(
        id=f"att-{uuid4().hex[:12]}",
        project_id=project.id if project else None,
        source="dashboard",
        file_name=file_name,
        file_path=file_path,
        file_sha256=file_sha256,
        file_dhash=file_dhash,
        caption=caption.strip(),
        amount_hint=amount_value,
        status="unmatched",
        transaction_type=transaction_type,
        review_status="pending_review",
        counterparty=counterparty.strip()[:240],
        bank_name=bank_name.strip()[:120],
        reference=reference.strip()[:240],
        transacted_at=transacted_at.strip()[:60],
        note=note.strip(),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment_dict(attachment)


@router.patch("/api/v1/attachments/{attachment_id}")
async def update_attachment(
    attachment_id: str,
    payload: AttachmentUpdateRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_WRITE_ROLES)),
) -> dict:
    attachment = db.get(TransferAttachmentModel, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="attachment_not_found")

    if payload.project_code is not None:
        code = payload.project_code.strip().upper()
        if not code:
            attachment.project_id = None
        else:
            project = db.scalar(select(ProjectModel).where(ProjectModel.code == code))
            if not project:
                raise HTTPException(status_code=404, detail="project_not_found")
            attachment.project_id = project.id

    if payload.transaction_type is not None:
        attachment.transaction_type = payload.transaction_type
    if payload.amount_hint is not None:
        attachment.amount_hint = payload.amount_hint
    if payload.counterparty is not None:
        attachment.counterparty = payload.counterparty
    if payload.bank_name is not None:
        attachment.bank_name = payload.bank_name
    if payload.reference is not None:
        attachment.reference = payload.reference
    if payload.transacted_at is not None:
        attachment.transacted_at = payload.transacted_at
    if payload.note is not None:
        attachment.note = payload.note
    if payload.status is not None:
        attachment.status = payload.status

    if payload.review_status == "confirmed":
        if attachment.transaction_type not in {"thu", "chi"}:
            raise HTTPException(status_code=400, detail="missing_transaction_type")
        if attachment.amount_hint is None:
            raise HTTPException(status_code=400, detail="missing_amount")
        if attachment.project_id is None:
            raise HTTPException(status_code=400, detail="missing_project")
        attachment.review_status = "confirmed"
    elif payload.review_status == "pending_review":
        attachment.review_status = "pending_review"
    elif payload.review_status is None and attachment.review_status == "confirmed":
        # Sua noi dung chung tu da xac nhan thi quay ve cho duyet lai.
        attachment.review_status = "pending_review"

    db.commit()
    db.refresh(attachment)
    return attachment_dict(attachment)


@router.delete("/api/v1/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_WRITE_ROLES)),
) -> dict[str, str]:
    attachment = db.get(TransferAttachmentModel, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="attachment_not_found")
    if attachment.file_path:
        Path(attachment.file_path).unlink(missing_ok=True)
    db.delete(attachment)
    db.commit()
    return {"status": "deleted", "id": attachment_id}


@router.get("/api/v1/integrations", response_model=list[IntegrationResponse])
async def list_integrations(
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*CONFIG_ROLES)),
) -> list[IntegrationResponse]:
    rows = db.scalars(select(IntegrationConfigModel).order_by(IntegrationConfigModel.key)).all()
    enriched = [await enrich_integration_status(row) for row in rows]
    return [IntegrationResponse(**item) for item in enriched]


@router.patch("/api/v1/integrations/{key}", response_model=IntegrationResponse)
async def update_integration(
    key: str,
    payload: IntegrationUpdateRequest,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*CONFIG_ROLES)),
) -> IntegrationResponse:
    row = db.get(IntegrationConfigModel, key)
    if not row:
        raise HTTPException(status_code=404, detail="integration_not_found")
    if payload.enabled is not None:
        row.enabled = payload.enabled
    if payload.status is not None:
        row.status = payload.status
    if payload.config:
        current = json.loads(row.config_json or "{}")
        current.update(payload.config)
        row.config_json = json.dumps(current)
    db.commit()
    db.refresh(row)
    return IntegrationResponse(
        key=row.key,
        provider=row.provider,
        display_name=row.display_name,
        enabled=row.enabled,
        status=row.status,
        config=json.loads(row.config_json or "{}"),
    )


XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _export_file_name(prefix: str, period: str, start_date: str | None, end_date: str | None, ext: str) -> str:
    if period == "custom":
        return f"{prefix}-{start_date}-to-{end_date}.{ext}"
    return f"{prefix}-{period}.{ext}"


@router.get("/api/v1/reports/export")
async def export_report(
    period: str = Query(default="month", pattern="^(day|week|month|year|custom)$"),
    start_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    project_id: str | None = None,
    fmt: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_READ_ROLES)),
) -> StreamingResponse:
    try:
        start, end = resolve_report_range(period, start_date, end_date)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    rows = project_report_rows(db, "month", project_id, start=start, end=end)

    if fmt == "xlsx":
        content = build_project_report_xlsx(rows, period_display_label(period, start, end))
        file_name = _export_file_name("invmmc-bao-cao-du-an", period, start_date, end_date, "xlsx")
        return StreamingResponse(
            iter([content]),
            media_type=XLSX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "code",
            "name",
            "owner",
            "department",
            "budget",
            "actual",
            "telegram_thu",
            "telegram_chi",
            "available",
            "usage_percent",
            "status",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    file_name = _export_file_name("invmmc-report", period, start_date, end_date, "csv")
    return StreamingResponse(
        iter(["﻿" + output.getvalue()]),  # BOM de Excel doc UTF-8 tieng Viet
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/api/v1/transfers/export")
async def export_transfers(
    period: str = Query(default="month", pattern="^(day|week|month|year|custom)$"),
    start_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    project_id: str | None = None,
    fmt: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
    user: AuthUser = Depends(require_roles(*FINANCE_READ_ROLES)),
) -> StreamingResponse:
    try:
        start, end = resolve_report_range(period, start_date, end_date)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    rows = transfer_report_rows(db, start, end, project_id)

    if fmt == "xlsx":
        content = build_transfer_report_xlsx(rows, period_display_label(period, start, end))
        file_name = _export_file_name("invmmc-giao-dich", period, start_date, end_date, "xlsx")
        return StreamingResponse(
            iter([content]),
            media_type=XLSX_MEDIA_TYPE,
            headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "received_at",
            "transacted_at",
            "project_code",
            "project_name",
            "source",
            "transaction_type",
            "amount",
            "counterparty",
            "bank_name",
            "reference",
            "status",
            "review_status",
            "caption",
            "note",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    file_name = _export_file_name("invmmc-transfers", period, start_date, end_date, "csv")
    return StreamingResponse(
        iter(["﻿" + output.getvalue()]),  # BOM de Excel doc UTF-8 tieng Viet
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_shared_secret(
        x_telegram_bot_api_secret_token,
        settings.telegram_webhook_secret,
    ):
        raise HTTPException(status_code=401, detail="invalid telegram webhook secret")

    update = await request.json()
    bot = TelegramBotClient()
    intake_service = TelegramAttachmentService()

    if "callback_query" in update:
        result = TelegramCommandService(db).handle_callback(update)
        await bot.answer_callback_query(str(update["callback_query"].get("id", "")), result.ack)
        if result.run_ai_for:
            background_tasks.add_task(intake_service.analyze_and_notify, result.run_ai_for)
        if result.reply:
            await bot.send_message(
                result.reply.chat_id,
                result.reply.text,
                result.reply.reply_markup,
            )
        return {"status": "ok", "attachment": "callback"}

    attachment = await intake_service.store_from_update(db, update)

    if attachment:
        if attachment.review_status == "duplicate":
            original = intake_service.find_duplicate_original(db, attachment)
            reply_text = build_duplicate_warning(attachment, original)
            keyboard = duplicate_keyboard(attachment.id)
        else:
            reply_text = build_intake_reply(attachment)
            keyboard = attachment_keyboard(attachment.id)
            if attachment.review_status == "pending_ai":
                background_tasks.add_task(intake_service.analyze_and_notify, attachment.id)
        if attachment.telegram_chat_id:
            await bot.send_message(int(attachment.telegram_chat_id), reply_text, keyboard)
        return {"status": "ok", "attachment": "stored"}

    reply = TelegramCommandService(db).handle(update) or TelegramUpdateHandler().handle(update)
    if reply:
        await bot.send_message(reply.chat_id, reply.text, reply.reply_markup)
    return {"status": "ok", "attachment": "none"}


@router.post("/webhooks/momo")
async def momo_webhook(request: Request, x_momo_signature: str | None = Header(default=None)) -> dict:
    raw_body = await request.body()
    adapter = MomoAdapter()
    if not adapter.verify_signature(raw_body, x_momo_signature):
        raise HTTPException(status_code=401, detail="invalid momo signature")
    payload = await request.json()
    normalized = adapter.normalize_webhook(payload)
    return {"status": "accepted", "transaction": normalized}


@router.post("/webhooks/bank")
async def bank_webhook(request: Request) -> dict:
    raw_body = await request.body()
    adapter = GenericBankAdapter()
    headers = {key: value for key, value in request.headers.items()}
    if not adapter.verify_webhook(headers, raw_body):
        raise HTTPException(status_code=401, detail="invalid bank webhook")
    payload = await request.json()
    transaction = adapter.parse_transaction(payload)
    return {"status": "accepted", "external_id": transaction.external_id}


@router.get("/uploads/{path:path}", include_in_schema=False)
async def protected_upload(
    path: str,
    user: AuthUser = Depends(require_roles(Role.SYSTEM_ADMIN, Role.CFO, Role.FINANCE_MANAGER, Role.AUDITOR)),
) -> FileResponse:
    upload_root = Path(settings.upload_dir).resolve()
    target = (upload_root / path).resolve()
    if not target.is_file() or not target.is_relative_to(upload_root):
        raise HTTPException(status_code=404, detail="file_not_found")
    return FileResponse(target)
