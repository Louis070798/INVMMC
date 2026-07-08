# Trien khai len server rieng (khong con phu thuoc laptop)

## 1. Vi sao truoc gio phu thuoc laptop

Ba thanh phan sau mac dinh gia dinh chay chung MOT may:

- **Ollama (AI local)**: `OLLAMA_BASE_URL=http://localhost:11434` - chi goi duoc
  neu Ollama cai tren CHINH may chay backend.
- **Bridge Telegram** (`scripts/telegram_polling.py`): forward update vao
  `INTERNAL_WEBHOOK_BASE_URL` (mac dinh `http://127.0.0.1:8000`) - phai la dia
  chi cua chinh may no dang chay, khong phai may khac.
- **Database SQLite**: `DATABASE_URL=sqlite:///./data/invmmc.db` - file nam
  tren dia cua may dang chay backend.

Neu chi dem code sang server khac ma khong dem ca ba thu tren, server moi se
"khong lam duoc gi" hoac van quay ve goi laptop - dung y nhu tinh huong da gap.

**Nguyen tac triln khai**: backend (uvicorn) + bridge (telegram_polling.py) +
Ollama + file database phai nam CUNG MOT server. Server do co the la VPS,
may vat ly, hay may ao noi bo - mien la ca bon thu tren cung server, tu chay
doc lap, khong can laptop bat.

## 2. Chuan bi server (Linux, khuyen nghi)

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv git curl

# Ollama - AI local, PHAI cai o day
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5vl:3b
```

## 3. Lay code va cai dat

```bash
sudo mkdir -p /opt/invmmc && sudo chown $USER /opt/invmmc
cd /opt/invmmc
git clone https://github.com/Louis070798/INVMMC.git repo
cd repo/01-INVMMC

python3.11 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
cp .env.example .env
```

## 4. Sua `.env` cho DUNG server nay

Khong copy nguyen `.env` tu laptop sang - it nhat phai doi:

| Bien | Gia tri tren server |
|---|---|
| `APP_BASE_URL` | URL cong khai that (vd `https://invmmc.congty.vn`), chi de hien thi |
| `INTERNAL_WEBHOOK_BASE_URL` | De nguyen `http://127.0.0.1:8000` (loopback cua chinh server) |
| `OLLAMA_BASE_URL` | De nguyen `http://localhost:11434` - vi Ollama vua cai o buoc 2 |
| `DATABASE_URL` | De nguyen (SQLite rieng cua server nay) hoac tro sang Postgres that su can HA |
| `JWT_SECRET`, `TELEGRAM_WEBHOOK_SECRET` | Sinh moi, KHONG dung lai gia tri cu: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Dat mat khau that, doi ngay sau lan dang nhap dau |
| `TELEGRAM_BOT_TOKEN` | De trong - moi user tu dan token bot rieng o Settings sau khi dang nhap |
| `AI_ENABLED` | `true` neu server du RAM chay Ollama vision (toi thieu ~4-6GB rang cho model 3b) |
| `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | Dien that de tinh nang "Quen mat khau" gui duoc email - de trong thi link reset chi bi log ra console (`journalctl -u invmmc-api`), khong dung cho production |

## 5. Khoi tao du lieu lan dau

```bash
./.venv/bin/python -c "from invmmc.persistence.bootstrap import init_db; init_db()"
```

Lenh nay tao file `data/invmmc.db`, cac bang, va tai khoan admin theo
`ADMIN_EMAIL`/`ADMIN_PASSWORD` trong `.env`.

## 6. Chay thuong truc bang systemd

Copy 2 file mau trong thu muc `deploy/` cua repo, sua `User=` va duong dan
`/opt/invmmc/01-INVMMC` cho khop that:

```bash
sudo cp deploy/invmmc-api.service deploy/invmmc-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now invmmc-api invmmc-bridge
sudo systemctl status invmmc-api invmmc-bridge
```

Hai service tu `Restart=always` - server reboot hay tien trinh crash deu tu
chay lai, khong can ai bat tay.

**Quan trong**: sau khi bridge chay tren server nay, TAT bridge dang chay tren
laptop di (neu con) - hai noi cung poll chung 1 token se bao loi 409 xen ke
(da gap loi nay khi chay 2 bridge song song tren cung 1 may).

## 7. Mo cong ra ngoai (tuy chon)

Khong can mo cong nao cho Telegram (long-polling la outbound-only). Chi can mo
cong cho nguoi dung truy cap dashboard, khuyen nghi qua reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name invmmc.congty.vn;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

`uvicorn` van bind `127.0.0.1` (khong `0.0.0.0`) - chi nginx moi lo phan TLS va
mo cong 443/80 ra internet.

## 8. Sau khi deploy

- Dang nhap bang `ADMIN_EMAIL`/`ADMIN_PASSWORD` -> doi mat khau ngay trong
  trang Admin (hoac lam lai buoc doi ADMIN_PASSWORD trong `.env` + tao user
  moi qua trang Quan tri).
- Moi nguoi dung tu vao Settings dan token bot Telegram rieng cua ho
  ([docs/09](./09-multi-user-bot.md)) - khong can dong gi them tren server.
- Xem log: `journalctl -u invmmc-api -f` va `journalctl -u invmmc-bridge -f`.
