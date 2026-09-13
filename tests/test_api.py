from fastapi.testclient import TestClient

from intelligence_os.main import app


def test_health_and_dashboard():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        dashboard = client.get("/")
        assert dashboard.status_code == 200
        assert "Raeburn Intelligence OS" in dashboard.text


def test_status_and_company_index():
    with TestClient(app) as client:
        status = client.get("/v1/status")
        assert status.status_code == 200
        payload = status.json()
        assert "integrations" in payload
        assert "companies_house" in payload["integrations"]

        companies = client.get("/v1/companies")
        assert companies.status_code == 200
        assert isinstance(companies.json(), list)


def test_opportunity_export():
    with TestClient(app) as client:
        response = client.get("/v1/opportunities.csv")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "recommended_action" in response.text
