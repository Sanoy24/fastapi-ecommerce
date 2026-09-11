"""
Regression test for the tax-rates double route prefix.

app/api/v1/routes/tax_rate.py declares `APIRouter(prefix="/admin/tax-rates")`
on itself — the same pattern app/api/v1/routes/shipping.py uses for its own
admin_router. init_routes.py mounted it with an *additional*
`prefix="/tax-rates"` on top, so every route in that file actually lived at
/tax-rates/admin/tax-rates/... instead of the intended /admin/tax-rates/...
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.routes import tax_rate as tax_rate_module
from app.models.user import User
from app.utils.security import hash_password


def _make_admin(db_session: Session, email: str = "taxroute_admin@test.com") -> None:
    db_session.add(
        User(
            email=email,
            password_hash=hash_password("TaxRouteAdmin1"),
            first_name="Admin",
            last_name="TaxRoute",
            phone="0911100001",
            is_verified=True,
            role="admin",
        )
    )
    db_session.commit()


def _login(client: TestClient, email: str, password: str) -> dict:
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestTaxRateRouterOwnPrefix:
    """The router's own declared paths, independent of how it gets
    mounted — checked directly against the router object."""

    def test_router_paths_are_not_doubled(self):
        paths = {r.path for r in tax_rate_module.router.routes}
        assert paths == {"/admin/tax-rates/", "/admin/tax-rates/{id}"}
        assert not any(p.startswith("/tax-rates/admin") for p in paths)


class TestTaxRatesAreReachableAtTheCorrectPath:
    def test_list_tax_rates_at_admin_tax_rates(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "taxroute1@test.com")
        admin = _login(client, "taxroute1@test.com", "TaxRouteAdmin1")

        resp = client.get("/admin/tax-rates/", headers=admin)

        assert resp.status_code == 200

    def test_create_tax_rate_at_admin_tax_rates(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "taxroute2@test.com")
        admin = _login(client, "taxroute2@test.com", "TaxRouteAdmin1")

        resp = client.post(
            "/admin/tax-rates/",
            json={"name": "Test Tax", "rate": 0.05, "applies_to": "all", "is_active": True},
            headers=admin,
        )

        assert resp.status_code == 201, resp.json()

    def test_old_double_prefixed_path_no_longer_exists(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "taxroute3@test.com")
        admin = _login(client, "taxroute3@test.com", "TaxRouteAdmin1")

        resp = client.get("/tax-rates/admin/tax-rates/", headers=admin)

        assert resp.status_code == 404
