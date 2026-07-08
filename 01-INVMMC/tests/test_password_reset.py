from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from invmmc.core.config import settings
from invmmc.core.database import Base, SessionLocal
from invmmc.main import app
from invmmc.persistence.models import UserModel
from invmmc.services.auth import (
    consume_password_reset_token,
    create_password_reset_token,
    hash_password,
    verify_password,
)


def test_forgot_password_response_does_not_leak_account_existence() -> None:
    with TestClient(app) as client:
        known = client.post(
            "/api/v1/auth/forgot-password", json={"email": settings.admin_email}
        )
        unknown = client.post(
            "/api/v1/auth/forgot-password", json={"email": "khong-ton-tai@invmmc.local"}
        )

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json() == unknown.json()


def test_reset_password_with_invalid_token_returns_400() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "token-khong-ton-tai", "new_password": "MatKhauMoi123"},
        )
    assert response.status_code == 400
    assert "invalid_or_expired_token" in response.text


def test_create_and_consume_reset_token_single_use_and_expiry() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as db:
        user = UserModel(
            id="user-test-reset",
            email="reset-test@invmmc.local",
            full_name="Reset Test",
            password_hash=hash_password("MatKhauCu123"),
        )
        db.add(user)
        db.commit()

        token = create_password_reset_token(db, user)

        # Token sai thi khong tra ve user nao.
        assert consume_password_reset_token(db, "token-sai") is None

        # Token dung dung 1 lan.
        consumed_user = consume_password_reset_token(db, token)
        assert consumed_user is not None
        assert consumed_user.id == user.id

        # Dung lai token da dung -> tu choi.
        assert consume_password_reset_token(db, token) is None

        # Token da het han thi tu choi du chua dung.
        expired_token = create_password_reset_token(db, user)
        from invmmc.persistence.models import PasswordResetTokenModel
        from invmmc.services.auth import hash_token

        row = db.scalar(
            select(PasswordResetTokenModel).where(
                PasswordResetTokenModel.token_hash == hash_token(expired_token)
            )
        )
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
        assert consume_password_reset_token(db, expired_token) is None


def test_reset_password_end_to_end_updates_real_admin_and_restores_it() -> None:
    """Chay tren DB that (nhu test_dashboard_api.py) - PHAI khoi phuc mat khau
    admin trong finally du assert co fail giua chung, tranh khoa mat tai
    khoan that su dung hang ngay."""
    original_password = settings.admin_password
    with TestClient(app) as client:
        with SessionLocal() as db:
            admin = db.scalar(select(UserModel).where(UserModel.email == settings.admin_email.lower().strip()))
            assert admin is not None
            raw_token = create_password_reset_token(db, admin)

        try:
            new_password = "TamThoiChoTest#2026"
            reset_response = client.post(
                "/api/v1/auth/reset-password",
                json={"token": raw_token, "new_password": new_password},
            )
            assert reset_response.status_code == 200

            old_login = client.post(
                "/api/v1/auth/login",
                json={"email": settings.admin_email, "password": original_password},
            )
            assert old_login.status_code == 401

            new_login = client.post(
                "/api/v1/auth/login",
                json={"email": settings.admin_email, "password": new_password},
            )
            assert new_login.status_code == 200
        finally:
            with SessionLocal() as db:
                admin = db.scalar(
                    select(UserModel).where(UserModel.email == settings.admin_email.lower().strip())
                )
                admin.password_hash = hash_password(original_password)
                db.commit()

            with SessionLocal() as db:
                admin = db.scalar(
                    select(UserModel).where(UserModel.email == settings.admin_email.lower().strip())
                )
                assert verify_password(original_password, admin.password_hash)
