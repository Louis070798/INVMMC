import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from invmmc.core.database import get_db
from invmmc.domain.enums import Role
from invmmc.persistence.models import UserModel, UserSessionModel

SESSION_COOKIE_NAME = "invmmc_session"
SESSION_DAYS = 7

FINANCE_READ_ROLES = {
    Role.SYSTEM_ADMIN,
    Role.CFO,
    Role.CEO,
    Role.FINANCE_MANAGER,
    Role.FINANCE_CONTROLLER,
    Role.ACCOUNTANT,
    Role.TREASURY,
    Role.AUDITOR,
    Role.PROJECT_MANAGER,
}

FINANCE_WRITE_ROLES = {
    Role.SYSTEM_ADMIN,
    Role.CFO,
    Role.CEO,
    Role.FINANCE_MANAGER,
    Role.FINANCE_CONTROLLER,
    Role.ACCOUNTANT,
    Role.PROJECT_MANAGER,
}

CONFIG_ROLES = {
    Role.SYSTEM_ADMIN,
    Role.CFO,
    Role.FINANCE_MANAGER,
}

PAYMENT_WEBHOOK_ROLES = {
    Role.SYSTEM_ADMIN,
}


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    full_name: str
    roles: set[Role]

    def has_any_role(self, allowed: set[Role]) -> bool:
        return bool(self.roles & allowed)


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, salt, expected = stored_hash.split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    candidate = hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_expired(expires_at: datetime) -> bool:
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


def roles_to_json(roles: set[Role]) -> str:
    return json.dumps(sorted(role.value for role in roles))


def roles_from_json(value: str) -> set[Role]:
    try:
        raw_roles = json.loads(value or "[]")
    except json.JSONDecodeError:
        raw_roles = []
    roles: set[Role] = set()
    for raw in raw_roles:
        try:
            roles.add(Role(raw))
        except ValueError:
            continue
    return roles


def create_session(db: Session, user: UserModel) -> str:
    token = secrets.token_urlsafe(48)
    session = UserSessionModel(
        id=f"sess-{uuid4().hex[:12]}",
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=SESSION_DAYS),
    )
    db.add(session)
    db.commit()
    return token


def authenticate_user(db: Session, email: str, password: str) -> UserModel | None:
    user = db.scalar(select(UserModel).where(UserModel.email == email.lower().strip()))
    if not user or user.status != "active":
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def revoke_session(db: Session, token: str | None) -> None:
    if not token:
        return
    session = db.scalar(select(UserSessionModel).where(UserSessionModel.token_hash == hash_token(token)))
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()


def user_to_auth_user(user: UserModel) -> AuthUser:
    return AuthUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=roles_from_json(user.roles_json),
    )


def get_current_user(
    request: Request,
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AuthUser:
    header_token = request.headers.get("x-invmmc-session")
    token = session_token or header_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    session = db.scalar(select(UserSessionModel).where(UserSessionModel.token_hash == hash_token(token)))
    if not session or session.revoked_at is not None or is_expired(session.expires_at):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session_expired")

    if session.user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive")
    return user_to_auth_user(session.user)


def optional_current_user(
    session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> AuthUser | None:
    if not session_token:
        return None
    session = db.scalar(select(UserSessionModel).where(UserSessionModel.token_hash == hash_token(session_token)))
    if not session or session.revoked_at is not None or is_expired(session.expires_at):
        return None
    if session.user.status != "active":
        return None
    return user_to_auth_user(session.user)


def require_roles(*allowed: Role):
    allowed_set = set(allowed)

    def dependency(user: AuthUser = Depends(get_current_user)) -> AuthUser:
        if not user.has_any_role(allowed_set):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission_denied")
        return user

    return dependency
