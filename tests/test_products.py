from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.user import User


def test_create_product_as_admin(client: TestClient, db_session: Session):
    # 1. Register a user
    register_payload = {
        "email": "admin@example.com",
        "password": "Password1",
        "first_name": "Admin",
        "last_name": "User",
        "phone": "1234567890",
    }
    client.post("/users/register", json=register_payload)

    # 2. Promote to admin
    stmt = select(User).where(User.email == "admin@example.com")
    user = db_session.scalars(stmt).first()
    user.role = "admin"
    db_session.commit()

    # 3. Login
    login_payload = {
        "email": "admin@example.com",
        "password": "Password1",
    }
    login_res = client.post("/users/login", json=login_payload)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Create Product
    product_payload = {
        "name": "Test Product",
        "description": "A test product",
        "price": 99.99,
        "stock_quantity": 10,
        "image_url": "https://example.com/image.jpg"
    }
    response = client.post("/product", json=product_payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == product_payload["name"]
    assert data["price"] == product_payload["price"]


def _make_admin(client: TestClient, db_session: Session) -> dict:
    client.post(
        "/users/register",
        json={
            "email": "admin_products@example.com",
            "password": "Password1",
            "first_name": "Admin",
            "last_name": "User",
            "phone": "1234567891",
        },
    )
    stmt = select(User).where(User.email == "admin_products@example.com")
    user = db_session.scalars(stmt).first()
    user.role = "admin"
    db_session.commit()
    login_res = client.post(
        "/users/login",
        json={"email": "admin_products@example.com", "password": "Password1"},
    )
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_update_product_name_regenerates_slug(client: TestClient, db_session: Session):
    """
    Regression test: updating a product's name without also supplying a slug
    used to call generate_slug() with a missing required "context" argument,
    raising a TypeError on every such update.
    """
    headers = _make_admin(client, db_session)
    create_resp = client.post(
        "/product",
        json={"name": "Original Name", "price": 10.0, "stock_quantity": 5},
        headers=headers,
    )
    product_id = create_resp.json()["id"]

    update_resp = client.put(
        f"/product/{product_id}",
        json={"name": "Updated Name"},
        headers=headers,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["name"] == "Updated Name"
    assert data["slug"].startswith("updated-name")


def test_get_products(client: TestClient):
    response = client.get("/product")
    assert response.status_code == 200
    data = response.json()

    # Validate PaginatedResponse structure
    assert isinstance(data, dict)
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)

    # Validate pagination metadata
    meta = data["meta"]
    assert "current_page" in meta
    assert "per_page" in meta
    assert "total_pages" in meta
    assert "total_items" in meta
    assert meta["current_page"] == 1
    assert meta["per_page"] == 10


def _make_brand(client: TestClient, headers: dict, name: str) -> int:
    resp = client.post("/brands", json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.json()
    return resp.json()["id"]


def test_filtering_by_brand_returns_only_that_brands_products(
    client: TestClient, db_session: Session
):
    """Regression target: GET /product filtered by category/price/rating/
    availability but had no brand filter at all, despite Product.brand_id
    existing — essential for a general-merchandise catalog where brand is
    often the deciding filter (electronics especially)."""
    headers = _make_admin(client, db_session)
    brand_a = _make_brand(client, headers, "Acme")
    brand_b = _make_brand(client, headers, "Zenith")

    client.post(
        "/product",
        json={"name": "Acme Widget", "price": 10.0, "stock_quantity": 5, "brand_id": brand_a, "status": "active"},
        headers=headers,
    )
    client.post(
        "/product",
        json={"name": "Zenith Gadget", "price": 20.0, "stock_quantity": 5, "brand_id": brand_b, "status": "active"},
        headers=headers,
    )

    resp = client.get(f"/product?brand_id={brand_a}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Acme Widget"


def test_brand_filter_survives_pagination_links(client: TestClient, db_session: Session):
    """Regression target: get_all_products() builds each pagination link's
    query string from a second, separately-maintained list of params — a
    filter added only to the WHERE clause and not to that list silently
    disappears from page 2 onward while page 1's results still look correct."""
    headers = _make_admin(client, db_session)
    brand_id = _make_brand(client, headers, "Consistent Brand")

    for i in range(3):
        client.post(
            "/product",
            json={
                "name": f"Consistent Product {i}", "price": 10.0, "stock_quantity": 5,
                "brand_id": brand_id, "status": "active",
            },
            headers=headers,
        )

    resp = client.get(f"/product?brand_id={brand_id}&per_page=2")
    assert resp.status_code == 200
    links = resp.json()["links"]
    assert f"brand_id={brand_id}" in links["next"]


def test_product_attributes_round_trip_through_create_and_fetch(
    client: TestClient, db_session: Session
):
    """Product had no equivalent to ProductVariant.attributes — a laptop's
    RAM/screen size or a shirt's material/care had nowhere to live except
    free-text description. attributes is a plain JSON passthrough, so this
    just confirms it round-trips rather than being silently dropped."""
    headers = _make_admin(client, db_session)
    specs = {"ram_gb": 16, "screen_in": 14.0, "color": "Silver"}

    create_resp = client.post(
        "/product",
        json={"name": "Ultrabook 14", "price": 1200.0, "stock_quantity": 3, "attributes": specs},
        headers=headers,
    )
    assert create_resp.status_code == 201, create_resp.json()
    assert create_resp.json()["attributes"] == specs

    product_id = create_resp.json()["id"]
    fetch_resp = client.get(f"/product/id/{product_id}", headers=headers)
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["attributes"] == specs
