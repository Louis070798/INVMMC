from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any

from invmmc.domain.entities import ExternalTransaction
from invmmc.domain.enums import TransactionDirection


class BankAdapter(ABC):
    @abstractmethod
    async def fetch_transactions(self, since: datetime) -> list[ExternalTransaction]:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, headers: dict[str, str], payload: bytes) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse_transaction(self, payload: dict[str, Any]) -> ExternalTransaction:
        raise NotImplementedError


class GenericBankAdapter(BankAdapter):
    async def fetch_transactions(self, since: datetime) -> list[ExternalTransaction]:
        return []

    def verify_webhook(self, headers: dict[str, str], payload: bytes) -> bool:
        return bool(headers or payload)

    def parse_transaction(self, payload: dict[str, Any]) -> ExternalTransaction:
        return ExternalTransaction(
            provider=str(payload.get("provider", "bank")),
            external_id=str(payload["external_id"]),
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            amount=Decimal(str(payload["amount"])),
            currency=str(payload.get("currency", "VND")),
            direction=TransactionDirection(payload.get("direction", "out")),
            counterparty_name=payload.get("counterparty_name"),
            counterparty_account=payload.get("counterparty_account"),
            description=str(payload.get("description", "")),
            raw=payload,
        )
