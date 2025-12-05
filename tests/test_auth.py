from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    payload = {
        "email": "test@example.com",
        "password": "password123",
        "first_name": "Test",
        "last_name": "User",
        "address": "123 Test St",
        "city": "Test City",
        "country": "Test Country",
        "zip_code": "12345",
        "phone": "1234567890"
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
        "password": "password123",
        "first_name": "Login",
        "last_name": "User",
        "address": "123 Test St",
        "city": "Test City",
        "country": "Test Country",
        "zip_code": "12345",
        "phone": "1234567890"
    }
    client.post("/users/register", json=register_payload)

    # Login
    login_payload = {
        "email": "login@example.com",
        "password": "password123"
    }
    response = client.post("/users/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["token_type"] == "Bearer"


def test_login_invalid_credentials(client: TestClient):
    login_payload = {
        "email": "wrong@example.com",
        "password": "wrongpassword"
    }
    response = client.post("/users/login", json=login_payload)
    assert response.status_code == 401
