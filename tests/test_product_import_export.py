"""
Tests for admin bulk product CSV import/export
(GET/POST /admin/products/export, /admin/products/import).

Import deliberately reuses ProductCrud.create_product/update_product — the
same methods the single-product API routes call — rather than writing a
parallel bulk-insert path, so slug/sku generation, price-history recording,
and price-drop notifications all keep working for a CSV-driven edit for
free. See app/utils/product_csv.py for the column set and
AdminService.import_products_csv for the per-row create-vs-update logic.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.price_history import PriceHistory
from app.models.product import Product
from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db_session: Session, email: str = "csv_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("CsvAdmin123"),
            first_name="Admin",
            last_name="Csv",
            phone="0966600001",
            is_verified=True,
            role="admin",
        )
    )
    db_session.commit()


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0966600002"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_product(db_session: Session, *, slug: str = "csv-widget", price: float = 20.0) -> Product:
    product = Product(
        name="CSV Widget",
        slug=slug,
        sku=f"SKU-{slug}",
        description="d",
        price=price,
        stock_quantity=10,
        image_url="http://test.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


def _upload(client: TestClient, csv_text: str, headers: dict):
    return client.post(
        "/admin/products/import",
        files={"file": ("products.csv", csv_text.encode("utf-8"), "text/csv")},
        headers=headers,
    )


class TestExportAccess:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        resp = client.get("/admin/products/export")
        assert resp.status_code == 401

    def test_rejects_non_admin(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "csv_cust1@test.com", "CsvCust123")
        resp = client.get("/admin/products/export", headers=customer)
        assert resp.status_code == 403


class TestExportContent:
    def test_exports_products_as_csv(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "csv_admin1@test.com")
        product = _make_product(db_session, slug="export-widget", price=15.0)
        admin = _login(client, "csv_admin1@test.com", "CsvAdmin123")

        resp = client.get("/admin/products/export", headers=admin)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "products.csv" in resp.headers["content-disposition"]
        lines = resp.text.strip().splitlines()
        assert lines[0] == "id,name,description,price,sale_price,compare_at_price,stock_quantity,sku,category_id,brand_id,status,image_url"
        assert any(str(product.id) in line and "CSV Widget" in line for line in lines[1:])


class TestImportAccess:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        resp = client.post(
            "/admin/products/import", files={"file": ("p.csv", b"name,price\nA,1\n", "text/csv")}
        )
        assert resp.status_code == 401

    def test_rejects_non_admin(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "csv_cust2@test.com", "CsvCust123")
        resp = _upload(client, "name,price\nA,1\n", customer)
        assert resp.status_code == 403


class TestImportCreates:
    def test_creates_a_new_product_from_a_row_without_an_id(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "csv_admin2@test.com")
        admin = _login(client, "csv_admin2@test.com", "CsvAdmin123")

        resp = _upload(client, "name,price,stock_quantity\nNew Import Widget,9.99,7\n", admin)

        assert resp.status_code == 200, resp.json()
        assert resp.json() == {"created_count": 1, "updated_count": 0, "failed_rows": []}

        db_session.expire_all()
        product = db_session.query(Product).filter_by(name="New Import Widget").first()
        assert product is not None
        assert float(product.price) == 9.99
        assert product.stock_quantity == 7
        assert product.sku  # auto-generated, same as the single-product create route

    def test_rejects_a_create_row_missing_name_or_price(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "csv_admin3@test.com")
        admin = _login(client, "csv_admin3@test.com", "CsvAdmin123")

        resp = _upload(client, "name,stock_quantity\nNo Price Widget,5\n", admin)

        assert resp.status_code == 200
        data = resp.json()
        assert data["created_count"] == 0
        assert len(data["failed_rows"]) == 1
        assert data["failed_rows"][0]["row_number"] == 2
        assert "required" in data["failed_rows"][0]["error"].lower()


class TestImportUpdates:
    def test_updates_an_existing_product_from_a_row_with_an_id(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "csv_admin4@test.com")
        product = _make_product(db_session, slug="update-widget", price=20.0)
        admin = _login(client, "csv_admin4@test.com", "CsvAdmin123")

        resp = _upload(client, f"id,price,stock_quantity\n{product.id},12.50,3\n", admin)

        assert resp.status_code == 200, resp.json()
        assert resp.json() == {"created_count": 0, "updated_count": 1, "failed_rows": []}

        db_session.expire_all()
        db_session.refresh(product)
        assert float(product.price) == 12.50
        assert product.stock_quantity == 3

    def test_updating_price_records_price_history_same_as_the_single_product_route(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "csv_admin5@test.com")
        product = _make_product(db_session, slug="history-widget", price=20.0)
        admin = _login(client, "csv_admin5@test.com", "CsvAdmin123")

        _upload(client, f"id,price\n{product.id},14.00\n", admin)

        db_session.expire_all()
        history = db_session.query(PriceHistory).filter_by(product_id=product.id).first()
        assert history is not None
        assert float(history.old_price) == 20.0
        assert float(history.new_price) == 14.0

    def test_reports_a_failed_row_for_a_nonexistent_product_id(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "csv_admin6@test.com")
        admin = _login(client, "csv_admin6@test.com", "CsvAdmin123")

        resp = _upload(client, "id,price\n999999,10.00\n", admin)

        assert resp.status_code == 200
        data = resp.json()
        assert data["updated_count"] == 0
        assert data["failed_rows"][0]["row_number"] == 2
        assert "not found" in data["failed_rows"][0]["error"].lower()


class TestImportRowIsolation:
    def test_one_bad_row_does_not_abort_the_rest_of_the_import(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "csv_admin7@test.com")
        admin = _login(client, "csv_admin7@test.com", "CsvAdmin123")

        csv_text = (
            "name,price\n"
            "Good Widget One,5.00\n"
            "Bad Widget,not-a-number\n"
            "Good Widget Two,6.00\n"
        )
        resp = _upload(client, csv_text, admin)

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["created_count"] == 2
        assert len(data["failed_rows"]) == 1
        assert data["failed_rows"][0]["row_number"] == 3
        assert "price" in data["failed_rows"][0]["error"].lower()

        db_session.expire_all()
        assert db_session.query(Product).filter_by(name="Good Widget One").first() is not None
        assert db_session.query(Product).filter_by(name="Good Widget Two").first() is not None

    def test_a_database_level_failure_on_one_row_does_not_abort_the_rest(
        self, client: TestClient, db_session: Session
    ):
        """Distinct from the parse-level failure above: this row parses
        fine but fails at insert time (FK violation on a nonexistent
        category_id), which is where ProductCrud.create_product converts
        IntegrityError into ProductException — the exception this loop
        must actually catch, not just a bad-input path caught earlier."""
        _make_admin(db_session, "csv_admin9@test.com")
        admin = _login(client, "csv_admin9@test.com", "CsvAdmin123")

        csv_text = (
            "name,price,category_id\n"
            "Before Bad Row,5.00,\n"
            "Bad FK Widget,6.00,999999\n"
            "After Bad Row,7.00,\n"
        )
        resp = _upload(client, csv_text, admin)

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["created_count"] == 2
        assert len(data["failed_rows"]) == 1
        assert data["failed_rows"][0]["row_number"] == 3

        db_session.expire_all()
        assert db_session.query(Product).filter_by(name="Before Bad Row").first() is not None
        assert db_session.query(Product).filter_by(name="After Bad Row").first() is not None
        assert db_session.query(Product).filter_by(name="Bad FK Widget").first() is None


class TestExportImportRoundTrip:
    def test_reimporting_an_unmodified_export_only_updates_never_creates(
        self, client: TestClient, db_session: Session
    ):
        _make_admin(db_session, "csv_admin8@test.com")
        _make_product(db_session, slug="roundtrip-widget", price=30.0)
        admin = _login(client, "csv_admin8@test.com", "CsvAdmin123")

        exported = client.get("/admin/products/export", headers=admin).text
        resp = _upload(client, exported, admin)

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["created_count"] == 0
        assert data["failed_rows"] == []
        assert data["updated_count"] >= 1
