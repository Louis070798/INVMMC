# Phan quyen va RACI

## 1. Vai tro

| Vai tro | Mo ta |
|---|---|
| Employee | Tao de nghi chi/tam ung cua ban than |
| Project Member | Tao chi phi gan voi du an duoc tham gia |
| Project Manager | Phe duyet chi phi trong han muc du an |
| Department Head | Phe duyet chi phi cap phong ban |
| Finance Controller | Kiem tra ngan sach, chung tu, thue, coding chi phi |
| Finance Manager | Quan ly doi finance va phe duyet cap trung |
| Accountant | Lap lenh thanh toan, cap nhat chung tu |
| Treasury | Thuc hien thanh toan va doi soat dong tien |
| CFO | Phe duyet chi phi lon, vuot ngan sach, ngoai le |
| CEO/Board | Phe duyet chi phi rat lon hoac chien luoc |
| System Admin | Quan ly nguoi dung, cau hinh, khong tu dong co quyen phe duyet tai chinh |
| Auditor | Chi doc bao cao va audit log |

## 2. Quyen he thong

| Quyen | Employee | PM | Finance | CFO | Admin | Auditor |
|---|---:|---:|---:|---:|---:|---:|
| Tao de nghi chi | Y | Y | Y | Y | N | N |
| Sua draft cua minh | Y | Y | Y | Y | N | N |
| Xem chi phi du an | Project | Project | All | All | Config | All |
| Kiem tra finance | N | N | Y | Y | N | N |
| Phe duyet | N | Y | Theo vai tro | Y | N | N |
| Lap lenh thanh toan | N | N | Accountant | N | N | N |
| Thuc hien thanh toan | N | N | Treasury | N | N | N |
| Sua ngan sach | N | De xuat | Y | Y | N | N |
| Quan ly user | N | N | N | N | Y | N |
| Xem audit log | N | Project | Y | Y | Y | Y |

## 2.1. RBAC backend da implement

Backend hien tai dung `users.roles_json` de gan nhieu role cho mot user. Session dang nhap duoc luu trong `user_sessions`, browser giu cookie `invmmc_session`.

Role groups trong code:

| Nhom quyen | Roles |
|---|---|
| FINANCE_READ_ROLES | system_admin, cfo, ceo, finance_manager, finance_controller, accountant, treasury, auditor, project_manager |
| FINANCE_WRITE_ROLES | system_admin, cfo, ceo, finance_manager, finance_controller, accountant, project_manager |
| CONFIG_ROLES | system_admin, cfo, finance_manager |
| Upload/chung tu read | system_admin, cfo, finance_manager, auditor |

Endpoint auth:

| Endpoint | Quyen |
|---|---|
| `GET /login` | public |
| `POST /api/v1/auth/login` | public |
| `POST /api/v1/auth/logout` | authenticated |
| `GET /api/v1/auth/me` | authenticated |
| `GET /dashboard` | authenticated |
| `GET /api/v1/dashboard/summary` | FINANCE_READ_ROLES |
| `GET /api/v1/projects` | FINANCE_READ_ROLES |
| `POST /api/v1/projects` | FINANCE_WRITE_ROLES |
| `POST /api/v1/expenses` | FINANCE_WRITE_ROLES |
| `GET /api/v1/integrations` | CONFIG_ROLES |
| `PATCH /api/v1/integrations/{key}` | CONFIG_ROLES |
| `GET /api/v1/reports/export` | FINANCE_READ_ROLES |
| `GET /uploads/{path}` | system_admin, cfo, finance_manager, auditor |

Default admin local:

```text
ADMIN_EMAIL=admin@invmmc.local
ADMIN_PASSWORD=Admin@123456
ADMIN_ROLES=system_admin,cfo,finance_manager,auditor
```

Production phai doi password va nen chuyen sang SSO hoac secret manager.

## 3. RACI quy trinh de nghi chi

| Buoc | Employee | PM | Finance Controller | Accountant | Treasury | CFO |
|---|---|---|---|---|---|---|
| Tao de nghi | R | A neu thay mat | C | I | I | I |
| Kiem tra ngan sach | I | C | R/A | I | I | C |
| Phe duyet nghiep vu | I | R/A | C | I | I | A neu ngoai le |
| Lap thanh toan | I | I | C | R/A | C | I |
| Chuyen tien | I | I | I | C | R/A | I |
| Doi soat | I | I | R | C | C | I |
| Bao cao sai lech | I | C | R | C | I | A |

R = Responsible, A = Accountable, C = Consulted, I = Informed.

## 4. Chinh sach bat buoc

- Admin he thong khong co quyen phe duyet tai chinh mac dinh.
- CFO co the phe duyet ngoai le nhung van can audit reason.
- Nguoi tao de nghi khong the la nguoi phe duyet cuoi.
- Moi thay doi role phai co ly do va nguoi phe duyet.
- Role theo du an het hieu luc khi du an dong.
