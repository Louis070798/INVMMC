from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from invmmc.core.database import Base
from invmmc.integrations.telegram import TelegramAttachmentCandidate
from invmmc.persistence.models import ProjectModel
from invmmc.services.telegram_intake import TelegramAttachmentService


class FakeTelegramBotClient:
    async def download_file(self, file_id: str, target_dir: Path, file_name: str) -> str:
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / file_name
        path.write_bytes(b"fake-image")
        return str(path)


@pytest.mark.anyio
async def test_store_telegram_transfer_attachment_links_project_and_file(tmp_path: Path) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        db.add(
            ProjectModel(
                id="prj-001",
                code="PRJ001",
                name="ERP Rollout",
                owner="Owner",
                department="Ops",
                budget_amount=Decimal("100000000"),
            )
        )
        db.commit()

        service = TelegramAttachmentService(bot_client=FakeTelegramBotClient())
        attachment = await service.store_candidate(
            db,
            TelegramAttachmentCandidate(
                chat_id="100",
                message_id="200",
                file_id="file-1",
                file_name="transfer.jpg",
                caption="PRJ001 chuyen khoan 1200000",
            ),
        )

    assert attachment.project_id == "prj-001"
    assert attachment.amount_hint == Decimal("1200000.00")
    assert attachment.file_path is not None
    assert Path(attachment.file_path).exists()
