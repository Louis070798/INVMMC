from fastapi.testclient import TestClient

from invmmc.core.config import settings
from invmmc.main import app


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert response.status_code == 200


def test_dashboard_requires_login_then_loads_after_auth() -> None:
    with TestClient(app) as client:
        login_page = client.get("/dashboard")
        assert "loginForm" in login_page.text

        login_admin(client)
        page = client.get("/dashboard")
        summary = client.get("/api/v1/dashboard/summary?period=month")

    assert page.status_code == 200
    assert "INVMMC Finance Dashboard" in page.text
    assert summary.status_code == 200
    assert "kpis" in summary.json()


XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_report_export_xlsx_default_and_csv_fallback() -> None:
    with TestClient(app) as client:
        locked = client.get("/api/v1/reports/export?period=week")
        assert locked.status_code == 401

        login_admin(client)
        xlsx = client.get("/api/v1/reports/export?period=week")
        csv_response = client.get("/api/v1/reports/export?period=week&fmt=csv")

    assert xlsx.status_code == 200
    assert xlsx.headers["content-type"].startswith(XLSX_CONTENT_TYPE)
    assert xlsx.content[:2] == b"PK"  # xlsx la file zip
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "code,name,owner,department,budget,actual,telegram_thu,telegram_chi,available" in csv_response.text


def test_transfers_export_xlsx_default_and_csv_fallback() -> None:
    with TestClient(app) as client:
        locked = client.get("/api/v1/transfers/export?period=month")
        assert locked.status_code == 401

        login_admin(client)
        by_month = client.get("/api/v1/transfers/export?period=month")
        by_month_csv = client.get("/api/v1/transfers/export?period=month&fmt=csv")
        by_year = client.get("/api/v1/transfers/export?period=year")
        custom = client.get("/api/v1/transfers/export?period=custom&start_date=2026-01-01&end_date=2026-12-31")
        custom_missing = client.get("/api/v1/transfers/export?period=custom")
        custom_reversed = client.get(
            "/api/v1/transfers/export?period=custom&start_date=2026-12-31&end_date=2026-01-01"
        )

    assert by_month.status_code == 200
    assert by_month.headers["content-type"].startswith(XLSX_CONTENT_TYPE)
    assert by_month.content[:2] == b"PK"
    assert by_month_csv.status_code == 200
    assert by_month_csv.headers["content-type"].startswith("text/csv")
    assert "received_at,transacted_at,project_code,project_name" in by_month_csv.text
    assert by_year.status_code == 200
    assert custom.status_code == 200
    assert 'filename="invmmc-giao-dich-2026-01-01-to-2026-12-31.xlsx"' in custom.headers["content-disposition"]
    assert custom_missing.status_code == 422
    assert custom_reversed.status_code == 422
