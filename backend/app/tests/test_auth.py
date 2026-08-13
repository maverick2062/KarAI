from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.main import app

client = TestClient(app)


def _register(email="alice@example.com", password="Passw0rd1"):
    return client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Alice", "password": password},
    )


class TestRegister:
    def test_register_succeeds(self):
        response = _register("register-success@example.com")
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == "register-success@example.com"
        assert "hashed_password" not in body

    def test_duplicate_email_rejected(self):
        _register("duplicate@example.com")
        response = _register("duplicate@example.com")
        assert response.status_code == 409

    def test_weak_password_rejected(self):
        response = _register("weak-pw@example.com", password="alllettersnodigits")
        assert response.status_code == 422

    def test_cannot_self_register_as_admin(self):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "wannabe-admin@example.com", "full_name": "X", "password": "Passw0rd1", "role": "admin"},
        )
        assert response.status_code == 422


class TestLoginAndLockout:
    def test_login_with_correct_credentials_returns_token(self):
        _register("login-ok@example.com", "Passw0rd1")
        response = client.post("/api/v1/auth/login", json={"email": "login-ok@example.com", "password": "Passw0rd1"})
        assert response.status_code == 200
        assert response.json()["token_type"] == "bearer"

    def test_login_with_wrong_password_returns_401(self):
        _register("login-bad@example.com", "Passw0rd1")
        response = client.post("/api/v1/auth/login", json={"email": "login-bad@example.com", "password": "wrong"})
        assert response.status_code == 401

    def test_account_locks_after_five_failed_attempts(self):
        email = "lockout@example.com"
        _register(email, "Passw0rd1")

        for _ in range(5):
            response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
            assert response.status_code == 401

        # 6th attempt, even with the CORRECT password, must be locked out.
        response = client.post("/api/v1/auth/login", json={"email": email, "password": "Passw0rd1"})
        assert response.status_code == 423

    def test_successful_login_resets_failed_attempt_counter(self):
        email = "reset-counter@example.com"
        _register(email, "Passw0rd1")

        for _ in range(3):
            client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})

        ok = client.post("/api/v1/auth/login", json={"email": email, "password": "Passw0rd1"})
        assert ok.status_code == 200

        # Two more wrong attempts after a successful login shouldn't lock (counter reset to 0).
        for _ in range(2):
            client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})
        still_ok = client.post("/api/v1/auth/login", json={"email": email, "password": "Passw0rd1"})
        assert still_ok.status_code == 200


class TestTokenAuthAndLogout:
    def test_me_requires_token(self):
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token_returns_401(self):
        response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        assert response.status_code == 401

    def test_me_with_valid_token_succeeds(self):
        _register("me-endpoint@example.com", "Passw0rd1")
        login = client.post("/api/v1/auth/login", json={"email": "me-endpoint@example.com", "password": "Passw0rd1"})
        token = login.json()["access_token"]

        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["email"] == "me-endpoint@example.com"

    def test_logout_revokes_token(self):
        _register("logout-test@example.com", "Passw0rd1")
        login = client.post("/api/v1/auth/login", json={"email": "logout-test@example.com", "password": "Passw0rd1"})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

        logout_response = client.post("/api/v1/auth/logout", headers=headers)
        assert logout_response.status_code == 204

        # The exact same (now-revoked) token must be rejected, even though it hasn't expired.
        assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


class TestRateLimitingMechanism:
    """Exercises the same slowapi Limiter class used in app.security.limiter,
    on an isolated low-limit route, so the test is fast and doesn't interfere
    with the 100/minute limit used by the real app in other tests."""

    def test_exceeding_the_limit_returns_429(self):
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse

        limiter = Limiter(key_func=get_remote_address)
        test_app = FastAPI()
        test_app.state.limiter = limiter

        @test_app.exception_handler(RateLimitExceeded)
        def _handler(request: Request, exc: RateLimitExceeded):
            return JSONResponse(status_code=429, content={"detail": "rate limited"})

        @test_app.get("/ping")
        @limiter.limit("2/minute")
        def ping(request: Request):
            return {"pong": True}

        test_client = TestClient(test_app)
        assert test_client.get("/ping").status_code == 200
        assert test_client.get("/ping").status_code == 200
        assert test_client.get("/ping").status_code == 429
