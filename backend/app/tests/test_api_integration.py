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

        listing = client.get("/api/v1/tds-events", params={"limit": 100}, headers=headers)
        assert listing.status_code == 200
        assert len(listing.json()["items"]) == body["tds_events_created"]

        transactions = client.get("/api/v1/transactions", params={"limit": 100}, headers=headers)
        assert transactions.status_code == 200
        assert len(transactions.json()["items"]) == body["transactions_created"]

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
        assert b_transactions.json()["items"] == []

    def test_user_cannot_see_another_users_tds_events(self):
        headers_a = _register_and_login("isolation-c@example.com")
        headers_b = _register_and_login("isolation-d@example.com")

        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers_a)

        b_events = client.get("/api/v1/tds-events", headers=headers_b)
        assert b_events.json()["items"] == []

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


class TestTransactionWorkflow:
    def test_reports_include_manual_transactions_but_exclude_synthetic_feed(self, monkeypatch):
        from app.routers import reports as reports_router

        headers = _register_and_login("report-sources@example.com")
        simulated = client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers)
        assert simulated.status_code == 201
        assert simulated.json()["tds_events_created"] > 0

        manual = client.post(
            "/api/v1/transactions/manual",
            json={
                "entries": [
                    {
                        "transaction_date": "2026-05-10",
                        "amount": "60000",
                        "party_name": "Manual Consulting",
                        "description": "Professional consulting service",
                        "declared_category": "professional_fees",
                        "party_pan_provided": True,
                        "rule_context": {
                            "payer_is_specified_person": True,
                            "service_kind": "professional",
                        },
                    }
                ]
            },
            headers=headers,
        )
        assert manual.status_code == 201
        assert manual.json()["tds_events_created"] == 1

        captured_reports = []
        monkeypatch.setattr(
            reports_router,
            "generate_excel_report",
            lambda report_input: captured_reports.append(report_input) or b"test report",
        )
        report = client.post(
            "/api/v1/reports/generate",
            json={"financial_year": "2026-27", "report_type": "excel"},
            headers=headers,
        )

        assert report.status_code == 201
        assert len(captured_reports) == 1
        assert len(captured_reports[0].tds_events) == 1
        assert captured_reports[0].tds_events[0].vendor_name == "Manual Consulting"

    def test_delete_complete_reopen_and_restore_transaction(self):
        headers = _register_and_login("workflow@example.com")
        ingested = client.post(
            "/api/v1/transactions/manual",
            json={
                "entries": [
                    {
                        "transaction_date": "2026-05-10",
                        "amount": "60000",
                        "party_name": "Workflow Consulting",
                        "description": "Professional consulting service",
                        "declared_category": "professional_fees",
                        "party_pan_provided": True,
                        "rule_context": {
                            "payer_is_specified_person": True,
                            "service_kind": "professional",
                        },
                    }
                ]
            },
            headers=headers,
        )
        assert ingested.status_code == 201
        transaction_id = client.get("/api/v1/transactions", headers=headers).json()["items"][0]["id"]

        unpaid_events = client.get(
            "/api/v1/tds-events",
            params={"transaction_completed": False, "limit": 100},
            headers=headers,
        ).json()
        assert unpaid_events["flagged_count"] == 1
        assert unpaid_events["total_tds_due"] != "0"
        assert unpaid_events["upcoming_deadlines"]
        assert unpaid_events["items"][0]["transaction_date"] == "2026-05-10"

        completed = client.patch(
            f"/api/v1/transactions/{transaction_id}/complete",
            headers=headers,
        )
        assert completed.status_code == 200
        assert completed.json()["is_completed"] is True
        paid_events = client.get(
            "/api/v1/tds-events",
            params={"transaction_completed": True, "limit": 100},
            headers=headers,
        ).json()
        assert paid_events["flagged_count"] == 1
        assert paid_events["total_tds_due"] == "0"
        assert paid_events["upcoming_deadlines"] == []
        assert client.get(
            "/api/v1/transactions",
            params={"include_completed": False},
            headers=headers,
        ).json()["total"] == 0

        reopened = client.patch(
            f"/api/v1/transactions/{transaction_id}/reopen",
            headers=headers,
        )
        assert reopened.status_code == 200
        assert reopened.json()["is_completed"] is False

        deleted = client.delete(
            f"/api/v1/transactions/{transaction_id}",
            headers=headers,
        )
        assert deleted.status_code == 204
        assert all(
            transaction["id"] != transaction_id
            for transaction in client.get("/api/v1/transactions", headers=headers).json()["items"]
        )
        deleted_events = client.get("/api/v1/tds-events", headers=headers)
        assert deleted_events.json()["total"] == 0
        assert deleted_events.json()["flagged_count"] == 0

        restored = client.patch(
            f"/api/v1/transactions/{transaction_id}/restore",
            headers=headers,
        )
        assert restored.status_code == 200
        assert restored.json()["is_deleted"] is False

    def test_batch_delete_complete_reopen_and_restore_transactions(self):
        headers = _register_and_login("batch-workflow@example.com")
        entries = [
            {
                "transaction_date": "2026-05-10",
                "amount": "60000",
                "party_name": "Batch Consulting 1",
                "description": "Professional consulting service 1",
                "declared_category": "professional_fees",
                "party_pan_provided": True,
                "rule_context": {
                    "payer_is_specified_person": True,
                    "service_kind": "professional",
                },
            },
            {
                "transaction_date": "2026-05-11",
                "amount": "70000",
                "party_name": "Batch Consulting 2",
                "description": "Professional consulting service 2",
                "declared_category": "professional_fees",
                "party_pan_provided": True,
                "rule_context": {
                    "payer_is_specified_person": True,
                    "service_kind": "professional",
                },
            },
        ]
        ingested = client.post(
            "/api/v1/transactions/manual",
            json={"entries": entries},
            headers=headers,
        )
        assert ingested.status_code == 201
        tx_items = client.get("/api/v1/transactions", headers=headers).json()["items"]
        ids = [t["id"] for t in tx_items]
        assert len(ids) == 2

        # Batch complete
        complete_res = client.post(
            "/api/v1/transactions/batch-complete",
            json={"transaction_ids": ids},
            headers=headers,
        )
        assert complete_res.status_code == 200
        assert len(complete_res.json()) == 2

        # Batch reopen
        reopen_res = client.post(
            "/api/v1/transactions/batch-reopen",
            json={"transaction_ids": ids},
            headers=headers,
        )
        assert reopen_res.status_code == 200
        assert len(reopen_res.json()) == 2

        # Batch delete
        delete_res = client.post(
            "/api/v1/transactions/batch-delete",
            json={"transaction_ids": ids},
            headers=headers,
        )
        assert delete_res.status_code == 204
        remaining = client.get("/api/v1/transactions", headers=headers).json()["items"]
        assert remaining == []

        # Batch restore
        restore_res = client.post(
            "/api/v1/transactions/batch-restore",
            json={"transaction_ids": ids},
            headers=headers,
        )
        assert restore_res.status_code == 200
        assert len(restore_res.json()) == 2

    def test_synthetic_transactions_are_reference_only_and_removable_as_feed(self):
        headers = _register_and_login("synthetic-workflow@example.com")
        simulated = client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers)
        assert simulated.status_code == 201
        transaction_id = client.get("/api/v1/transactions", headers=headers).json()["items"][0]["id"]
        recent_transactions = client.get(
            "/api/v1/transactions",
            params={"recent_only": True},
            headers=headers,
        )
        assert recent_transactions.json()["total"] == 0

        forbidden = client.patch(
            f"/api/v1/transactions/{transaction_id}/complete",
            headers=headers,
        )
        assert forbidden.status_code == 404

        removed = client.delete("/api/v1/transactions/synthetic-feed", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["transactions_removed"] == simulated.json()["transactions_created"]
        assert client.get("/api/v1/transactions", headers=headers).json()["total"] == 0

    def test_transaction_search_matches_indexed_description_and_exact_amount(self):
        headers = _register_and_login("transaction-search@example.com")
        client.post(
            "/api/v1/transactions/manual",
            json={
                "entries": [
                    {
                        "transaction_date": "2026-05-10",
                        "amount": "45250.00",
                        "party_name": "Northstar Design",
                        "description": "Annual design consulting retainer",
                    }
                ]
            },
            headers=headers,
        )

        by_description = client.get(
            "/api/v1/transactions",
            params={"search": "design consulting", "recent_only": True},
            headers=headers,
        )
        assert by_description.status_code == 200
        assert by_description.json()["total"] == 1

        by_amount = client.get(
            "/api/v1/transactions",
            params={"search": "45,250.00", "recent_only": True},
            headers=headers,
        )
        assert by_amount.status_code == 200
        assert by_amount.json()["total"] == 1

        event_search = client.get(
            "/api/v1/tds-events",
            params={"search": "design consulting"},
            headers=headers,
        )
        assert event_search.status_code == 200
        assert event_search.json()["total"] == 1
        assert event_search.json()["items"][0]["transaction_date"] == "2026-05-10"


class TestAccountDeletion:
    def test_deleting_account_removes_access_and_cascades_data(self):
        headers = _register_and_login("delete-me@example.com")
        client.post("/api/v1/transactions/simulate", json={"seed": 42}, headers=headers)

        delete_response = client.delete("/api/v1/users/me", headers=headers)
        assert delete_response.status_code == 204

        # The token belonged to a now-deleted user; it must no longer work.
        follow_up = client.get("/api/v1/auth/me", headers=headers)
        assert follow_up.status_code == 401
