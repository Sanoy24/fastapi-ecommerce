"""Tests for brand CRUD operations.

Regression coverage: BrandCrud used to call generate_slug(db, name, "brand"),
but generate_slug only recognized "product"/"category" and raised
ValueError("Invalid slug context: brand") for anything else — so every
brand create/update crashed unconditionally.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def _make_admin(client: TestClient, db_session: Session) -> dict:
    client.post(
        "/users/register",
        json={
            "email": "admin_brands@example.com",
            "password": "Password1",
            "first_name": "Admin",
            "last_name": "User",
            "phone": "1234567892",
        },
    )
    stmt = select(User).where(User.email == "admin_brands@example.com")
    user = db_session.scalars(stmt).first()
    user.role = "admin"
    db_session.commit()
    login_res = client.post(
        "/users/login",
        json={"email": "admin_brands@example.com", "password": "Password1"},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_brand_as_admin(client: TestClient, db_session: Session):
    headers = _make_admin(client, db_session)
    resp = client.post("/brands", json={"name": "Acme Corp"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Corp"
    assert data["slug"] == "acme-corp"


def test_update_brand_name_regenerates_slug(client: TestClient, db_session: Session):
    headers = _make_admin(client, db_session)
    create_resp = client.post("/brands", json={"name": "Old Brand"}, headers=headers)
    brand_id = create_resp.json()["id"]

    update_resp = client.put(
        f"/brands/{brand_id}", json={"name": "New Brand"}, headers=headers
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["name"] == "New Brand"
    assert data["slug"] == "new-brand"


def test_create_brand_requires_admin(client: TestClient):
    resp = client.post("/brands", json={"name": "No Auth Brand"})
    assert resp.status_code == 401
