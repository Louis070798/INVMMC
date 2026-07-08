# Backend contract cho Antigravity

File nay la handoff cho Antigravity hoac bat ky frontend builder nao muon code lai UI ma khong phai doc toan bo backend.

## 1. Nguyen tac

- Khong luu token that trong frontend.
- Khong hard-code data tai chinh mau.
- Frontend doc data tu API.
- Login truoc khi goi API noi bo.
- Dung cookie session `invmmc_session`; khong can tu quan ly JWT trong localStorage.
- Upload/chung tu khong public; truy cap qua route `/uploads/{path}` sau khi login.
- Telegram Bot Token lay tu BotFather nam trong `.env`, frontend chi hien token status.

## 2. Tech stack backend

```text
Backend: FastAPI
Database ORM: SQLAlchemy
Local DB: SQLite data/invmmc.db
Production DB: PostgreSQL
Auth: email/password + HttpOnly session cookie
Password hash: PBKDF2 SHA256
Session storage: user_sessions.token_hash
```

## 3. Local URLs

```text
Login:      http://127.0.0.1:8000/login
Dashboard:  http://127.0.0.1:8000/dashboard
API docs:   http://127.0.0.1:8000/docs
Health:     http://127.0.0.1:8000/health
```

## 4. Auth flow

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "admin@invmmc.local",
  "password": "Admin@123456"
}
```

Response:

```json
{
  "id": "user-admin",
  "email": "admin@invmmc.local",
  "full_name": "System Admin",
  "roles": ["auditor", "cfo", "finance_manager", "system_admin"]
}
```

Backend sets cookie:

```text
invmmc_session=<opaque-session-token>; HttpOnly; SameSite=Lax
```

Frontend fetch should include credentials when cross-origin. Same-origin dashboard can call normally.

### Current user

```http
GET /api/v1/auth/me
```

401 means not logged in. Frontend should redirect to `/login`.

### Logout

```http
POST /api/v1/auth/logout
```

## 5. Role model

Roles are strings from `Role` enum:

```text
employee
project_member
project_manager
department_head
finance_controller
finance_manager
accountant
treasury
cfo
ceo
system_admin
auditor
```

Frontend can use `/api/v1/auth/me` to decide which tabs/actions to show.

Suggested UI rules:

| UI action | Required role group |
|---|---|
| View dashboard, projects, reports | FINANCE_READ_ROLES |
| Create project, create expense | FINANCE_WRITE_ROLES |
| Configure Telegram/Bank/MoMo | CONFIG_ROLES |
| View uploaded transfer images | system_admin, cfo, finance_manager, auditor |

## 6. API endpoints

### Health

```http
GET /health
```

Public.

### Dashboard summary

```http
GET /api/v1/dashboard/summary?period=month
GET /api/v1/dashboard/summary?period=week
GET /api/v1/dashboard/summary?period=day
GET /api/v1/dashboard/summary?period=month&project_id=prj-xxx
```

Requires finance read role.

Response shape:

```json
{
  "period": "month",
  "period_start": "2026-07-01T00:00:00+00:00",
  "kpis": {
    "total_budget": 0,
    "total_actual": 0,
    "available": 0,
    "pending_approvals": 0,
    "unmatched_transfers": 0
  },
  "projects": [],
  "approval_queue": [],
  "attachments": []
}
```

### Projects

```http
GET /api/v1/projects
```

Requires finance read role.

### Report export (project summary & transaction detail)

```http
GET /api/v1/reports/export?period=month&fmt=xlsx&lang=vi
GET /api/v1/transfers/export?period=month&fmt=xlsx&lang=vi
```

`lang=vi` (default) or `lang=en` - translates titles, sheet name, column
headers, review-status labels, and THU/CHI -> INCOME/EXPENSE inside the
generated .xlsx. `fmt=csv` still returns raw field-name headers (unaffected
by `lang`, since those are machine-oriented keys, not display text).

Khi truyen them `project_id` (loc theo 1 du an cu the), file name va tieu de
trong file doi sang dang theo du an thay vi theo ky han chung:

- File name: `invmmc-bao-cao-du-an-{MA_DU_AN}-{start}-to-{end}.xlsx` (ma du
  an duoc loc ky tu khong an toan cho ten file).
- Tieu de trong file (dong A2): `Du an: {Ten du an day du} ({Ma du an})  |
  Tu {start} - {end}` - dung TEN DAY DU cua du an (giu dau tieng Viet, khong
  bi rang buoc nhu ten file).

```http
POST /api/v1/projects
Content-Type: application/json

{
  "code": "PRJ001",
  "name": "Project name",
  "owner": "Owner name",
  "department": "Finance",
  "budget_amount": 100000000
}
```

Requires finance write role. Project moi tao co `status = "pending_approval"`;
duyet bang PATCH ben duoi. 409 `project_code_exists` neu trung ma.

```http
PATCH /api/v1/projects/{project_id}
Content-Type: application/json

{
  "code": "PRJ001",          // optional, 409 neu trung ma khac
  "name": "...",             // optional
  "owner": "...",            // optional
  "department": "...",       // optional
  "budget_amount": 200000000, // optional
  "status": "active"         // optional: pending_approval | active (duyet du an = active)
}
```

```http
DELETE /api/v1/projects/{project_id}
```

Requires finance write role. 409 `project_has_data:expenses=N,attachments=M`
neu du an con de nghi chi hoac chung tu tham chieu - phai go/chuyen truoc khi xoa.

### Expenses

```http
POST /api/v1/expenses
Content-Type: application/json

{
  "project_id": "prj-xxx",
  "requester_id": "user-id",
  "amount": 1200000,
  "currency": "VND",
  "budget_line_code": "OPS",
  "vendor_id": "vendor-1",
  "description": "Expense reason"
}
```

Requires finance write role.

### Integrations

```http
GET /api/v1/integrations
```

Requires config role. Status is live-enriched:

- Telegram calls Telegram API `getMe` and `getWebhookInfo`.
- Bank checks env credentials.
- MoMo checks env credentials.

```http
PATCH /api/v1/integrations/telegram
Content-Type: application/json

{
  "enabled": true,
  "status": "botfather_configured",
  "config": {
    "bot_username": "ThanhDinhBot",
    "webhook_secret": "masked-or-local-secret",
    "webhook_url": "https://your-domain.example.com/telegram/webhook",
    "token_status": "env"
  }
}
```

Frontend must not send raw Bot Token here.

### Reports

```http
GET /api/v1/reports/export?period=week
GET /api/v1/reports/export?period=month&project_id=prj-xxx
```

Returns CSV. Requires finance read role.

### Uploads

```http
GET /uploads/telegram/<filename>
```

Requires authenticated role: system_admin, cfo, finance_manager, auditor.

### Telegram webhook

```http
POST /telegram/webhook
X-Telegram-Bot-Api-Secret-Token: <TELEGRAM_WEBHOOK_SECRET>
```

Public from Telegram, protected by webhook secret.

## 7. Database tables currently implemented

```text
users
  id
  email
  full_name
  password_hash
  roles_json
  status
  created_at

user_sessions
  id
  user_id
  token_hash
  created_at
  expires_at
  revoked_at

projects
  id
  code
  name
  owner
  department
  budget_amount
  status
  created_at

expense_requests
  id
  project_id
  requester_id
  amount
  currency
  budget_line_code
  vendor_id
  description
  status
  created_at

transfer_attachments
  id
  project_id
  source
  telegram_file_id
  telegram_chat_id
  telegram_message_id
  file_name
  file_path
  caption
  amount_hint
  status
  received_at

integration_configs
  key
  provider
  enabled
  display_name
  status
  config_json
  updated_at
```

## 8. Environment variables

Important local `.env` variables:

```env
DATABASE_URL=sqlite:///./data/invmmc.db
UPLOAD_DIR=./data/uploads
DEMO_SEED_DATA=false

TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=

ADMIN_EMAIL=admin@invmmc.local
ADMIN_PASSWORD=Admin@123456
ADMIN_FULL_NAME=System Admin
ADMIN_ROLES=system_admin,cfo,finance_manager,auditor
```

Production notes:

- Set `ADMIN_PASSWORD` to a strong secret before first boot.
- Prefer SSO later.
- Move secrets to secret manager.
- Use PostgreSQL and object storage.

## 9. Frontend implementation notes for Antigravity

Antigravity can replace the static files:

```text
src/invmmc/static/dashboard.html
src/invmmc/static/app.js
src/invmmc/static/styles.css
src/invmmc/static/login.html
```

Do not change backend contract unless coordinated.

Recommended app tabs:

- Login
- Dashboard
- Projects
- Approval Queue
- Integrations
- Reports
- Transfers/Documents
- Settings

Recommended startup logic:

1. Call `/api/v1/auth/me`.
2. If 401, show login or redirect `/login`.
3. Based on roles, show/hide tabs and buttons.
4. Fetch dashboard data with `/api/v1/dashboard/summary`.
5. Use `/api/v1/integrations` for real provider status.

## 10. Current data state

Financial data has been cleared:

```text
projects = 0
expense_requests = 0
transfer_attachments = 0
```

System data remains:

```text
integration_configs = 3
users = 1 default admin
```
