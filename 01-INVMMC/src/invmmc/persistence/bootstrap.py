import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from invmmc.core.config import settings
from invmmc.core.database import Base, engine
from invmmc.domain.enums import Role
from invmmc.persistence.models import (
    ExpenseRequestModel,
    IntegrationConfigModel,
    ProjectModel,
    TransferAttachmentModel,
    UserModel,
)
from invmmc.services.auth import hash_password, roles_to_json


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_migrations()
    backfill_attachment_hashes()


def migrate_env_bot_to_admin(db: Session) -> None:
    """Chuyen TELEGRAM_BOT_TOKEN trong .env thanh bot ca nhan cua admin (chay 1 lan).

    He thong da bot: moi user so huu 1 bot, luu trong bang telegram_bots.
    Token cu trong .env duoc gan cho tai khoan admin de khong mat du lieu flow cu.
    """
    from uuid import uuid4

    from invmmc.persistence.models import TelegramBotModel

    token = settings.telegram_bot_token.strip()
    if not token:
        return
    if db.scalar(select(TelegramBotModel).where(TelegramBotModel.token == token)):
        return
    admin = db.scalar(
        select(UserModel).where(UserModel.email == settings.admin_email.lower().strip())
    )
    if not admin or db.scalar(
        select(TelegramBotModel).where(TelegramBotModel.user_id == admin.id)
    ):
        return
    db.add(
        TelegramBotModel(
            id=f"bot-{uuid4().hex[:10]}",
            user_id=admin.id,
            token=token,
            status="active",
        )
    )
    db.commit()


# Cot bo sung sau khi bang da ton tai; create_all khong tu them cot moi.
# Ap dung cho SQLite local; production PostgreSQL nen dung cong cu migration rieng.
EXTRA_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "transfer_attachments": [
        ("owner_user_id", "VARCHAR(40)"),
        ("transaction_type", "VARCHAR(10) DEFAULT 'unknown'"),
        ("review_status", "VARCHAR(30) DEFAULT 'pending_review'"),
        ("file_sha256", "VARCHAR(64)"),
        ("file_dhash", "VARCHAR(16)"),
        ("counterparty", "VARCHAR(240) DEFAULT ''"),
        ("transacted_at", "VARCHAR(60) DEFAULT ''"),
        ("bank_name", "VARCHAR(120) DEFAULT ''"),
        ("reference", "VARCHAR(240) DEFAULT ''"),
        ("note", "TEXT DEFAULT ''"),
        ("ai_summary", "TEXT DEFAULT ''"),
        ("ai_payload_json", "TEXT DEFAULT '{}'"),
        ("ai_confidence", "NUMERIC(5,4)"),
    ],
}


def ensure_schema_migrations() -> None:
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as conn:
        for table, columns in EXTRA_COLUMNS.items():
            existing = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
            if not existing:
                continue
            for name, ddl in columns:
                if name not in existing:
                    conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def backfill_attachment_hashes() -> None:
    """Bo sung du lieu cho chung tu cu (truoc khi co tinh nang chong trung):

    - sha256/dhash tu file anh: khong co hash thi khong so trung duoc.
    - reference/transacted_at/counterparty/bank tu ai_payload_json:
      cot moi ra doi sau nen ban ghi cu bi rong du AI da doc duoc.
    """
    import hashlib
    import json
    from pathlib import Path

    from invmmc.core.database import SessionLocal
    from invmmc.core.imaging import dhash_hex

    with SessionLocal() as db:
        rows = db.scalars(select(TransferAttachmentModel)).all()
        changed = False
        for row in rows:
            if row.file_path:
                path = Path(row.file_path)
                if path.exists():
                    if row.file_sha256 is None:
                        row.file_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
                        changed = True
                    if row.file_dhash is None:
                        row.file_dhash = dhash_hex(path)
                        changed = row.file_dhash is not None or changed

            payload_raw = row.ai_payload_json or "{}"
            if payload_raw not in {"", "{}"}:
                try:
                    payload = json.loads(payload_raw)
                except json.JSONDecodeError:
                    payload = {}
                updates = {
                    "reference": str(payload.get("reference", "") or "")[:240],
                    "transacted_at": str(payload.get("transacted_at", "") or "")[:60],
                    "counterparty": str(payload.get("counterparty", "") or "")[:240],
                    "bank_name": str(payload.get("bank", "") or "")[:120],
                }
                for field, value in updates.items():
                    if value and not getattr(row, field):
                        setattr(row, field, value)
                        changed = True
        if changed:
            db.commit()


def seed_demo_data(db: Session) -> None:
    ensure_default_integrations(db)
    ensure_default_admin(db)
    migrate_env_bot_to_admin(db)

    if not settings.demo_seed_data:
        return

    has_project = db.scalar(select(ProjectModel.id).limit(1))
    if has_project:
        return

    projects = [
        ProjectModel(
            id="prj-001",
            code="PRJ001",
            name="ERP Rollout",
            owner="Nguyen Minh",
            department="Operations",
            budget_amount=Decimal("850000000"),
        ),
        ProjectModel(
            id="prj-002",
            code="PRJ002",
            name="Marketing Growth Q3",
            owner="Tran Linh",
            department="Marketing",
            budget_amount=Decimal("420000000"),
        ),
        ProjectModel(
            id="prj-003",
            code="PRJ003",
            name="Warehouse Automation",
            owner="Le Quang",
            department="Supply Chain",
            budget_amount=Decimal("1200000000"),
        ),
    ]
    db.add_all(projects)

    db.add_all(
        [
            ExpenseRequestModel(
                id="REQ-2026-0001",
                project_id="prj-001",
                requester_id="u-ops-01",
                amount=Decimal("24000000"),
                budget_line_code="SOFTWARE",
                vendor_id="vendor-erp",
                description="ERP implementation milestone",
                status="approved",
            ),
            ExpenseRequestModel(
                id="REQ-2026-0002",
                project_id="prj-002",
                requester_id="u-mkt-01",
                amount=Decimal("12500000"),
                budget_line_code="ADS",
                vendor_id="vendor-meta",
                description="Meta ads weekly top-up",
                status="submitted",
            ),
            ExpenseRequestModel(
                id="REQ-2026-0003",
                project_id="prj-003",
                requester_id="u-sc-01",
                amount=Decimal("93000000"),
                budget_line_code="EQUIPMENT",
                vendor_id="vendor-robotics",
                description="Deposit for scanner equipment",
                status="paid",
            ),
        ]
    )

    db.add(
        TransferAttachmentModel(
            id="att-demo-001",
            project_id="prj-002",
            source="telegram",
            telegram_file_id="demo-file",
            telegram_chat_id="demo-chat",
            telegram_message_id="demo-message",
            file_name="telegram-transfer-demo.txt",
            file_path=None,
            caption="PRJ002 chuyen khoan ads 12500000",
            amount_hint=Decimal("12500000"),
            status="unmatched",
        )
    )
    db.commit()


def ensure_default_integrations(db: Session) -> None:
    defaults = [
        IntegrationConfigModel(
            key="telegram",
            provider="telegram",
            display_name="Telegram Bot",
            enabled=False,
            status="needs_token",
            config_json='{"webhook": "/telegram/webhook", "stores_transfer_images": true}',
        ),
        IntegrationConfigModel(
            key="bank",
            provider="bank",
            display_name="Bank API / VietQR",
            enabled=False,
            status="sandbox_ready",
            config_json='{"provider": "vietqr", "mode": "adapter"}',
        ),
        IntegrationConfigModel(
            key="momo",
            provider="momo",
            display_name="MoMo Business",
            enabled=False,
            status="needs_contract",
            config_json='{"mode": "sandbox"}',
        ),
        IntegrationConfigModel(
            key="email",
            provider="smtp",
            display_name="Email (SMTP - Quen mat khau)",
            enabled=False,
            status="needs_smtp_config",
            config_json=json.dumps(
                {
                    "smtp_host": "",
                    "smtp_port": 587,
                    "smtp_username": "",
                    "smtp_password": "",
                    "smtp_from_email": "",
                    "smtp_from_name": "INVMMC Finance",
                    "smtp_use_tls": True,
                }
            ),
        ),
    ]

    changed = False
    for item in defaults:
        if db.get(IntegrationConfigModel, item.key) is None:
            db.add(item)
            changed = True
    if changed:
        db.commit()


def ensure_default_admin(db: Session) -> None:
    email = settings.admin_email.lower().strip()
    roles: set[Role] = set()
    for raw_role in settings.admin_roles.split(","):
        raw_role = raw_role.strip()
        if not raw_role:
            continue
        try:
            roles.add(Role(raw_role))
        except ValueError:
            continue
    if not roles:
        roles = {Role.SYSTEM_ADMIN}

    existing_admin = db.get(UserModel, "user-admin")
    existing_email_owner = db.scalar(select(UserModel).where(UserModel.email == email))
    if existing_admin:
        if existing_admin.email != email and existing_email_owner is None:
            existing_admin.email = email
            db.commit()
        return
    if existing_email_owner:
        return

    db.add(
        UserModel(
            id="user-admin",
            email=email,
            full_name=settings.admin_full_name,
            password_hash=hash_password(settings.admin_password),
            roles_json=roles_to_json(roles),
        )
    )
    db.commit()
