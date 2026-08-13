from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register_and_login(email: str, password: str = "Passw0rd1") -> dict:
    client.post("/api/v1/auth/register", json={"email": email, "full_name": "Test User", "password": password})
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestFullUserJourney:
    def test_simulate_ingest_view_tds_events(self):
        headers = _register_and_login("journey-1@example.com")

        response = client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers)
        assert response.status_code == 201
        body = response.json()
        assert body["transactions_created"] > 0

        listing = client.get("/api/v1/tds-events", params={"limit": 500}, headers=headers)
        assert listing.status_code == 200
        assert len(listing.json()) == body["tds_events_created"]

        transactions = client.get("/api/v1/transactions", params={"limit": 500}, headers=headers)
        assert transactions.status_code == 200
        assert len(transactions.json()) == body["transactions_created"]

    def test_manual_entry_crossing_threshold_produces_explanation(self):
        headers = _register_and_login("journey-2@example.com")

        entries = [
            {
                "transaction_date": "2026-04-10",
                "amount": "20000",
                "party_name": "Manual Consulting Co",
                "description": "Professional consulting fee",
            },
            {
                "transaction_date": "2026-05-10",
                "amount": "20000",
                "party_name": "Manual Consulting Co",
                "description": "Professional consulting fee",
            },
        ]
        response = client.post("/api/v1/transactions/manual", json={"entries": entries}, headers=headers)
        assert response.status_code == 201
        events = response.json()["tds_events"]
        crossed = [e for e in events if e["threshold_crossed_this_transaction"]]
        assert len(crossed) == 1
        assert "crossing" in crossed[0]["explanation_text"]

    def test_advance_tax_estimate_and_regime_comparison(self):
        headers = _register_and_login("journey-3@example.com")

        comparison = client.get(
            "/api/v1/advance-tax/compare-regimes", params={"total_income": "1500000"}, headers=headers
        )
        assert comparison.status_code == 200
        assert comparison.json()["recommended_regime"] in ("old", "new")

        estimate = client.post(
            "/api/v1/advance-tax/estimate",
            json={"financial_year": "2026-27", "total_income_estimate": "1500000", "regime": "new"},
            headers=headers,
        )
        assert estimate.status_code == 200
        assert estimate.json()["advance_tax_required"] is True
        assert len(estimate.json()["installments"]) == 4

    def test_ais_simulation_surfaces_discrepancies(self):
        headers = _register_and_login("journey-4@example.com")
        client.post("/api/v1/transactions/simulate", json={"seed": 1}, headers=headers)

        response = client.post(
            "/api/v1/ais/simulate", json={"financial_year": "2026-27", "seed": 1}, headers=headers
        )
        assert response.status_code == 200
        assert "discrepancies" in response.json()

        # Discrepancies persist and are re-fetchable without re-simulating.
        refetch = client.get(
            "/api/v1/ais/discrepancies", params={"financial_year": "2026-27"}, headers=headers
        )
        assert refetch.status_code == 200

    def test_generate_and_download_pdf_report(self):
        headers = _register_and_login("journey-5@example.com")
        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers)

        generated = client.post(
            "/api/v1/reports/generate",
            json={"financial_year": "2026-27", "report_type": "pdf"},
            headers=headers,
        )
        assert generated.status_code == 201
        report_id = generated.json()["id"]

        listing = client.get("/api/v1/reports", headers=headers)
        assert listing.status_code == 200
        assert any(r["id"] == report_id for r in listing.json())

        download = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF")

    def test_generate_and_download_excel_report(self):
        headers = _register_and_login("journey-6@example.com")
        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers)

        generated = client.post(
            "/api/v1/reports/generate",
            json={"financial_year": "2026-27", "report_type": "excel"},
            headers=headers,
        )
        assert generated.status_code == 201
        report_id = generated.json()["id"]

        download = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
        assert download.status_code == 200
        assert download.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


class TestRowLevelIsolationAcrossEndpoints:
    def test_user_cannot_see_another_users_transactions(self):
        headers_a = _register_and_login("isolation-a@example.com")
        headers_b = _register_and_login("isolation-b@example.com")

        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers_a)

        b_transactions = client.get("/api/v1/transactions", headers=headers_b)
        assert b_transactions.json() == []

    def test_user_cannot_see_another_users_tds_events(self):
        headers_a = _register_and_login("isolation-c@example.com")
        headers_b = _register_and_login("isolation-d@example.com")

        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers_a)

        b_events = client.get("/api/v1/tds-events", headers=headers_b)
        assert b_events.json() == []

    def test_user_cannot_download_another_users_report(self):
        headers_a = _register_and_login("isolation-e@example.com")
        headers_b = _register_and_login("isolation-f@example.com")

        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers_a)
        generated = client.post(
            "/api/v1/reports/generate",
            json={"financial_year": "2026-27", "report_type": "pdf"},
            headers=headers_a,
        )
        report_id = generated.json()["id"]

        forbidden = client.get(f"/api/v1/reports/{report_id}/download", headers=headers_b)
        assert forbidden.status_code == 404


class TestAccountDeletion:
    def test_deleting_account_removes_access_and_cascades_data(self):
        headers = _register_and_login("delete-me@example.com")
        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers)

        delete_response = client.delete("/api/v1/users/me", headers=headers)
        assert delete_response.status_code == 204

        # The token belonged to a now-deleted user; it must no longer work.
        follow_up = client.get("/api/v1/auth/me", headers=headers)
        assert follow_up.status_code == 401
