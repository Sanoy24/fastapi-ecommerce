from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    payload = {
        "email": "test@example.com",
        "password": "Password1",  # Updated: meets uppercase + digit requirement
        "first_name": "Test",
        "last_name": "User",
        "phone": "1234567890",
    }
    response = client.post("/users/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == payload["email"]
    assert "id" in data


def test_login_user(client: TestClient):
    # Register first
    register_payload = {
        "email": "login@example.com",
        "password": "Password1",
        "first_name": "Login",
        "last_name": "User",
        "phone": "1234567890",
    }
    client.post("/users/register", json=register_payload)

    # Login
    login_payload = {
        "email": "login@example.com",
        "password": "Password1",
    }
    response = client.post("/users/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data       # Updated: new TokenSchema field name
    assert "refresh_token" in data      # New: refresh token now returned
    assert data["token_type"] == "Bearer"
    assert "expires_in" in data


def test_login_invalid_credentials(client: TestClient):
    login_payload = {
        "email": "wrong@example.com",
        "password": "wrongpassword",
    }
    response = client.post("/users/login", json=login_payload)
    assert response.status_code == 401


def test_register_duplicate_email_fails(client: TestClient):
    payload = {
        "email": "dup@example.com",
        "password": "Password1",
        "first_name": "Dup",
        "last_name": "User",
        "phone": "1234567891",
    }
    client.post("/users/register", json=payload)
    resp = client.post("/users/register", json=payload)
    assert resp.status_code == 400

