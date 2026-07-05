from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx

from invmmc.core.config import settings
from invmmc.services.expense_intake import ExpenseIntakeService


@dataclass(frozen=True)
class TelegramReply:
    chat_id: int
    text: str
    reply_markup: dict | None = None


@dataclass(frozen=True)
class TelegramAttachmentCandidate:
    chat_id: str
    message_id: str
    file_id: str
    file_name: str
    caption: str


class TelegramBotClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> None:
        if not self.token:
            return
        payload: dict = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json=payload,
            )

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> None:
        if not self.token:
            return
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{self.token}/answerCallbackQuery",
                json=payload,
            )

    async def download_file(self, file_id: str, target_dir: Path, file_name: str) -> str | None:
        if not self.token:
            return None

        target_dir.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=30) as client:
            file_response = await client.get(
                f"https://api.telegram.org/bot{self.token}/getFile",
                params={"file_id": file_id},
            )
            file_response.raise_for_status()
            file_path = file_response.json()["result"]["file_path"]

            extension = Path(file_path).suffix or Path(file_name).suffix or ".jpg"
            local_name = f"{uuid4().hex}{extension}"
            local_path = target_dir / local_name
            download_response = await client.get(
                f"https://api.telegram.org/file/bot{self.token}/{file_path}"
            )
            download_response.raise_for_status()
            local_path.write_bytes(download_response.content)
            return str(local_path)


class TelegramUpdateHandler:
    def __init__(self, intake: ExpenseIntakeService | None = None) -> None:
        self.intake = intake or ExpenseIntakeService()

    def handle(self, update: dict) -> TelegramReply | None:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = str(message.get("text") or "").strip()
        if not chat_id or not text:
            candidate = extract_attachment_candidate(update)
            if candidate:
                return TelegramReply(
                    chat_id=int(candidate.chat_id),
                    text="Da nhan anh/chung tu chuyen khoan. He thong se luu vao hang doi doi soat.",
                )
            return None

        if text.startswith("/start"):
            return TelegramReply(
                chat_id=chat_id,
                text=(
                    "INVMMC san sang.\n"
                    "Gui anh chuyen khoan (kem caption ma du an PRJxxx neu co) de AI phan tich thu/chi.\n"
                    "Sau do dung cac NUT duoi tin nhan de chon THU/CHI, gan du an, xac nhan.\n"
                    "Lenh go tay khi can: /edit <ma|last> amount|doitac|bank|ref|note <gia tri>, "
                    "/project new <MA> <ngan sach> <ten>."
                ),
                reply_markup=start_keyboard(),
            )

        if text.startswith("/new"):
            parsed = self.intake.parse_text(text.removeprefix("/new"))
            if not parsed.amount or not parsed.project_code:
                return TelegramReply(
                    chat_id=chat_id,
                    text="Thieu so tien hoac ma du an. Vi du: /new 1200000 PRJ001 marketing ads",
                )
            return TelegramReply(
                chat_id=chat_id,
                text=(
                    "Da nhan de nghi chi nhap. "
                    f"Du an: {parsed.project_code}, so tien: {parsed.amount} VND. "
                    "Finance se kiem tra ngan sach va chung tu."
                ),
            )

        if text.startswith("/status"):
            return TelegramReply(chat_id=chat_id, text="Tinh nang tra cuu trang thai se ket noi DB o phase MVP.")

        return TelegramReply(
            chat_id=chat_id,
            text=(
                "Lenh chua ho tro. Dung /projects, /project new, /budget, "
                "/pending, /edit, /confirm, /new hoac /status."
            ),
        )


# ---------------------------------------------------------------- keyboards
# Callback data (gioi han 64 byte): t=type, c=confirm, p=chon du an,
# pa=gan du an, b=ngan sach, pl=ds du an, pd=cho xu ly, dk=giu anh trung, dx=bo anh trung.


def attachment_keyboard(attachment_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "THU (tien vao)", "callback_data": f"t:{attachment_id}:thu"},
                {"text": "CHI (tien ra)", "callback_data": f"t:{attachment_id}:chi"},
            ],
            [
                {"text": "Chon du an", "callback_data": f"p:{attachment_id}"},
                {"text": "Xac nhan", "callback_data": f"c:{attachment_id}"},
            ],
        ]
    }


def intake_note_keyboard(attachment_id: str) -> dict:
    """Keyboard sau khi nhan anh: cac nut chuan + nut bo qua nhap noi dung."""
    keyboard = attachment_keyboard(attachment_id)
    keyboard["inline_keyboard"].append(
        [{"text": "Bo qua nhap noi dung", "callback_data": f"ns:{attachment_id}"}]
    )
    return keyboard


def duplicate_keyboard(attachment_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Van luu", "callback_data": f"dk:{attachment_id}"},
                {"text": "Bo qua (xoa)", "callback_data": f"dx:{attachment_id}"},
            ]
        ]
    }


def start_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Danh sach du an", "callback_data": "pl"},
                {"text": "Chung tu cho xu ly", "callback_data": "pd"},
            ]
        ]
    }


def project_picker_keyboard(attachment_id: str, projects: list[tuple[str, str]]) -> dict:
    """projects: list (code, project_id). Toi da 10 nut, 2 nut moi hang."""
    buttons = [
        {"text": code, "callback_data": f"pa:{attachment_id}:{project_id}"}
        for code, project_id in projects[:10]
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return {"inline_keyboard": rows}


def projects_list_keyboard(projects: list[tuple[str, str]]) -> dict:
    """Nut xem ngan sach tung du an. projects: list (code, project_id)."""
    buttons = [
        {"text": f"Ngan sach {code}", "callback_data": f"b:{project_id}"}
        for code, project_id in projects[:10]
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return {"inline_keyboard": rows}


def pending_list_keyboard(items: list[tuple[str, str]]) -> dict:
    """items: list (attachment_id, nhan hien thi ngan). Moi chung tu 1 hang nut."""
    rows = []
    for attachment_id, label in items[:5]:
        rows.append(
            [
                {"text": f"Xac nhan {label}", "callback_data": f"c:{attachment_id}"},
                {"text": "Du an", "callback_data": f"p:{attachment_id}"},
            ]
        )
    return {"inline_keyboard": rows}


def extract_attachment_candidate(update: dict) -> TelegramAttachmentCandidate | None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return None

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    caption = str(message.get("caption") or "")
    if not chat_id or not message_id:
        return None

    if message.get("photo"):
        largest_photo = sorted(message["photo"], key=lambda item: item.get("file_size", 0))[-1]
        return TelegramAttachmentCandidate(
            chat_id=str(chat_id),
            message_id=str(message_id),
            file_id=str(largest_photo["file_id"]),
            file_name=f"telegram-photo-{message_id}.jpg",
            caption=caption,
        )

    document = message.get("document")
    if document and str(document.get("mime_type", "")).startswith("image/"):
        return TelegramAttachmentCandidate(
            chat_id=str(chat_id),
            message_id=str(message_id),
            file_id=str(document["file_id"]),
            file_name=str(document.get("file_name") or f"telegram-document-{message_id}.jpg"),
            caption=caption,
        )

    return None
