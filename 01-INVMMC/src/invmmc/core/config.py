from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "INVMMC Project Finance Control"
    app_base_url: str = "http://localhost:8000"
    # Dung boi scripts/telegram_polling.py (doc .env truc tiep, khong qua Settings
    # nay) - khai bao o day de gia tri thua trong .env khong lam vo pydantic.
    internal_webhook_base_url: str = "http://127.0.0.1:8000"
    database_url: str = "sqlite:///./data/invmmc.db"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: str = "./data/uploads"
    demo_seed_data: bool = False

    telegram_bot_token: str = ""
    telegram_webhook_secret: str = ""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_vision_model: str = "qwen2.5vl:7b"
    ai_enabled: bool = False
    # Ten chu tai khoan cong ty/ca nhan, phan cach bang dau phay.
    # Nguoi NHAN khop ten nay -> thu; nguoi CHUYEN khop -> chi.
    owner_account_names: str = ""

    momo_partner_code: str = ""
    momo_access_key: str = ""
    momo_secret_key: str = ""
    momo_endpoint: str = "https://test-payment.momo.vn"
    momo_webhook_secret: str = ""

    bank_provider: str = "vietqr"
    bank_api_base_url: str = ""
    bank_client_id: str = ""
    bank_client_secret: str = ""
    bank_webhook_secret: str = ""

    jwt_secret: str = "change-me"

    # Email quen mat khau. Trong khi SMTP_HOST rong: khong gui that, chi log
    # link reset ra console (de dev/test khong can tai khoan SMTP that).
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "INVMMC Finance"
    smtp_use_tls: bool = True

    admin_email: str = "admin@invmmc.local"
    admin_password: str = "Admin@123456"
    admin_full_name: str = "System Admin"
    admin_roles: str = "system_admin,cfo,finance_manager,auditor"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
