import base64
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from invmmc.core.config import settings


@dataclass(frozen=True)
class AiSuggestion:
    budget_line_code: str | None
    risk_flags: set[str]
    summary: str


@dataclass(frozen=True)
class TransferImageAnalysis:
    transaction_type: str  # thu | chi | unknown
    amount: Decimal | None
    currency: str
    counterparty: str
    sender_name: str
    receiver_name: str
    bank: str
    transacted_at: str
    reference: str
    project_code: str
    confidence: float
    summary: str
    raw_json: str


TRANSFER_IMAGE_PROMPT = """Ban la tro ly tai chinh. Anh dinh kem la man hinh giao dich chuyen khoan \
ngan hang hoac vi dien tu cua Viet Nam.
Xac dinh giao dich la "thu" (tien VAO tai khoan: dau +, chu "nhan tien", "bao co") \
hay "chi" (tien RA khoi tai khoan: dau -, "chuyen tien thanh cong", "bao no").
Goi y them tu nguoi gui: "{caption}"
{project_hint}
{owner_hint}
Tra ve DUY NHAT mot JSON hop le, khong them van ban khac:
{{"transaction_type": "thu|chi|unknown", "amount": <so tien dang number, khong dau phan cach>, \
"currency": "VND", "sender_name": "<ten nguoi/don vi CHUYEN tien>", \
"receiver_name": "<ten nguoi/don vi NHAN tien>", \
"counterparty": "<ten doi tac phia ben kia>", "bank": "<ngan hang>", \
"transacted_at": "<thoi gian giao dich neu doc duoc>", "reference": "<ma giao dich hoac noi dung CK>", \
"project_code": "<ma du an khop danh sach, khong chac thi de rong>", \
"confidence": <0..1>, "summary": "<mo ta ngan gon giao dich>"}}"""

PROJECT_HINT_TEMPLATE = (
    "Cac ma du an hop le cua cong ty: {codes}. "
    "Neu noi dung chuyen khoan hoac caption nhac den mot ma nay thi dien vao project_code."
)

OWNER_HINT_TEMPLATE = (
    "Chu tai khoan he thong: {names}. "
    "Neu nguoi NHAN tien la chu tai khoan thi transaction_type la 'thu'; "
    "neu nguoi CHUYEN tien la chu tai khoan thi la 'chi'."
)


class LocalAiClient:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        self.vision_model = settings.ollama_vision_model

    async def suggest_expense_metadata(self, text: str) -> AiSuggestion:
        if not settings.ai_enabled:
            return AiSuggestion(None, set(), "AI disabled; using rule-based intake only.")

        prompt = (
            "You are a finance controller. Summarize this expense request, "
            "suggest a budget line code if obvious, and list risk flags. "
            f"Expense text: {text}"
        )
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data = response.json()

        summary = str(data.get("response", "")).strip()
        return AiSuggestion(None, set(), summary)

    async def analyze_transfer_image(
        self,
        image_path: str,
        caption: str = "",
        project_codes: list[str] | None = None,
    ) -> TransferImageAnalysis:
        if not settings.ai_enabled:
            return _unknown_analysis("AI disabled; cho nhap tay hoac bat AI_ENABLED.")

        project_hint = ""
        if project_codes:
            project_hint = PROJECT_HINT_TEMPLATE.format(codes=", ".join(project_codes[:30]))

        owner_hint = ""
        owner_names = [name.strip() for name in settings.owner_account_names.split(",") if name.strip()]
        if owner_names:
            owner_hint = OWNER_HINT_TEMPLATE.format(names=", ".join(owner_names))

        image_bytes = Path(image_path).read_bytes()
        prompt = TRANSFER_IMAGE_PROMPT.format(
            caption=caption.replace('"', "'"),
            project_hint=project_hint,
            owner_hint=owner_hint,
        )
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [base64.b64encode(image_bytes).decode("ascii")],
                    "stream": False,
                    "format": "json",
                },
            )
            response.raise_for_status()
            raw_text = str(response.json().get("response", "")).strip()

        return parse_transfer_analysis(raw_text)


def parse_transfer_analysis(raw_text: str) -> TransferImageAnalysis:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start < 0 or end <= start:
        return _unknown_analysis(f"AI khong tra ve JSON: {raw_text[:200]}")

    try:
        payload = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError:
        return _unknown_analysis(f"JSON khong hop le: {raw_text[:200]}")

    transaction_type = str(payload.get("transaction_type", "unknown")).strip().lower()
    if transaction_type not in {"thu", "chi"}:
        transaction_type = "unknown"

    # Dau +/- tren bien lai the hien huong tien, da co transaction_type; luu so duong.
    amount: Decimal | None = None
    raw_amount = payload.get("amount")
    if raw_amount is not None:
        try:
            amount = abs(Decimal(str(raw_amount).replace(",", "").replace(" ", "")))
        except InvalidOperation:
            amount = None

    try:
        confidence = min(max(float(payload.get("confidence", 0.0)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.0

    return TransferImageAnalysis(
        transaction_type=transaction_type,
        amount=amount,
        currency=str(payload.get("currency", "VND") or "VND"),
        counterparty=str(payload.get("counterparty", "") or ""),
        sender_name=str(payload.get("sender_name", "") or ""),
        receiver_name=str(payload.get("receiver_name", "") or ""),
        bank=str(payload.get("bank", "") or ""),
        transacted_at=str(payload.get("transacted_at", "") or ""),
        reference=str(payload.get("reference", "") or ""),
        project_code=str(payload.get("project_code", "") or "").strip().upper(),
        confidence=confidence,
        summary=str(payload.get("summary", "") or ""),
        raw_json=raw_text[start : end + 1],
    )


def _unknown_analysis(summary: str) -> TransferImageAnalysis:
    return TransferImageAnalysis(
        transaction_type="unknown",
        amount=None,
        currency="VND",
        counterparty="",
        sender_name="",
        receiver_name="",
        bank="",
        transacted_at="",
        reference="",
        project_code="",
        confidence=0.0,
        summary=summary,
        raw_json="{}",
    )


def normalize_person_name(name: str) -> str:
    """Chuan hoa ten de so khop: bo dau tieng Viet, viet hoa, gop khoang trang."""
    import unicodedata

    decomposed = unicodedata.normalize("NFD", name)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(stripped.upper().replace("Đ", "D").split())


def owner_rule_transaction_type(sender_name: str, receiver_name: str) -> str | None:
    """Ap dung rule chu tai khoan: nguoi NHAN la chu -> thu, nguoi CHUYEN la chu -> chi."""
    owners = {
        normalize_person_name(name)
        for name in settings.owner_account_names.split(",")
        if name.strip()
    }
    if not owners:
        return None
    if normalize_person_name(receiver_name) in owners:
        return "thu"
    if normalize_person_name(sender_name) in owners:
        return "chi"
    return None
