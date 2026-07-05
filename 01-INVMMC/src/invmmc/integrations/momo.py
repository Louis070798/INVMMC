import hashlib
import hmac
from typing import Any

from invmmc.core.config import settings


class MomoAdapter:
    def verify_signature(self, raw_body: bytes, received_signature: str | None) -> bool:
        if not settings.momo_secret_key:
            return True
        if not received_signature:
            return False
        digest = hmac.new(settings.momo_secret_key.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, received_signature)

    def normalize_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": "momo",
            "external_id": str(payload.get("transId") or payload.get("requestId")),
            "amount": payload.get("amount"),
            "currency": "VND",
            "description": payload.get("orderInfo") or payload.get("extraData") or "",
            "raw": payload,
        }
