import hashlib
from datetime import UTC
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from invmmc.core.config import settings
from invmmc.core.database import SessionLocal
from invmmc.core.imaging import DHASH_DUPLICATE_THRESHOLD, dhash_hex, hamming_hex
from invmmc.integrations.local_ai import LocalAiClient, owner_rule_transaction_type
from invmmc.integrations.telegram import (
    TelegramAttachmentCandidate,
    TelegramBotClient,
    attachment_keyboard,
    extract_attachment_candidate,
)
from invmmc.persistence.models import (
    ChatStateModel,
    ProjectModel,
    TransferAttachmentModel,
    utc_now,
)
from invmmc.services.expense_intake import ExpenseIntakeService

# Trang thai "cho nhap noi dung" het han sau 6 gio; tin nhan sau do
# khong bi hieu nham la noi dung chung tu cu.
NOTE_STATE_TTL_SECONDS = 6 * 3600


class TelegramAttachmentService:
    def __init__(
        self,
        bot_client: TelegramBotClient | None = None,
        intake: ExpenseIntakeService | None = None,
    ) -> None:
        self.bot_client = bot_client or TelegramBotClient()
        self.intake = intake or ExpenseIntakeService()

    async def store_from_update(
        self,
        db: Session,
        update: dict,
        owner_user_id: str | None = None,
    ) -> TransferAttachmentModel | None:
        candidate = extract_attachment_candidate(update)
        if not candidate:
            return None
        return await self.store_candidate(db, candidate, owner_user_id=owner_user_id)

    async def store_candidate(
        self,
        db: Session,
        candidate: TelegramAttachmentCandidate,
        owner_user_id: str | None = None,
    ) -> TransferAttachmentModel:
        parsed = self.intake.parse_text(candidate.caption)
        # So qua nho trong caption (vd "lan 1", "so 5") khong phai so tien VND;
        # bo qua de AI doc so tien that tu anh.
        caption_amount = parsed.amount if parsed.amount and parsed.amount >= 1000 else None
        project = None
        if parsed.project_code:
            project = db.scalar(select(ProjectModel).where(ProjectModel.code == parsed.project_code))

        local_path = await self.bot_client.download_file(
            candidate.file_id,
            Path(settings.upload_dir) / "telegram",
            candidate.file_name,
        )

        file_sha256: str | None = None
        file_dhash: str | None = None
        duplicate = False
        if local_path:
            file_sha256 = hashlib.sha256(Path(local_path).read_bytes()).hexdigest()
            file_dhash = dhash_hex(local_path)
            duplicate = self._is_visual_duplicate(db, file_sha256, file_dhash)

        if duplicate:
            review_status = "duplicate"
        elif self._can_analyze(local_path):
            review_status = "pending_ai"
        else:
            review_status = "pending_review"

        attachment = TransferAttachmentModel(
            id=f"att-{uuid4().hex[:12]}",
            project_id=project.id if project else None,
            owner_user_id=owner_user_id,
            source="telegram",
            telegram_file_id=candidate.file_id,
            telegram_chat_id=candidate.chat_id,
            telegram_message_id=candidate.message_id,
            file_name=candidate.file_name,
            file_path=local_path,
            file_sha256=file_sha256,
            file_dhash=file_dhash,
            caption=candidate.caption,
            amount_hint=caption_amount,
            status="unmatched",
            transaction_type="unknown",
            review_status=review_status,
        )
        db.add(attachment)
        if not duplicate:
            set_awaiting_note(db, candidate.chat_id, attachment.id)
        db.commit()
        db.refresh(attachment)
        return attachment

    @staticmethod
    def _can_analyze(local_path: str | None) -> bool:
        return bool(settings.ai_enabled and local_path)

    def capture_pending_note(self, db: Session, update: dict):
        """Tin nhan text thuong (khong phai lenh) sau khi gui anh = noi dung chung tu.

        Tra ve TelegramReply neu da tieu thu tin nhan, nguoc lai None de
        cac handler khac xu ly.
        """
        from invmmc.integrations.telegram import TelegramReply, attachment_keyboard

        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        text = str(message.get("text") or "").strip()
        if not chat_id or not text or text.startswith("/"):
            return None

        state = db.get(ChatStateModel, str(chat_id))
        if not state or state.awaiting != "note" or not state.attachment_id:
            return None

        # SQLite tra ve datetime khong co timezone; coi nhu UTC de so sanh.
        updated_at = state.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        expired = (utc_now() - updated_at).total_seconds() > NOTE_STATE_TTL_SECONDS
        attachment = db.get(TransferAttachmentModel, state.attachment_id)
        state.awaiting = ""
        state.attachment_id = None
        if expired or not attachment:
            db.commit()
            return None

        attachment.note = text[:1000]
        # Noi dung nguoi dung go co the chua ma du an va so tien -> tan dung.
        parsed = self.intake.parse_text(text)
        if attachment.project_id is None and parsed.project_code:
            project = db.scalar(
                select(ProjectModel).where(ProjectModel.code == parsed.project_code)
            )
            if project:
                attachment.project_id = project.id
        if attachment.amount_hint is None and parsed.amount and parsed.amount >= 1000:
            attachment.amount_hint = parsed.amount
        if attachment.review_status == "confirmed":
            attachment.review_status = "pending_review"
        db.commit()
        db.refresh(attachment)

        return TelegramReply(
            chat_id=int(chat_id),
            text="Da luu noi dung cho chung tu.\n" + build_analysis_message(attachment),
            reply_markup=attachment_keyboard(attachment.id),
        )

    @staticmethod
    def _is_visual_duplicate(db: Session, file_sha256: str, file_dhash: str | None) -> bool:
        """Trung tuyet doi (sha256) hoac trung thi giac (dhash gan nhau)."""
        exact = db.scalar(
            select(TransferAttachmentModel.id)
            .where(TransferAttachmentModel.file_sha256 == file_sha256)
            .limit(1)
        )
        if exact:
            return True
        if not file_dhash:
            return False
        existing_hashes = db.scalars(
            select(TransferAttachmentModel.file_dhash).where(
                TransferAttachmentModel.file_dhash.is_not(None)
            )
        ).all()
        return any(
            (distance := hamming_hex(file_dhash, other)) is not None
            and distance <= DHASH_DUPLICATE_THRESHOLD
            for other in existing_hashes
        )

    @staticmethod
    def find_duplicate_original(
        db: Session,
        attachment: TransferAttachmentModel,
    ) -> TransferAttachmentModel | None:
        """Tim ban goc theo thu tu tin cay: sha256 -> dhash -> ma GD/so tien+thoi gian."""
        others = db.scalars(
            select(TransferAttachmentModel)
            .where(TransferAttachmentModel.id != attachment.id)
            .order_by(TransferAttachmentModel.received_at.asc())
        ).all()

        if attachment.file_sha256:
            for other in others:
                if other.file_sha256 == attachment.file_sha256:
                    return other
        if attachment.file_dhash:
            for other in others:
                distance = hamming_hex(attachment.file_dhash, other.file_dhash)
                if distance is not None and distance <= DHASH_DUPLICATE_THRESHOLD:
                    return other
        return find_business_duplicate(db, attachment)

    async def analyze_and_notify(self, attachment_id: str) -> None:
        """Chay AI vision tren anh da tai ve, luu ket qua va bao lai qua Telegram.

        Duoc goi tu BackgroundTasks nen tu mo session rieng, khong dung session request.
        """
        with SessionLocal() as db:
            attachment = db.get(TransferAttachmentModel, attachment_id)
            if not attachment or not attachment.file_path:
                return

            code_to_id = {
                code: project_id
                for project_id, code in db.execute(select(ProjectModel.id, ProjectModel.code))
            }

            analysis = await LocalAiClient().analyze_transfer_image(
                attachment.file_path,
                attachment.caption,
                project_codes=sorted(code_to_id),
            )

            attachment.transaction_type = analysis.transaction_type
            attachment.counterparty = analysis.counterparty[:240]
            attachment.bank_name = analysis.bank[:120]
            attachment.reference = analysis.reference[:240]
            attachment.transacted_at = analysis.transacted_at[:60]
            attachment.ai_summary = analysis.summary
            attachment.ai_payload_json = analysis.raw_json
            attachment.ai_confidence = Decimal(str(round(analysis.confidence, 4)))
            if analysis.amount is not None and attachment.amount_hint is None:
                attachment.amount_hint = analysis.amount

            # Rule chu tai khoan ghi de ket qua AI: nguoi NHAN la chu -> thu,
            # nguoi CHUYEN la chu -> chi. Doi tac la phia ben kia.
            ruled_type = owner_rule_transaction_type(analysis.sender_name, analysis.receiver_name)
            if ruled_type:
                attachment.transaction_type = ruled_type
                other_side = analysis.sender_name if ruled_type == "thu" else analysis.receiver_name
                if other_side:
                    attachment.counterparty = other_side[:240]
                attachment.ai_summary = (
                    f"{analysis.summary} (rule: "
                    f"{'nguoi nhan' if ruled_type == 'thu' else 'nguoi chuyen'} la chu tai khoan)"
                ).strip()

            if attachment.project_id is None:
                matched_code = self._match_project_code(analysis, code_to_id)
                if matched_code:
                    attachment.project_id = code_to_id[matched_code]

            # Sau khi AI doc duoc ma GD/so tien/thoi gian: kiem tra trung nghiep vu
            # (cung giao dich nhung anh chup khac nhau, hash khong bat duoc).
            notify_client = client_for_owner(db, attachment.owner_user_id)

            business_original = find_business_duplicate(db, attachment)
            if business_original:
                attachment.review_status = "duplicate"
                db.commit()
                db.refresh(attachment)
                if attachment.telegram_chat_id:
                    from invmmc.integrations.telegram import duplicate_keyboard

                    await notify_client.send_message(
                        int(attachment.telegram_chat_id),
                        build_duplicate_warning(
                            attachment,
                            business_original,
                            reason="Cung giao dich (ma GD hoac so tien + thoi gian trung khop).",
                        ),
                        duplicate_keyboard(attachment.id),
                    )
                return

            attachment.review_status = "pending_review"
            db.commit()
            db.refresh(attachment)

            if attachment.telegram_chat_id:
                await notify_client.send_message(
                    int(attachment.telegram_chat_id),
                    build_analysis_message(attachment),
                    attachment_keyboard(attachment.id),
                )

    def _match_project_code(self, analysis, code_to_id: dict[str, str]) -> str | None:
        """Tim ma du an tu ket qua AI: uu tien project_code AI tra ve,
        sau do quet ma PRJ trong noi dung CK va tom tat."""
        if analysis.project_code in code_to_id:
            return analysis.project_code
        for text in (analysis.reference, analysis.summary):
            parsed = self.intake.parse_text(text)
            if parsed.project_code and parsed.project_code in code_to_id:
                return parsed.project_code
        return None


def client_for_owner(db: Session, owner_user_id: str | None) -> TelegramBotClient:
    """Tra ve bot client cua chu so huu chung tu; khong co thi dung token .env."""
    if owner_user_id:
        from invmmc.services.telegram_bots import get_user_bot

        bot = get_user_bot(db, owner_user_id)
        if bot and bot.token:
            return TelegramBotClient(bot.token)
    return TelegramBotClient()


def set_awaiting_note(db: Session, chat_id: str, attachment_id: str) -> None:
    """Danh dau chat dang cho nhap noi dung cho chung tu vua tao (upsert)."""
    state = db.get(ChatStateModel, str(chat_id))
    if state is None:
        state = ChatStateModel(chat_id=str(chat_id))
        db.add(state)
    state.awaiting = "note"
    state.attachment_id = attachment_id
    state.updated_at = utc_now()


def clear_awaiting_note(db: Session, chat_id: str) -> None:
    state = db.get(ChatStateModel, str(chat_id))
    if state:
        state.awaiting = ""
        state.attachment_id = None
        db.commit()


def build_intake_reply(attachment: TransferAttachmentModel) -> str:
    project_code = attachment.project.code if attachment.project else None
    lines = [f"Da nhan anh chuyen khoan. Ma: {attachment.id}"]

    caption_code = ExpenseIntakeService().parse_text(attachment.caption).project_code
    if project_code:
        lines.append(f"Du an: {project_code}")
    elif caption_code:
        lines.append(
            f"CANH BAO: ma du an {caption_code} trong caption KHONG ton tai. "
            "Xem danh sach: /projects | Tao moi: /project new <MA> <ngan sach> <ten> "
            "| Gan lai: /edit last project <ma>"
        )
    else:
        lines.append("Du an: chua gan. Xem ma: /projects | Gan: /edit last project <ma>")

    if attachment.amount_hint is not None:
        lines.append(f"So tien (tu caption): {_format_amount(attachment.amount_hint)} VND")
    if attachment.review_status == "pending_ai":
        lines.append("AI dang phan tich thu/chi va tu do ma du an, se bao ket qua sau.")
    else:
        lines.append("AI chua bat. Dung nut ben duoi hoac /edit de nhap tay.")
    lines.append(
        ">>> NHAP NOI DUNG: go tin nhan tiep theo de luu dien giai cho chung tu "
        "(vi du: thanh toan hoa don ABC PRJ001). Khong can thi bam nut Bo qua."
    )
    lines.append(f"Sua so tien/doi tac: /edit {attachment.id} amount|doitac|bank|ref|note <gia tri>")
    return "\n".join(lines)


def find_business_duplicate(
    db: Session,
    attachment: TransferAttachmentModel,
) -> TransferAttachmentModel | None:
    """Trung nghiep vu: cung ma giao dich, hoac cung so tien + thoi gian giao dich.

    Bat truong hop cung mot hoa don nhung anh chup man hinh khac nhau
    (crop khac, app khac) ma sha256/dhash khong phat hien duoc.
    """
    candidates = db.scalars(
        select(TransferAttachmentModel)
        .where(
            TransferAttachmentModel.id != attachment.id,
            TransferAttachmentModel.review_status != "duplicate",
        )
        .order_by(TransferAttachmentModel.received_at.asc())
    ).all()

    ref = _normalize_key(attachment.reference)
    when = _normalize_key(attachment.transacted_at)
    for other in candidates:
        if ref and len(ref) >= 6 and _normalize_key(other.reference) == ref:
            return other
        if (
            when
            and attachment.amount_hint is not None
            and other.amount_hint == attachment.amount_hint
            and _normalize_key(other.transacted_at) == when
        ):
            return other
    return None


def _normalize_key(value: str | None) -> str:
    return "".join((value or "").upper().split())


def build_duplicate_warning(
    attachment: TransferAttachmentModel,
    original: TransferAttachmentModel | None,
    reason: str = "",
) -> str:
    lines = [f"CANH BAO: anh nay TRUNG voi chung tu da gui truoc do. Ma moi: {attachment.id}"]
    if reason:
        lines.append(f"Ly do: {reason}")
    if original:
        original_project = original.project.code if original.project else "chua gan"
        amount = (
            f"{_format_amount(original.amount_hint)} VND"
            if original.amount_hint is not None
            else "chua co so tien"
        )
        lines.append(
            f"Ban goc: {original.id} | {original.transaction_type} | {amount} "
            f"| du an {original_project} | trang thai {original.review_status} "
            f"| nhan luc {original.received_at:%d/%m/%Y %H:%M}"
        )
    lines.append("Co luu ban moi nay khong? Chon nut ben duoi.")
    return "\n".join(lines)


def build_analysis_message(attachment: TransferAttachmentModel) -> str:
    type_label = {"thu": "THU (tien vao)", "chi": "CHI (tien ra)"}.get(
        attachment.transaction_type,
        "CHUA RO (can chinh tay)",
    )
    confidence = float(attachment.ai_confidence or 0)
    lines = [
        f"Ket qua AI cho {attachment.id}:",
        f"Loai: {type_label} (do tin cay {confidence:.0%})",
    ]
    if attachment.amount_hint is not None:
        lines.append(f"So tien: {_format_amount(attachment.amount_hint)} VND")
    if attachment.counterparty:
        lines.append(f"Doi tac: {attachment.counterparty}")
    if attachment.bank_name:
        lines.append(f"Ngan hang: {attachment.bank_name}")
    if attachment.reference:
        lines.append(f"Noi dung CK: {attachment.reference}")
    if attachment.ai_summary:
        lines.append(f"Tom tat: {attachment.ai_summary}")

    project_code = attachment.project.code if attachment.project else None
    if project_code:
        lines.append(f"Du an: {project_code}")
    else:
        lines.append("Du an: CHUA GAN. Bam nut 'Chon du an' ben duoi.")

    lines.append(
        "Dung nut ben duoi de sua loai/du an va xac nhan. "
        f"Sua chi tiet khac: /edit {attachment.id} amount|doitac|bank|ref|note <gia tri>"
    )
    return "\n".join(lines)


def _format_amount(amount: Decimal) -> str:
    return f"{amount:,.0f}".replace(",", ".")
