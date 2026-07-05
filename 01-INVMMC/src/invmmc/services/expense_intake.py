import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class ParsedExpenseText:
    amount: Decimal | None
    project_code: str | None
    description: str


class ExpenseIntakeService:
    amount_pattern = re.compile(r"(?<![A-Za-z0-9])(?P<amount>\d[\d,.]*)(?![A-Za-z0-9])")
    project_pattern = re.compile(r"\b(?P<project>PRJ[A-Z0-9_-]*)\b", re.IGNORECASE)

    def parse_text(self, text: str) -> ParsedExpenseText:
        amount = self._extract_amount(text)
        project = self._extract_project(text)
        return ParsedExpenseText(amount=amount, project_code=project, description=text.strip())

    def _extract_amount(self, text: str) -> Decimal | None:
        match = self.amount_pattern.search(text)
        if not match:
            return None
        raw_amount = match.group("amount").replace(",", "").replace(".", "")
        try:
            return Decimal(raw_amount)
        except InvalidOperation:
            return None

    def _extract_project(self, text: str) -> str | None:
        match = self.project_pattern.search(text)
        if not match:
            return None
        return match.group("project").upper()
