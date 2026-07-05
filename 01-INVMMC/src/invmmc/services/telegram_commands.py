"""Lenh Telegram (text + nut callback) thao tac tren transfer_attachments va projects.

Cac lenh nay can DB session nen tach khoi TelegramUpdateHandler (stateless).
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from invmmc.core.config import settings
from invmmc.integrations.telegram import (
    TelegramReply,
    attachment_keyboard,
    pending_list_keyboard,
    project_picker_keyboard,
    projects_list_keyboard,
)
from invmmc.persistence.models import ExpenseRequestModel, ProjectModel, TransferAttachmentModel
from invmmc.services.telegram_intake import build_analysis_message

EDIT_COMMANDS = {"/edit", "/sua"}
CONFIRM_COMMANDS = {"/confirm", "/xacnhan"}
PENDING_COMMANDS = {"/pending", "/cho"}
PROJECTS_COMMANDS = {"/projects", "/duan"}
PROJECT_COMMANDS = {"/project"}
BUDGET_COMMANDS = {"/budget", "/ngansach"}

PROJECT_CODE_PATTERN = re.compile(r"^PRJ[A-Z0-9_-]{1,20}$")

EDIT_USAGE = (
    "Cu phap: /edit <ma|last> <truong> <gia tri>\n"
    "Truong: type thu|chi, amount <so>, project <ma du an>, "
    "doitac <ten>, bank <ngan hang>, ref <noi dung CK>, note <ghi chu>\n"
    "Meo: loai thu/chi, du an va xac nhan co the bam NUT duoi tin nhan chung tu."
)

PROJECT_NEW_USAGE = (
    "Cu phap: /project new <MA> <ngan sach> <ten du an>\n"
    "Vi du: /project new PRJ001 500000000 Marketing Q3\n"
    "Ma du an bat dau bang PRJ, ngan sach la so VND."
)


@dataclass(frozen=True)
class CallbackResult:
    ack: str | None = None
    reply: TelegramReply | None = None
    run_ai_for: str | None = None


class TelegramCommandService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------- text commands

    def handle(self, update: dict) -> TelegramReply | None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None
        chat_id = (message.get("chat") or {}).get("id")
        text = str(message.get("text") or "").strip()
        if not chat_id or not text.startswith("/"):
            return None

        parts = text.split()
        command = parts[0].lower().split("@")[0]
        sender = message.get("from") or {}
        sender_name = " ".join(
            part for part in [sender.get("first_name"), sender.get("last_name")] if part
        ) or str(sender.get("username") or "telegram-user")

        if command in EDIT_COMMANDS:
            return TelegramReply(chat_id=chat_id, text=self._edit(str(chat_id), parts[1:]))
        if command in CONFIRM_COMMANDS:
            ref = parts[1] if len(parts) > 1 else "last"
            attachment = self._resolve(str(chat_id), ref)
            if not attachment:
                return TelegramReply(
                    chat_id=chat_id,
                    text=f"Khong tim thay chung tu '{ref}'. Dung /pending de xem danh sach.",
                )
            return TelegramReply(chat_id=chat_id, text=self._confirm_attachment(attachment))
        if command in PENDING_COMMANDS:
            text_reply, keyboard = self._pending(str(chat_id))
            return TelegramReply(chat_id=chat_id, text=text_reply, reply_markup=keyboard)
        if command in PROJECTS_COMMANDS:
            text_reply, keyboard = self._projects()
            return TelegramReply(chat_id=chat_id, text=text_reply, reply_markup=keyboard)
        if command in PROJECT_COMMANDS:
            return TelegramReply(chat_id=chat_id, text=self._project(parts[1:], sender_name))
        if command in BUDGET_COMMANDS:
            return TelegramReply(chat_id=chat_id, text=self._budget(parts[1:]))
        return None

    # ------------------------------------------------------------- callbacks

    def handle_callback(self, update: dict) -> CallbackResult:
        callback = update.get("callback_query") or {}
        data = str(callback.get("data") or "")
        message = callback.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        if not chat_id or not data:
            return CallbackResult(ack="Khong doc duoc thao tac.")

        parts = data.split(":")
        action = parts[0]

        if action == "t" and len(parts) == 3:
            return self._cb_set_type(chat_id, parts[1], parts[2])
        if action == "c" and len(parts) == 2:
            return self._cb_confirm(chat_id, parts[1])
        if action == "p" and len(parts) == 2:
            return self._cb_project_picker(chat_id, parts[1])
        if action == "pa" and len(parts) == 3:
            return self._cb_assign_project(chat_id, parts[1], parts[2])
        if action == "b" and len(parts) == 2:
            project = self.db.get(ProjectModel, parts[1])
            if not project:
                return CallbackResult(ack="Du an khong con ton tai.")
            return CallbackResult(
                reply=TelegramReply(chat_id=chat_id, text=self._budget_text(project))
            )
        if action == "pl":
            text_reply, keyboard = self._projects()
            return CallbackResult(
                reply=TelegramReply(chat_id=chat_id, text=text_reply, reply_markup=keyboard)
            )
        if action == "pd":
            text_reply, keyboard = self._pending(str(chat_id))
            return CallbackResult(
                reply=TelegramReply(chat_id=chat_id, text=text_reply, reply_markup=keyboard)
            )
        if action == "dk" and len(parts) == 2:
            return self._cb_duplicate_keep(chat_id, parts[1])
        if action == "dx" and len(parts) == 2:
            return self._cb_duplicate_discard(chat_id, parts[1])
        return CallbackResult(ack="Thao tac khong hop le hoac da het han.")

    def _cb_set_type(self, chat_id: int, attachment_id: str, value: str) -> CallbackResult:
        if value not in {"thu", "chi"}:
            return CallbackResult(ack="Loai khong hop le.")
        attachment = self.db.get(TransferAttachmentModel, attachment_id)
        if not attachment:
            return CallbackResult(ack="Chung tu khong con ton tai.")
        attachment.transaction_type = value
        if attachment.review_status == "confirmed":
            attachment.review_status = "pending_review"
        self.db.commit()
        self.db.refresh(attachment)
        return CallbackResult(
            ack=f"Da chon {value.upper()}.",
            reply=TelegramReply(
                chat_id=chat_id,
                text="Da cap nhat.\n" + build_analysis_message(attachment),
                reply_markup=attachment_keyboard(attachment.id),
            ),
        )

    def _cb_confirm(self, chat_id: int, attachment_id: str) -> CallbackResult:
        attachment = self.db.get(TransferAttachmentModel, attachment_id)
        if not attachment:
            return CallbackResult(ack="Chung tu khong con ton tai.")
        text = self._confirm_attachment(attachment)
        return CallbackResult(reply=TelegramReply(chat_id=chat_id, text=text))

    def _cb_project_picker(self, chat_id: int, attachment_id: str) -> CallbackResult:
        attachment = self.db.get(TransferAttachmentModel, attachment_id)
        if not attachment:
            return CallbackResult(ack="Chung tu khong con ton tai.")
        projects = self.db.scalars(select(ProjectModel).order_by(ProjectModel.code)).all()
        if not projects:
            return CallbackResult(
                reply=TelegramReply(
                    chat_id=chat_id,
                    text=(
                        "Chua co du an nao. Tao moi: /project new <MA> <ngan sach> <ten>\n"
                        "Vi du: /project new PRJ001 500000000 Marketing Q3"
                    ),
                )
            )
        return CallbackResult(
            reply=TelegramReply(
                chat_id=chat_id,
                text=f"Chon du an cho {attachment.id}:",
                reply_markup=project_picker_keyboard(
                    attachment.id,
                    [(p.code, p.id) for p in projects],
                ),
            )
        )

    def _cb_assign_project(self, chat_id: int, attachment_id: str, project_id: str) -> CallbackResult:
        attachment = self.db.get(TransferAttachmentModel, attachment_id)
        if not attachment:
            return CallbackResult(ack="Chung tu khong con ton tai.")
        project = self.db.get(ProjectModel, project_id)
        if not project:
            return CallbackResult(ack="Du an khong con ton tai.")
        attachment.project_id = project.id
        if attachment.review_status == "confirmed":
            attachment.review_status = "pending_review"
        self.db.commit()
        self.db.refresh(attachment)
        return CallbackResult(
            ack=f"Da gan {project.code}.",
            reply=TelegramReply(
                chat_id=chat_id,
                text="Da cap nhat.\n" + build_analysis_message(attachment),
                reply_markup=attachment_keyboard(attachment.id),
            ),
        )

    def _cb_duplicate_keep(self, chat_id: int, attachment_id: str) -> CallbackResult:
        attachment = self.db.get(TransferAttachmentModel, attachment_id)
        if not attachment:
            return CallbackResult(ack="Chung tu khong con ton tai.")
        if attachment.review_status != "duplicate":
            return CallbackResult(ack="Chung tu nay da duoc xu ly roi.")

        # AI da phan tich roi (trung phat hien sau AI) thi khong chay lai.
        already_analyzed = bool((attachment.ai_payload_json or "{}") not in {"", "{}"})
        can_analyze = bool(settings.ai_enabled and attachment.file_path) and not already_analyzed
        attachment.review_status = "pending_ai" if can_analyze else "pending_review"
        self.db.commit()
        self.db.refresh(attachment)

        if already_analyzed:
            text = f"Da giu lai {attachment.id}.\n" + build_analysis_message(attachment)
        elif can_analyze:
            text = f"Da giu lai {attachment.id}. AI dang phan tich thu/chi..."
        else:
            text = f"Da giu lai {attachment.id}. Dung nut/lenh de nhap thu/chi."
        return CallbackResult(
            ack="Da giu lai.",
            reply=TelegramReply(
                chat_id=chat_id,
                text=text,
                reply_markup=attachment_keyboard(attachment.id),
            ),
            run_ai_for=attachment.id if can_analyze else None,
        )

    def _cb_duplicate_discard(self, chat_id: int, attachment_id: str) -> CallbackResult:
        attachment = self.db.get(TransferAttachmentModel, attachment_id)
        if not attachment:
            return CallbackResult(ack="Chung tu da duoc xoa truoc do.")
        if attachment.review_status != "duplicate":
            return CallbackResult(ack="Chung tu nay da duoc xu ly, khong xoa.")

        if attachment.file_path:
            Path(attachment.file_path).unlink(missing_ok=True)
        self.db.delete(attachment)
        self.db.commit()
        return CallbackResult(
            ack="Da bo qua.",
            reply=TelegramReply(
                chat_id=chat_id,
                text=f"Da bo qua va xoa anh trung ({attachment_id}).",
            ),
        )

    # ------------------------------------------------------------- helpers

    def _resolve(self, chat_id: str, ref: str) -> TransferAttachmentModel | None:
        if ref.lower() == "last":
            return self.db.scalar(
                select(TransferAttachmentModel)
                .where(TransferAttachmentModel.telegram_chat_id == chat_id)
                .order_by(TransferAttachmentModel.received_at.desc())
                .limit(1)
            )
        return self.db.get(TransferAttachmentModel, ref)

    def _find_project(self, code: str) -> ProjectModel | None:
        return self.db.scalar(select(ProjectModel).where(ProjectModel.code == code.upper()))

    # ------------------------------------------------------------- attachments

    def _edit(self, chat_id: str, args: list[str]) -> str:
        if len(args) < 3:
            return EDIT_USAGE

        attachment = self._resolve(chat_id, args[0])
        if not attachment:
            return f"Khong tim thay chung tu '{args[0]}'. Dung /pending de xem danh sach."

        field = args[1].lower()
        value = " ".join(args[2:]).strip()

        if field == "type":
            normalized = value.lower()
            if normalized not in {"thu", "chi"}:
                return "Gia tri type chi nhan 'thu' hoac 'chi'."
            attachment.transaction_type = normalized
        elif field == "amount":
            try:
                attachment.amount_hint = Decimal(value.replace(",", "").replace(".", ""))
            except InvalidOperation:
                return "So tien khong hop le. Vi du: /edit last amount 1200000"
        elif field == "project":
            project = self._find_project(value)
            if not project:
                return (
                    f"Khong tim thay du an voi ma '{value.upper()}'. "
                    "Xem danh sach: /projects | Tao moi: /project new <MA> <ngan sach> <ten>"
                )
            attachment.project_id = project.id
        elif field in {"doitac", "counterparty"}:
            attachment.counterparty = value[:240]
        elif field == "bank":
            attachment.bank_name = value[:120]
        elif field in {"ref", "reference"}:
            attachment.reference = value[:240]
        elif field == "note":
            attachment.note = value
        else:
            return EDIT_USAGE

        if attachment.review_status == "confirmed":
            attachment.review_status = "pending_review"
        self.db.commit()
        self.db.refresh(attachment)
        return "Da cap nhat.\n" + build_analysis_message(attachment)

    def _confirm_attachment(self, attachment: TransferAttachmentModel) -> str:
        if attachment.review_status == "duplicate":
            return (
                f"{attachment.id} dang cho quyet dinh anh trung. "
                "Bam 'Van luu' hoac 'Bo qua' trong tin canh bao truoc."
            )
        if attachment.transaction_type not in {"thu", "chi"}:
            return (
                f"{attachment.id} chua ro thu hay chi. "
                "Bam nut THU/CHI duoi tin nhan chung tu truoc."
            )
        if attachment.amount_hint is None:
            return f"{attachment.id} chua co so tien. Sua truoc: /edit {attachment.id} amount <so>"
        if attachment.project_id is None:
            return f"{attachment.id} chua gan du an. Bam nut 'Chon du an' truoc."

        attachment.review_status = "confirmed"
        self.db.commit()

        project_code = attachment.project.code if attachment.project else "?"
        type_label = "THU" if attachment.transaction_type == "thu" else "CHI"
        amount = _fmt(attachment.amount_hint)
        return (
            f"Da xac nhan {attachment.id}: {type_label} {amount} VND ({project_code}). "
            f"Xem tong hop du an: /budget {project_code}"
        )

    def _pending(self, chat_id: str) -> tuple[str, dict | None]:
        items = self.db.scalars(
            select(TransferAttachmentModel)
            .where(
                TransferAttachmentModel.telegram_chat_id == chat_id,
                TransferAttachmentModel.review_status != "confirmed",
            )
            .order_by(TransferAttachmentModel.received_at.desc())
            .limit(5)
        ).all()
        if not items:
            return "Khong co chung tu nao cho xu ly.", None

        lines = ["Chung tu cho xu ly (moi nhat truoc):"]
        keyboard_items: list[tuple[str, str]] = []
        for item in items:
            project_code = item.project.code if item.project else "?"
            amount = _fmt(item.amount_hint) if item.amount_hint is not None else "?"
            lines.append(
                f"- {item.id} | {item.transaction_type} | {amount} VND | {project_code} | {item.review_status}"
            )
            keyboard_items.append((item.id, item.id.removeprefix("att-")[:6]))
        lines.append("Bam nut de xac nhan/gan du an, hoac /edit <ma> ... de sua chi tiet.")
        return "\n".join(lines), pending_list_keyboard(keyboard_items)

    # ------------------------------------------------------------- projects

    def _projects(self) -> tuple[str, dict | None]:
        projects = self.db.scalars(select(ProjectModel).order_by(ProjectModel.code)).all()
        if not projects:
            return (
                "Chua co du an nao. Tao moi: /project new <MA> <ngan sach> <ten du an>\n"
                "Vi du: /project new PRJ001 500000000 Marketing Q3",
                None,
            )
        lines = ["Danh sach du an:"]
        for project in projects:
            lines.append(
                f"- {project.code} | {project.name} | ngan sach {_fmt(project.budget_amount)} VND"
            )
        lines.append("Bam nut de xem tong hop thu/chi tung du an.")
        return "\n".join(lines), projects_list_keyboard([(p.code, p.id) for p in projects])

    def _project(self, args: list[str], sender_name: str) -> str:
        if not args or args[0].lower() != "new":
            return PROJECT_NEW_USAGE
        if len(args) < 4:
            return PROJECT_NEW_USAGE

        code = args[1].upper()
        if not PROJECT_CODE_PATTERN.match(code):
            return f"Ma du an '{code}' khong hop le. Dung dang PRJ001, PRJ-MKT... (bat dau bang PRJ)."
        if self._find_project(code):
            return f"Du an {code} da ton tai. Xem: /budget {code}"

        try:
            budget = Decimal(args[2].replace(",", "").replace(".", ""))
        except InvalidOperation:
            return f"Ngan sach '{args[2]}' khong hop le. " + PROJECT_NEW_USAGE
        if budget < 0:
            return "Ngan sach phai >= 0."

        name = " ".join(args[3:]).strip()
        project = ProjectModel(
            id=f"prj-{uuid4().hex[:10]}",
            code=code,
            name=name[:200],
            owner=sender_name[:120],
            department="Telegram",
            budget_amount=budget,
        )
        self.db.add(project)
        self.db.commit()
        return (
            f"Da tao du an {code} - {name} | ngan sach {_fmt(budget)} VND.\n"
            f"Gan chung tu: bam nut 'Chon du an' duoi tin chung tu, "
            f"hoac gui anh kem caption chua {code}."
        )

    def _budget(self, args: list[str]) -> str:
        if not args:
            return "Cu phap: /budget <ma du an>. Xem danh sach: /projects"

        project = self._find_project(args[0])
        if not project:
            return f"Khong tim thay du an '{args[0].upper()}'. Xem danh sach: /projects"
        return self._budget_text(project)

    def _budget_text(self, project: ProjectModel) -> str:
        expenses = self.db.scalars(
            select(ExpenseRequestModel).where(ExpenseRequestModel.project_id == project.id)
        ).all()
        actual = sum(
            (e.amount for e in expenses if e.status in {"paid", "reconciled", "closed"}),
            Decimal("0"),
        )

        attachments = self.db.scalars(
            select(TransferAttachmentModel).where(TransferAttachmentModel.project_id == project.id)
        ).all()
        thu = sum(
            (a.amount_hint for a in attachments
             if a.review_status == "confirmed" and a.transaction_type == "thu" and a.amount_hint),
            Decimal("0"),
        )
        chi = sum(
            (a.amount_hint for a in attachments
             if a.review_status == "confirmed" and a.transaction_type == "chi" and a.amount_hint),
            Decimal("0"),
        )
        pending = sum(1 for a in attachments if a.review_status != "confirmed")

        budget = Decimal(project.budget_amount)
        return "\n".join(
            [
                f"Du an {project.code} - {project.name}",
                f"Ngan sach: {_fmt(budget)} VND",
                f"Chi thuc te (de nghi chi da thanh toan): {_fmt(actual)} VND",
                f"Telegram THU da xac nhan: {_fmt(thu)} VND",
                f"Telegram CHI da xac nhan: {_fmt(chi)} VND",
                f"Con lai theo ngan sach: {_fmt(budget - actual - chi)} VND",
                f"Chung tu cho xu ly: {pending}",
            ]
        )


def _fmt(amount: Decimal) -> str:
    return f"{amount:,.0f}".replace(",", ".")
