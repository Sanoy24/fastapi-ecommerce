import pytest
from fastapi.testclient import TestClient

_USER = {
    "email": "address@test.com",
    "password": "StrongPassword123!",
    "first_name": "Address",
    "last_name": "User",
    "phone": "0911000000",
}

_ADDRESS = {
    "type": "home",
    "street": "123 Test St",
    "city": "Testville",
    "state": "TS",
    "postal_code": "12345",
    "country": "Testland",
    "is_default": True,
}

@pytest.fixture
def user_tokens(client: TestClient) -> dict:
    client.post("/users/register", json=_USER)
    resp = client.post(
        "/users/login",
        json={"email": _USER["email"], "password": _USER["password"]},
    )
    return resp.json()

@pytest.fixture
def auth_headers(user_tokens: dict) -> dict:
    return {"Authorization": f"Bearer {user_tokens['access_token']}"}

class TestAddresses:
    def test_add_address(self, client: TestClient, auth_headers: dict):
        resp = client.post(
            "/users/me/address",
            headers=auth_headers,
            json=_ADDRESS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["street"] == _ADDRESS["street"]
        assert data["city"] == _ADDRESS["city"]
        assert data["state"] == _ADDRESS["state"]
        assert data["postal_code"] == _ADDRESS["postal_code"]
        assert data["country"] == _ADDRESS["country"]
        assert data["is_default"] is True
        assert "id" in data

    def test_update_address(self, client: TestClient, auth_headers: dict):
        # Create address
        resp = client.post(
            "/users/me/address",
            headers=auth_headers,
            json=_ADDRESS,
        )
        address_id = resp.json()["id"]

        # Update address
        update_data = {"city": "New City"}
        update_resp = client.put(
            f"/users/me/address/{address_id}",
            headers=auth_headers,
            json=update_data,
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["city"] == "New City"
        assert updated["street"] == _ADDRESS["street"] # unchanged
        
    def test_update_nonexistent_address_fails(self, client: TestClient, auth_headers: dict):
        update_resp = client.put(
            "/users/me/address/9999",
            headers=auth_headers,
            json={"city": "Nowhere"},
        )
        assert update_resp.status_code == 404
        assert update_resp.json()["detail"] == "Address not found"
