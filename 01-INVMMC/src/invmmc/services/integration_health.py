import json
from typing import Any

import httpx

from invmmc.core.config import settings
from invmmc.persistence.models import IntegrationConfigModel


async def enrich_integration_status(row: IntegrationConfigModel) -> dict[str, Any]:
    config = json.loads(row.config_json or "{}")
    status = row.status
    enabled = row.enabled

    if row.key == "telegram":
        telegram_status = await check_telegram_status(config)
        config.update(telegram_status["config"])
        status = telegram_status["status"]
        enabled = telegram_status["enabled"]
    elif row.key == "bank":
        status = check_bank_status()
        enabled = status == "configured"
    elif row.key == "momo":
        status = check_momo_status()
        enabled = status == "configured"
    elif row.key == "email":
        status = check_email_status(config)
        enabled = status == "configured"

    return {
        "key": row.key,
        "provider": row.provider,
        "display_name": row.display_name,
        "enabled": enabled,
        "status": status,
        "config": config,
    }


async def check_telegram_status(config: dict[str, Any]) -> dict[str, Any]:
    if not settings.telegram_bot_token:
        return {
            "enabled": False,
            "status": "missing_bot_token",
            "config": {
                "token_configured": False,
                "webhook_url": config.get("webhook_url") or f"{settings.app_base_url}/telegram/webhook",
            },
        }

    result_config: dict[str, Any] = {
        "token_configured": True,
        "token_status": "env",
        "webhook_url": config.get("webhook_url") or f"{settings.app_base_url}/telegram/webhook",
    }

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            me_response = await client.get(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe"
            )
            me_data = me_response.json()
            if not me_response.is_success or not me_data.get("ok"):
                return {
                    "enabled": False,
                    "status": "invalid_bot_token",
                    "config": result_config,
                }

            bot_info = me_data.get("result", {})
            result_config.update(
                {
                    "bot_id": bot_info.get("id"),
                    "bot_username": bot_info.get("username"),
                    "bot_first_name": bot_info.get("first_name"),
                }
            )

            webhook_response = await client.get(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/getWebhookInfo"
            )
            webhook_data = webhook_response.json()
            webhook_info = webhook_data.get("result", {}) if webhook_data.get("ok") else {}
            active_webhook_url = webhook_info.get("url") or ""
            result_config.update(
                {
                    "telegram_webhook_url": active_webhook_url,
                    "pending_update_count": webhook_info.get("pending_update_count", 0),
                    "last_error_message": webhook_info.get("last_error_message"),
                }
            )

            if active_webhook_url:
                return {
                    "enabled": True,
                    "status": "connected_webhook_active",
                    "config": result_config,
                }
            return {
                "enabled": True,
                "status": "token_valid_webhook_not_set",
                "config": result_config,
            }
    except httpx.HTTPError as exc:
        result_config["last_error_message"] = str(exc)
        return {
            "enabled": False,
            "status": "telegram_api_unreachable",
            "config": result_config,
        }


def check_bank_status() -> str:
    required = [settings.bank_api_base_url, settings.bank_client_id, settings.bank_client_secret]
    if all(required):
        return "configured"
    if settings.bank_provider:
        return "adapter_ready_missing_credentials"
    return "not_configured"


def check_momo_status() -> str:
    required = [settings.momo_partner_code, settings.momo_access_key, settings.momo_secret_key]
    if all(required):
        return "configured"
    return "missing_business_credentials"


def check_email_status(config: dict[str, Any]) -> str:
    if config.get("smtp_host") and config.get("smtp_username"):
        return "configured"
    return "needs_smtp_config"
