"""Quan ly bot Telegram ca nhan: moi user nhap token bot rieng o trang Settings.

He thong CHI dung long polling (getUpdates) - khong dang ky webhook voi Telegram.
Token duoc verify qua getMe truoc khi luu.
"""

from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from invmmc.persistence.models import TelegramBotModel


class BotTokenError(ValueError):
    """Token khong hop le hoac Telegram tu choi."""


async def verify_bot_token(token: str) -> tuple[str, str]:
    """Goi getMe de xac thuc token; tra ve (bot_id, bot_username)."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
        except httpx.HTTPError as error:
            raise BotTokenError("telegram_unreachable") from error
    payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code != 200 or not payload.get("ok"):
        raise BotTokenError("invalid_token")
    result = payload.get("result") or {}
    return str(result.get("id", "")), str(result.get("username", ""))


def get_user_bot(db: Session, user_id: str) -> TelegramBotModel | None:
    return db.scalar(select(TelegramBotModel).where(TelegramBotModel.user_id == user_id))


def get_bot_by_row_id(db: Session, bot_row_id: str) -> TelegramBotModel | None:
    return db.get(TelegramBotModel, bot_row_id)


def set_user_bot(db: Session, user_id: str, token: str, bot_id: str, bot_username: str) -> TelegramBotModel:
    """Gan/cap nhat bot cho user. Token da duoc verify truoc khi goi ham nay."""
    taken = db.scalar(
        select(TelegramBotModel).where(
            TelegramBotModel.token == token,
            TelegramBotModel.user_id != user_id,
        )
    )
    if taken:
        raise BotTokenError("token_in_use")

    bot = get_user_bot(db, user_id)
    if bot is None:
        bot = TelegramBotModel(id=f"bot-{uuid4().hex[:10]}", user_id=user_id)
        db.add(bot)
    bot.token = token
    bot.bot_id = bot_id
    bot.bot_username = bot_username
    bot.status = "active"
    db.commit()
    db.refresh(bot)
    return bot


def delete_user_bot(db: Session, user_id: str) -> bool:
    bot = get_user_bot(db, user_id)
    if not bot:
        return False
    db.delete(bot)
    db.commit()
    return True


def mask_token(token: str) -> str:
    if len(token) <= 10:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


def bot_summary(bot: TelegramBotModel | None) -> dict:
    if not bot:
        return {"configured": False}
    return {
        "configured": True,
        "bot_id": bot.bot_id,
        "bot_username": bot.bot_username,
        "status": bot.status,
        "token_masked": mask_token(bot.token),
        "updated_at": bot.updated_at.isoformat() if bot.updated_at else None,
    }
