# INVMMC Project Finance Control

He thong quan ly va kiem soat chi tieu tai chinh theo du an cho cong ty khoang 100 nguoi.

Muc tieu cua du an:

- Kiem soat ngan sach theo du an, hang muc, phong ban va nha cung cap.
- Tao luong de nghi chi, tam ung, thanh toan, doi soat va hau kiem.
- Phan quyen ro rang theo vai tro tai chinh, quan ly du an, nguoi de nghi va ban dieu hanh.
- Tich hop Telegram de nhap lieu, phe duyet, nhan canh bao.
- Tich hop MoMo, ngan hang hoac trung gian VietQR/Casso qua adapter.
- Dung AI local, uu tien Ollama, de doc noi dung giao dich va goi y phan loai chi phi.

## Tai lieu nen tang

- [Quy trinh kiem soat tai chinh](./docs/01-financial-control-process.md)
- [Kien truc he thong](./docs/02-system-architecture.md)
- [Phan quyen va RACI](./docs/03-rbac-raci.md)
- [Chien luoc tich hop ngan hang MoMo Telegram AI](./docs/04-integration-strategy.md)
- [Lo trinh trien khai](./docs/05-implementation-roadmap.md)
- [Telegram chatbot va BotFather token](./docs/06-telegram-chatbot-token-data-flow.md)
- [Backend contract cho Antigravity](./docs/07-antigravity-backend-contract.md)
- [AI local phan tich anh chuyen khoan thu/chi](./docs/08-ai-phan-tich-thu-chi.md)
- [Da nguoi dung: moi user mot bot Telegram](./docs/09-multi-user-bot.md)
- [Trien khai len server rieng](./docs/10-trien-khai-production.md)

## Cau truc ung dung

```text
src/invmmc/
  api/                 FastAPI routes
  core/                cau hinh, database va bao mat
  domain/              entity, enum, policy nghiep vu
  integrations/        adapter Telegram, MoMo, ngan hang, AI local
  persistence/         SQLAlchemy models, bootstrap database
  services/            auth, workflow, approval, reporting, telegram intake
  static/              dashboard HTML/CSS/JS
tests/                 unit tests cho nghiep vu loi
```

## Backend hien tai

- Backend: FastAPI.
- Auth: login bang email/password, session cookie `invmmc_session`, HttpOnly. Co quen mat khau (`/forgot-password` -> email link -> `/reset-password`), can cau hinh `SMTP_*` trong `.env` de gui that (xem `.env.example`), khong thi link reset chi log ra console.
- RBAC: role nam trong bang `users.roles_json`.
- Database local: SQLite `data/invmmc.db`.
- Demo seed: tat mac dinh bang `DEMO_SEED_DATA=false`.
- Du lieu tai chinh hien tai da duoc lam sach; chi giu cau hinh integration va user admin.
- Antigravity co the thay the frontend trong `src/invmmc/static`, nhung nen giu API contract trong [docs/07-antigravity-backend-contract.md](./docs/07-antigravity-backend-contract.md).

## Cau truc luu data Telegram

Telegram duoc dung nhu chatbot nhap lieu va kenh gui anh/chung tu. Bot Token lay tu BotFather khong phai noi luu data; token chi dung de backend xac thuc voi Telegram Bot API, nhan webhook va download file anh.

Data duoc luu trong he thong nhu sau:

- Noi dung chat, caption, amount hint, project code: luu trong database.
- Anh/chung tu chuyen khoan: luu trong `data/uploads` khi chay local, production nen dung object storage noi bo.
- Metadata Telegram: `chat_id`, `message_id`, `file_id`, `received_at`, `status`: luu trong bang `transfer_attachments`.
- Ket qua AI phan tich thu/chi: `transaction_type`, `ai_summary`, `ai_confidence`, `review_status` trong `transfer_attachments`; xem [docs/08](./docs/08-ai-phan-tich-thu-chi.md).
- Token that: luu trong `.env` bang `TELEGRAM_BOT_TOKEN`, khong luu trong source code hoac dashboard production.

Khong co HTTPS webhook cong khai van chay duoc: `scripts/telegram_polling.py` long-poll getUpdates roi forward vao webhook local, chi can Bot Token.

## Chay local

Yeu cau:

- Python 3.11+
- Docker Desktop neu muon chay PostgreSQL/Redis bang `docker compose`
- Telegram Bot token neu can test webhook that
- Ollama neu can AI local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
uvicorn invmmc.main:app --reload
```

Dashboard:

- http://127.0.0.1:8000/login
- http://127.0.0.1:8000/dashboard
- http://127.0.0.1:8000/docs

Neu dung Docker cho database:

```powershell
docker compose up -d postgres redis
```

Kiem tra:

```powershell
pytest
```

## Bien moi truong chinh

Xem file [.env.example](./.env.example).

Cac token va secret khong duoc commit len git. Moi provider thanh toan/ngan hang se can xac minh hop dong, IP allowlist, webhook secret va che do sandbox rieng.

Mac dinh local dung SQLite tai `data/invmmc.db` va luu anh/chung tu Telegram trong `data/uploads`. Production nen dung PostgreSQL, object storage noi bo, backup va phan quyen file ro rang.

## Nguon API tham chieu

- Telegram Bot API: https://core.telegram.org/bots/api
- MoMo Developers Vietnam: https://developers.momo.vn/v3/
- VietQR API: https://api.vietqr.vn/en
