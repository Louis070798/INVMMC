from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from invmmc.persistence.models import ExpenseRequestModel, ProjectModel, TransferAttachmentModel

Period = Literal["day", "week", "month", "year"]


def period_start(period: Period, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    if period == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        start = now - timedelta(days=now.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if period == "year":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValueError(f"Unsupported period: {period}")


def resolve_report_range(
    period: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[datetime, datetime]:
    """Tra ve (start, end) cho bao cao. period=custom dung start_date/end_date (YYYY-MM-DD)."""
    now = datetime.now(UTC)
    if period == "custom":
        if not start_date or not end_date:
            raise ValueError("custom period requires start_date and end_date")
        start = datetime.fromisoformat(start_date).replace(tzinfo=UTC)
        end = datetime.fromisoformat(end_date).replace(tzinfo=UTC) + timedelta(days=1)
        if end <= start:
            raise ValueError("end_date must be on or after start_date")
        return start, end
    return period_start(period, now), now + timedelta(days=1)


def dashboard_summary(
    db: Session,
    period: Period = "month",
    project_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    if start is None:
        start = period_start(period)
    projects = db.scalars(select(ProjectModel).order_by(ProjectModel.code)).all()
    expenses_query = select(ExpenseRequestModel).where(ExpenseRequestModel.created_at >= start)
    if end is not None:
        expenses_query = expenses_query.where(ExpenseRequestModel.created_at < end)
    if project_id:
        expenses_query = expenses_query.where(ExpenseRequestModel.project_id == project_id)
    expenses = db.scalars(expenses_query).all()

    attachment_query = select(TransferAttachmentModel).where(TransferAttachmentModel.received_at >= start)
    if end is not None:
        attachment_query = attachment_query.where(TransferAttachmentModel.received_at < end)
    if project_id:
        attachment_query = attachment_query.where(TransferAttachmentModel.project_id == project_id)
    attachments = db.scalars(attachment_query).all()

    actual_by_project: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    pending_count = 0
    for expense in expenses:
        if expense.status in {"paid", "reconciled", "closed"}:
            actual_by_project[expense.project_id] += expense.amount
        if expense.status in {"submitted", "finance_checked", "approved"}:
            pending_count += 1

    # Thu/chi tu chung tu Telegram da duoc xac nhan (/confirm), gom theo du an.
    thu_by_project: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    chi_by_project: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for attachment in attachments:
        if attachment.review_status != "confirmed" or attachment.amount_hint is None:
            continue
        bucket = attachment.project_id or "__unassigned__"
        if attachment.transaction_type == "thu":
            thu_by_project[bucket] += attachment.amount_hint
        elif attachment.transaction_type == "chi":
            chi_by_project[bucket] += attachment.amount_hint

    project_rows = []
    for project in projects:
        actual = actual_by_project[project.id]
        budget = Decimal(project.budget_amount)
        project_rows.append(
            {
                "id": project.id,
                "code": project.code,
                "name": project.name,
                "owner": project.owner,
                "department": project.department,
                "budget": float(budget),
                "actual": float(actual),
                "available": float(budget - actual),
                "usage_percent": float((actual / budget * 100) if budget else Decimal("0")),
                "status": project.status,
                "telegram_thu": float(thu_by_project[project.id]),
                "telegram_chi": float(chi_by_project[project.id]),
            }
        )

    total_budget = sum(Decimal(project.budget_amount) for project in projects)
    total_actual = sum(actual_by_project.values(), Decimal("0"))
    unmatched_count = sum(1 for attachment in attachments if attachment.status == "unmatched")
    pending_review_count = sum(
        1 for attachment in attachments if attachment.review_status != "confirmed"
    )
    total_thu = sum(thu_by_project.values(), Decimal("0"))
    total_chi = sum(chi_by_project.values(), Decimal("0"))

    return {
        "period": period,
        "period_start": start.isoformat(),
        "kpis": {
            "total_budget": float(total_budget),
            "total_actual": float(total_actual),
            "available": float(total_budget - total_actual),
            "pending_approvals": pending_count,
            "unmatched_transfers": unmatched_count,
            "pending_review_attachments": pending_review_count,
            "telegram_thu": float(total_thu),
            "telegram_chi": float(total_chi),
        },
        "projects": project_rows,
        "approval_queue": [
            {
                "id": expense.id,
                "project_id": expense.project_id,
                "amount": float(expense.amount),
                "status": expense.status,
                "description": expense.description,
                "created_at": expense.created_at.isoformat(),
            }
            for expense in expenses
            if expense.status in {"submitted", "finance_checked", "approved"}
        ],
        "attachments": [attachment_dict(item) for item in attachments],
    }


def attachment_dict(item: TransferAttachmentModel) -> dict:
    return {
        "id": item.id,
        "project_id": item.project_id,
        "source": item.source,
        "file_name": item.file_name,
        "file_path": item.file_path,
        "file_url": upload_url(item.file_path),
        "caption": item.caption,
        "amount_hint": float(item.amount_hint) if item.amount_hint is not None else None,
        "status": item.status,
        "transaction_type": item.transaction_type,
        "review_status": item.review_status,
        "counterparty": item.counterparty,
        "bank_name": item.bank_name,
        "reference": item.reference,
        "transacted_at": item.transacted_at,
        "note": item.note,
        "ai_summary": item.ai_summary,
        "ai_confidence": float(item.ai_confidence) if item.ai_confidence is not None else None,
        "received_at": item.received_at.isoformat(),
    }


def project_report_rows(
    db: Session,
    period: Period = "month",
    project_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    summary = dashboard_summary(db, period, project_id, start=start, end=end)
    return summary["projects"]


def transfer_report_rows(
    db: Session,
    start: datetime,
    end: datetime,
    project_id: str | None = None,
) -> list[dict]:
    query = (
        select(TransferAttachmentModel)
        .where(TransferAttachmentModel.received_at >= start)
        .where(TransferAttachmentModel.received_at < end)
        .order_by(TransferAttachmentModel.received_at)
    )
    if project_id:
        query = query.where(TransferAttachmentModel.project_id == project_id)
    attachments = db.scalars(query).all()

    projects = {project.id: project for project in db.scalars(select(ProjectModel)).all()}
    rows = []
    for item in attachments:
        project = projects.get(item.project_id) if item.project_id else None
        rows.append(
            {
                "received_at": item.received_at.isoformat(),
                "transacted_at": item.transacted_at or "",
                "project_code": project.code if project else "",
                "project_name": project.name if project else "",
                "source": item.source,
                "transaction_type": item.transaction_type or "",
                "amount": float(item.amount_hint) if item.amount_hint is not None else "",
                "counterparty": item.counterparty or "",
                "bank_name": item.bank_name or "",
                "reference": item.reference or "",
                "status": item.status,
                "review_status": item.review_status,
                "caption": item.caption or "",
                "note": item.note or "",
                "file_path": item.file_path or "",
            }
        )
    return rows


def upload_url(file_path: str | None) -> str | None:
    if not file_path:
        return None
    normalized = file_path.replace("\\", "/")
    marker = "/uploads/"
    if marker in normalized:
        return "/uploads/" + normalized.split(marker, 1)[1]
    if normalized.startswith("data/uploads/"):
        return "/uploads/" + normalized.removeprefix("data/uploads/")
    return None
