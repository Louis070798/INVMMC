"""Long-polling bridge DA BOT: poll getUpdates cua tat ca bot user va forward
vao endpoint noi bo /telegram/webhook (khong dang ky webhook voi Telegram).

- Danh sach bot doc truc tiep tu SQLite (bang telegram_bots, status=active),
  lam moi moi REFRESH_INTERVAL giay: user them/go bot khong can restart bridge.
- Moi bot mot task async rieng, offset luu o data/telegram_offsets/<bot_row_id>.txt.
- Forward kem header X-Invmmc-Bot-Id de backend biet update thuoc bot cua ai.
- Chi tao ket noi outbound (Telegram + localhost), khong mo cong nao ra ngoai.

Chay:
    python scripts/telegram_polling.py
"""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "invmmc.db"
OFFSET_DIR = PROJECT_ROOT / "data" / "telegram_offsets"
LEGACY_OFFSET_FILE = PROJECT_ROOT / "data" / "telegram_polling_offset.txt"
DEFAULT_INTERNAL_BASE_URL = "http://127.0.0.1:8000"
POLL_TIMEOUT_SECONDS = 50
REFRESH_INTERVAL_SECONDS = 60


@dataclass(frozen=True)
class BotRow:
    row_id: str
    token: str
    username: str


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_bots() -> list[BotRow]:
    """Doc bot active tu DB; loi DB (dang migrate...) thi tra ve danh sach rong."""
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        try:
            rows = conn.execute(
                "SELECT id, token, bot_username FROM telegram_bots WHERE status = 'active'"
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as error:
        print(f"load_bots error: {error}")
        return []
    return [BotRow(str(r[0]), str(r[1]), str(r[2] or "")) for r in rows if r[1]]


def offset_file(bot_row_id: str) -> Path:
    return OFFSET_DIR / f"{bot_row_id}.txt"


def load_offset(bot: BotRow, legacy_token: str) -> int:
    path = offset_file(bot.row_id)
    if path.exists():
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    # Bot dau tien ke thua offset tu file cu (thoi con 1 bot .env).
    if bot.token == legacy_token and LEGACY_OFFSET_FILE.exists():
        try:
            return int(LEGACY_OFFSET_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return 0


def save_offset(bot_row_id: str, offset: int) -> None:
    OFFSET_DIR.mkdir(parents=True, exist_ok=True)
    offset_file(bot_row_id).write_text(str(offset), encoding="utf-8")


async def forward_update(
    client: httpx.AsyncClient, bot: BotRow, update: dict, secret: str, webhook_url: str
) -> None:
    response = await client.post(
        webhook_url,
        json=update,
        headers={
            "X-Telegram-Bot-Api-Secret-Token": secret,
            "X-Invmmc-Bot-Id": bot.row_id,
        },
        timeout=60,
    )
    response.raise_for_status()
    print(f"[{bot.username or bot.row_id}] forwarded update_id={update.get('update_id')}")


async def poll_bot(bot: BotRow, secret: str, legacy_token: str, webhook_url: str) -> None:
    api_base = f"https://api.telegram.org/bot{bot.token}"
    offset = load_offset(bot, legacy_token)
    print(f"[{bot.username or bot.row_id}] polling started, offset={offset}")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                response = await client.get(
                    f"{api_base}/getUpdates",
                    params={"offset": offset, "timeout": POLL_TIMEOUT_SECONDS},
                    timeout=POLL_TIMEOUT_SECONDS + 10,
                )
                if response.status_code == 401:
                    print(f"[{bot.username or bot.row_id}] token bi thu hoi (401); doi 60s")
                    await asyncio.sleep(60)
                    continue
                if response.status_code == 409:
                    # Co tien trinh khac dang getUpdates cung token.
                    print(f"[{bot.username or bot.row_id}] getUpdates conflict (409); doi 30s")
                    await asyncio.sleep(30)
                    continue
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as error:
                print(f"[{bot.username or bot.row_id}] getUpdates error: {error}; retry in 5s")
                await asyncio.sleep(5)
                continue

            for update in payload.get("result", []):
                update_id = int(update.get("update_id", 0))
                try:
                    await forward_update(client, bot, update, secret, webhook_url)
                except httpx.ConnectError:
                    print(f"backend chua chay tai {webhook_url}; retry in 5s")
                    await asyncio.sleep(5)
                    break
                except httpx.HTTPError as error:
                    print(f"[{bot.username or bot.row_id}] forward error {update_id}: {error}; skip")
                offset = update_id + 1
                save_offset(bot.row_id, offset)


async def main() -> None:
    env = load_env(PROJECT_ROOT / ".env")
    secret = env.get("TELEGRAM_WEBHOOK_SECRET", "")
    legacy_token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not secret:
        raise SystemExit("TELEGRAM_WEBHOOK_SECRET chua co trong .env")

    # Bridge luon phai chay CUNG MAY voi backend (goi loopback, khong mo cong ra ngoai).
    # Doc tu .env de deploy sang server khac khong bi dinh cung "127.0.0.1" cua may cu.
    internal_base = (env.get("INTERNAL_WEBHOOK_BASE_URL") or DEFAULT_INTERNAL_BASE_URL).rstrip("/")
    webhook_url = f"{internal_base}/telegram/webhook"
    print(f"forward target: {webhook_url}")

    tasks: dict[str, asyncio.Task] = {}
    known_tokens: dict[str, str] = {}

    while True:
        bots = {bot.row_id: bot for bot in load_bots()}

        # Dung task cua bot da bi go / doi token / khoa.
        for row_id in list(tasks):
            bot = bots.get(row_id)
            if bot is None or known_tokens.get(row_id) != bot.token:
                tasks.pop(row_id).cancel()
                known_tokens.pop(row_id, None)
                print(f"[{row_id}] polling stopped (bot go bo hoac doi token)")

        # Mo task cho bot moi.
        for row_id, bot in bots.items():
            if row_id not in tasks:
                tasks[row_id] = asyncio.create_task(poll_bot(bot, secret, legacy_token, webhook_url))
                known_tokens[row_id] = bot.token

        if not tasks:
            print("chua co bot active nao trong telegram_bots; cho user nhap token o Settings...")

        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
