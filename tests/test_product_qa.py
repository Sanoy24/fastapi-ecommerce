"""
Tests for product Q&A: any signed-in user can ask a question on a product
(deliberately not gated on having purchased it, unlike Review — the point
is helping someone decide whether to buy) and any signed-in user can
answer, crowd-sourced like Amazon's customer Q&A rather than an
admin-only FAQ.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product import Product


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    client.post(
        "/users/register",
        json={"email": email, "password": password, "first_name": "Test", "last_name": "User", "phone": "0955500001"},
    )
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _make_admin(db_session: Session, email: str = "qa_admin@test.com") -> None:
    from app.models.user import User
    from app.utils.security import hash_password

    db_session.add(
        User(
            email=email,
            password_hash=hash_password("QaAdmin123"),
            first_name="Admin",
            last_name="Qa",
            phone="0955500002",
            is_verified=True,
            role="admin",
        )
    )
    db_session.commit()


def _make_product(db_session: Session, *, slug: str = "qa-widget") -> Product:
    product = Product(
        name="QA Widget",
        slug=slug,
        sku=f"SKU-{slug}",
        description="d",
        price=20.0,
        stock_quantity=10,
        image_url="http://test.com/img.jpg",
    )
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    return product


class TestAskQuestion:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="auth-widget")
        resp = client.post("/questions", json={"product_id": product.id, "question": "Does this fit a size 10?"})
        assert resp.status_code == 401

    def test_rejects_nonexistent_product(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "qa_cust1@test.com", "QaCust123")
        resp = client.post(
            "/questions", json={"product_id": 999999, "question": "Does this fit a size 10?"}, headers=customer
        )
        assert resp.status_code == 404

    def test_rejects_a_too_short_question(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="short-widget")
        customer = _register_and_login(client, "qa_cust2@test.com", "QaCust123")
        resp = client.post("/questions", json={"product_id": product.id, "question": "hi"}, headers=customer)
        assert resp.status_code == 422

    def test_does_not_require_a_purchase(self, client: TestClient, db_session: Session):
        """Unlike reviews, asking a question has no purchase requirement —
        someone browsing the product page should be able to ask before
        buying."""
        product = _make_product(db_session, slug="no-purchase-widget")
        customer = _register_and_login(client, "qa_cust3@test.com", "QaCust123")

        resp = client.post(
            "/questions", json={"product_id": product.id, "question": "Does this come in blue?"}, headers=customer
        )

        assert resp.status_code == 201, resp.json()
        data = resp.json()
        assert data["product_id"] == product.id
        assert data["question"] == "Does this come in blue?"
        assert data["answers"] == []


class TestListAndGetQuestions:
    def test_lists_questions_for_a_product_newest_first(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="list-widget")
        customer = _register_and_login(client, "qa_cust4@test.com", "QaCust123")

        first = client.post(
            "/questions", json={"product_id": product.id, "question": "First question here?"}, headers=customer
        ).json()
        second = client.post(
            "/questions", json={"product_id": product.id, "question": "Second question here?"}, headers=customer
        ).json()

        resp = client.get(f"/questions/product/{product.id}")
        assert resp.status_code == 200
        ids = [q["id"] for q in resp.json()]
        assert ids == [second["id"], first["id"]]

    def test_get_single_question_includes_its_answers(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="single-widget")
        customer = _register_and_login(client, "qa_cust5@test.com", "QaCust123")
        answerer = _register_and_login(client, "qa_answerer1@test.com", "QaAns1234")

        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Is this waterproof?"}, headers=customer
        ).json()["id"]
        client.post(f"/questions/{question_id}/answers", json={"answer": "Yes, IP67 rated."}, headers=answerer)

        resp = client.get(f"/questions/{question_id}")
        assert resp.status_code == 200
        assert len(resp.json()["answers"]) == 1
        assert resp.json()["answers"][0]["answer"] == "Yes, IP67 rated."

    def test_get_nonexistent_question_404s(self, client: TestClient, db_session: Session):
        resp = client.get("/questions/999999")
        assert resp.status_code == 404


class TestAnswerQuestion:
    def test_requires_authentication(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="ans-auth-widget")
        customer = _register_and_login(client, "qa_cust6@test.com", "QaCust123")
        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Any warranty on this?"}, headers=customer
        ).json()["id"]

        resp = client.post(f"/questions/{question_id}/answers", json={"answer": "One year."})
        assert resp.status_code == 401

    def test_rejects_answering_a_nonexistent_question(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "qa_cust7@test.com", "QaCust123")
        resp = client.post("/questions/999999/answers", json={"answer": "One year."}, headers=customer)
        assert resp.status_code == 404

    def test_any_signed_in_user_can_answer_not_just_an_admin(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="crowd-widget")
        asker = _register_and_login(client, "qa_asker1@test.com", "QaAsk1234")
        answerer = _register_and_login(client, "qa_answerer2@test.com", "QaAns1234")

        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Does it come with a charger?"}, headers=asker
        ).json()["id"]

        resp = client.post(f"/questions/{question_id}/answers", json={"answer": "Yes, USB-C included."}, headers=answerer)

        assert resp.status_code == 201, resp.json()
        assert resp.json()["question_id"] == question_id


class TestDeleteQuestion:
    def test_owner_can_delete_their_question(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="del-own-widget")
        customer = _register_and_login(client, "qa_cust8@test.com", "QaCust123")
        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Is this dishwasher safe?"}, headers=customer
        ).json()["id"]

        resp = client.delete(f"/questions/{question_id}", headers=customer)

        assert resp.status_code == 204
        assert client.get(f"/questions/{question_id}").status_code == 404

    def test_non_owner_cannot_delete_someone_elses_question(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="del-other-widget")
        owner = _register_and_login(client, "qa_owner1@test.com", "QaOwner12")
        attacker = _register_and_login(client, "qa_attacker1@test.com", "QaAttack1")
        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Does it float in water?"}, headers=owner
        ).json()["id"]

        resp = client.delete(f"/questions/{question_id}", headers=attacker)

        assert resp.status_code == 403
        assert client.get(f"/questions/{question_id}").status_code == 200

    def test_admin_can_delete_anyones_question(self, client: TestClient, db_session: Session):
        _make_admin(db_session, "qa_admin1@test.com")
        product = _make_product(db_session, slug="del-admin-widget")
        owner = _register_and_login(client, "qa_owner2@test.com", "QaOwner12")
        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Is a manual included?"}, headers=owner
        ).json()["id"]

        admin = _register_and_login(client, "qa_admin1@test.com", "QaAdmin123")
        resp = client.delete(f"/questions/{question_id}", headers=admin)

        assert resp.status_code == 204

    def test_deleting_a_question_deletes_its_answers(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="cascade-widget")
        asker = _register_and_login(client, "qa_asker2@test.com", "QaAsk1234")
        answerer = _register_and_login(client, "qa_answerer3@test.com", "QaAns1234")
        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Does it need batteries?"}, headers=asker
        ).json()["id"]
        answer_id = client.post(
            f"/questions/{question_id}/answers", json={"answer": "Yes, 2 AA batteries."}, headers=answerer
        ).json()["id"]

        client.delete(f"/questions/{question_id}", headers=asker)

        db_session.expire_all()
        from app.models.product_answer import ProductAnswer
        assert db_session.get(ProductAnswer, answer_id) is None


class TestDeleteAnswer:
    def test_owner_can_delete_their_answer(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="del-ans-widget")
        asker = _register_and_login(client, "qa_asker3@test.com", "QaAsk1234")
        answerer = _register_and_login(client, "qa_answerer4@test.com", "QaAns1234")
        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Any color options?"}, headers=asker
        ).json()["id"]
        answer_id = client.post(
            f"/questions/{question_id}/answers", json={"answer": "Black and white."}, headers=answerer
        ).json()["id"]

        resp = client.delete(f"/questions/answers/{answer_id}", headers=answerer)

        assert resp.status_code == 204
        assert client.get(f"/questions/{question_id}").json()["answers"] == []

    def test_non_owner_cannot_delete_someone_elses_answer(self, client: TestClient, db_session: Session):
        product = _make_product(db_session, slug="del-ans-other-widget")
        asker = _register_and_login(client, "qa_asker4@test.com", "QaAsk1234")
        answerer = _register_and_login(client, "qa_answerer5@test.com", "QaAns1234")
        attacker = _register_and_login(client, "qa_attacker2@test.com", "QaAttack1")
        question_id = client.post(
            "/questions", json={"product_id": product.id, "question": "Is it machine washable?"}, headers=asker
        ).json()["id"]
        answer_id = client.post(
            f"/questions/{question_id}/answers", json={"answer": "Hand wash only."}, headers=answerer
        ).json()["id"]

        resp = client.delete(f"/questions/answers/{answer_id}", headers=attacker)

        assert resp.status_code == 403

    def test_rejects_deleting_a_nonexistent_answer(self, client: TestClient, db_session: Session):
        customer = _register_and_login(client, "qa_cust9@test.com", "QaCust123")
        resp = client.delete("/questions/answers/999999", headers=customer)
        assert resp.status_code == 404
