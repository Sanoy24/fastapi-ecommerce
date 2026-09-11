"""
Regression tests for POST /elastic/search no longer accepting a raw
Elasticsearch query body.

Previously the route was `search(query: dict = Body(...))`, forwarded
verbatim to Elasticsearch with no auth, no schema, and no field allowlist —
anyone could submit expensive aggregations, deep pagination, wildcard/regex/
fuzzy bombs, or script-bearing queries directly against the cluster. It now
takes a typed ProductElasticSearchRequest and the service builds a bounded
query server-side (ElasticService._build_product_query).

Tests that would reach a real Elasticsearch call are avoided here — there's
no ES available in this environment and the unreachable-host path takes
15+ seconds per call (connection retries) — so these test request
validation and query construction directly instead of the live network path.
"""
from fastapi.testclient import TestClient

from app.schema.search_schema import ProductElasticSearchRequest
from app.services.elasticsearch_service import ElasticService


class TestSearchRequestValidation:
    def test_legacy_raw_dsl_body_is_rejected(self, client: TestClient):
        """The old attack shape — a raw ES query body — no longer validates."""
        resp = client.post("/elastic/search", json={"query": {"match_all": {}}})
        assert resp.status_code == 422
        assert resp.json()["fields"].get("q") == "Field required"

    def test_script_field_is_rejected(self, client: TestClient):
        """Unknown fields (e.g. a smuggled 'script' clause) are rejected outright."""
        resp = client.post(
            "/elastic/search",
            json={"q": "phone", "script": {"source": "1==1"}},
        )
        assert resp.status_code == 422

    def test_valid_request_shape_is_accepted(self, client: TestClient):
        params = ProductElasticSearchRequest(q="phone")
        assert params.q == "phone"
        assert params.size == 20
        assert params.offset == 0

    def test_size_over_100_is_rejected(self, client: TestClient):
        resp = client.post("/elastic/search", json={"q": "phone", "size": 500})
        assert resp.status_code == 422

    def test_negative_offset_is_rejected(self, client: TestClient):
        resp = client.post("/elastic/search", json={"q": "phone", "offset": -1})
        assert resp.status_code == 422


class TestBuiltQueryIsBounded:
    """Unit-level: the DSL sent to Elasticsearch is always built server-side
    from validated fields, never influenced by arbitrary client input."""

    def test_query_contains_only_expected_clauses(self):
        params = ProductElasticSearchRequest(
            q="phone", category="Electronics", min_price=10, max_price=500, in_stock_only=True
        )
        query = ElasticService._build_product_query(params)

        assert set(query.keys()) == {"query"}
        bool_query = query["query"]["bool"]
        assert bool_query["must"] == [
            {
                "multi_match": {
                    "query": "phone",
                    "fields": ["name^3", "name.english^2", "description"],
                    "fuzziness": "AUTO",
                }
            }
        ]
        assert {"term": {"category": "Electronics"}} in bool_query["filter"]
        assert {"range": {"price": {"gte": 10, "lte": 500}}} in bool_query["filter"]
        assert {"term": {"in_stock": True}} in bool_query["filter"]

    def test_minimal_query_has_no_filters(self):
        params = ProductElasticSearchRequest(q="phone")
        query = ElasticService._build_product_query(params)
        assert query["query"]["bool"]["filter"] == []

    def test_search_products_forwards_size_and_offset(self, monkeypatch):
        import asyncio

        captured = {}

        async def fake_search(self, query, index="products", size=20, from_=0, highlight=True):
            captured["query"] = query
            captured["size"] = size
            captured["from_"] = from_
            return {"total": {"value": 0}, "results": []}

        monkeypatch.setattr(ElasticService, "search", fake_search)

        service = ElasticService(es=None)
        params = ProductElasticSearchRequest(q="phone", size=5, offset=15)
        asyncio.run(service.search_products(params))

        assert captured["size"] == 5
        assert captured["from_"] == 15
        assert captured["query"] == ElasticService._build_product_query(params)
