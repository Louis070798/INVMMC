"""Long-polling bridge giua Telegram Bot API va webhook endpoint local.

Dung khi chua co HTTPS webhook cong khai: script goi getUpdates (outbound),
roi forward tung update vao POST /telegram/webhook cua backend local voi
header X-Telegram-Bot-Api-Secret-Token. Khong mo cong nao ra internet.

Chay:
    python scripts/telegram_polling.py
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFSET_FILE = PROJECT_ROOT / "data" / "telegram_polling_offset.txt"
LOCAL_WEBHOOK_URL = "http://127.0.0.1:8000/telegram/webhook"
POLL_TIMEOUT_SECONDS = 50


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    return 0


def save_offset(offset: int) -> None:
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(str(offset), encoding="utf-8")


def forward_update(client: httpx.Client, update: dict, secret: str) -> None:
    response = client.post(
        LOCAL_WEBHOOK_URL,
        json=update,
        headers={"X-Telegram-Bot-Api-Secret-Token": secret},
        timeout=60,
    )
    response.raise_for_status()
    print(f"forwarded update_id={update.get('update_id')} -> {response.json()}")


def main() -> None:
    env = load_env(PROJECT_ROOT / ".env")
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    secret = env.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not token or not secret:
        raise SystemExit("TELEGRAM_BOT_TOKEN hoac TELEGRAM_WEBHOOK_SECRET chua co trong .env")

    api_base = f"https://api.telegram.org/bot{token}"
    offset = load_offset()
    print(f"polling started, offset={offset}")

    with httpx.Client() as client:
        while True:
            try:
                response = client.get(
                    f"{api_base}/getUpdates",
                    params={"offset": offset, "timeout": POLL_TIMEOUT_SECONDS},
                    timeout=POLL_TIMEOUT_SECONDS + 10,
                )
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPError as error:
                print(f"getUpdates error: {error}; retry in 5s")
                time.sleep(5)
                continue

            for update in payload.get("result", []):
                update_id = int(update.get("update_id", 0))
                try:
                    forward_update(client, update, secret)
                except httpx.ConnectError:
                    print("backend local chua chay tai 127.0.0.1:8000; retry in 5s")
                    time.sleep(5)
                    break
                except httpx.HTTPError as error:
                    print(f"forward error update_id={update_id}: {error}; skip")
                offset = update_id + 1
                save_offset(offset)


if __name__ == "__main__":
    main()
