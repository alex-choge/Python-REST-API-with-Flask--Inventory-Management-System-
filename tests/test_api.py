"""Unit tests for the Flask CRUD endpoints (external API is always mocked)."""
from unittest.mock import patch

import app as inventory_app


# ---------- GET ----------
def test_get_all_items(client):
    response = client.get("/inventory")
    assert response.status_code == 200
    assert len(response.get_json()) == 5


def test_get_single_item(client):
    response = client.get("/inventory/3")
    assert response.status_code == 200
    assert response.get_json()["product"]["product_name"] == "Organic Almond Milk"


def test_get_missing_item_returns_404(client):
    response = client.get("/inventory/999")
    assert response.status_code == 404
    assert "error" in response.get_json()


# ---------- POST ----------
def test_create_item_with_name(client):
    response = client.post(
        "/inventory", json={"product_name": "Rice 1kg", "price": 2.5, "stock": 10}
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] == 6
    assert body["product"]["product_name"] == "Rice 1kg"
    assert len(client.get("/inventory").get_json()) == 6


def test_create_item_requires_name_or_barcode(client):
    response = client.post("/inventory", json={"price": 1})
    assert response.status_code == 400


def test_create_item_rejects_bad_price_and_stock(client):
    assert client.post("/inventory", json={"product_name": "X", "price": -1}).status_code == 400
    assert client.post("/inventory", json={"product_name": "X", "price": "free"}).status_code == 400
    assert client.post("/inventory", json={"product_name": "X", "stock": 1.5}).status_code == 400
    assert client.post("/inventory", json={"product_name": "X", "stock": True}).status_code == 400


def test_create_item_rejects_non_json_body(client):
    response = client.post("/inventory", data="not json", content_type="text/plain")
    assert response.status_code == 400


def test_create_item_rejects_non_digit_barcode(client):
    response = client.post("/inventory", json={"barcode": "abc123"})
    assert response.status_code == 400


def test_create_item_enriched_from_api(client):
    fake = {"barcode": "123456", "product": {
        "product_name": "Fake Juice", "brands": "FakeCo", "ingredients_text": "Water",
        "categories": "Drinks", "quantity": "1 L"}}
    with patch("app.fetch_product", return_value=fake):
        response = client.post("/inventory", json={"barcode": "123456", "price": 2, "stock": 5})
    assert response.status_code == 201
    assert response.get_json()["product"]["brands"] == "FakeCo"


def test_client_values_win_over_api_values(client):
    fake = {"barcode": "123456", "product": {
        "product_name": "API Name", "brands": "FakeCo", "ingredients_text": "",
        "categories": "", "quantity": ""}}
    with patch("app.fetch_product", return_value=fake):
        response = client.post("/inventory", json={"barcode": "123456", "product_name": "My Name"})
    body = response.get_json()
    assert body["product"]["product_name"] == "My Name"
    assert body["product"]["brands"] == "FakeCo"


def test_create_with_barcode_not_found_and_no_name_returns_404(client):
    with patch("app.fetch_product", return_value=None):
        response = client.post("/inventory", json={"barcode": "000"})
    assert response.status_code == 404


def test_create_with_api_down_and_no_name_returns_502(client):
    with patch("app.fetch_product", side_effect=inventory_app.ExternalAPIError("down")):
        response = client.post("/inventory", json={"barcode": "123"})
    assert response.status_code == 502


def test_create_with_api_down_but_name_still_succeeds(client):
    with patch("app.fetch_product", side_effect=inventory_app.ExternalAPIError("down")):
        response = client.post("/inventory", json={"barcode": "123", "product_name": "Manual Item"})
    assert response.status_code == 201


def test_new_id_is_highest_id_plus_one(client):
    client.delete("/inventory/2")  # the highest id (5) is still there
    response = client.post("/inventory", json={"product_name": "New"})
    assert response.get_json()["id"] == 6


# ---------- PATCH ----------
def test_update_price_and_stock(client):
    response = client.patch("/inventory/1", json={"price": 9.99, "stock": 7})
    assert response.status_code == 200
    body = response.get_json()
    assert body["price"] == 9.99 and body["stock"] == 7
    # The change must persist in storage.
    assert client.get("/inventory/1").get_json()["price"] == 9.99


def test_update_product_name(client):
    response = client.patch("/inventory/1", json={"product_name": "Nutella Big"})
    assert response.get_json()["product"]["product_name"] == "Nutella Big"


def test_update_missing_item_returns_404(client):
    assert client.patch("/inventory/999", json={"price": 1}).status_code == 404


def test_update_rejects_unknown_field_and_empty_body(client):
    assert client.patch("/inventory/1", json={"id": 50}).status_code == 400
    assert client.patch("/inventory/1", json={}).status_code == 400


def test_update_is_all_or_nothing(client):
    # Valid price + invalid stock: the price must NOT be applied.
    response = client.patch("/inventory/1", json={"price": 99, "stock": -5})
    assert response.status_code == 400
    assert client.get("/inventory/1").get_json()["price"] == 5.49


def test_update_rejects_empty_product_name(client):
    assert client.patch("/inventory/1", json={"product_name": "  "}).status_code == 400


# ---------- DELETE ----------
def test_delete_item(client):
    response = client.delete("/inventory/2")
    assert response.status_code == 200
    assert client.get("/inventory/2").status_code == 404
    assert len(client.get("/inventory").get_json()) == 4


def test_delete_missing_item_returns_404(client):
    assert client.delete("/inventory/999").status_code == 404


# ---------- /external/product route ----------
def test_external_route_requires_param(client):
    assert client.get("/external/product").status_code == 400


def test_external_route_success(client):
    fake = {"barcode": "1", "product": {"product_name": "Thing"}}
    with patch("app.fetch_product", return_value=fake):
        response = client.get("/external/product?name=thing")
    assert response.status_code == 200
    assert response.get_json()["product"]["product_name"] == "Thing"


def test_external_route_not_found_and_failure(client):
    with patch("app.fetch_product", return_value=None):
        assert client.get("/external/product?barcode=123").status_code == 404
    with patch("app.fetch_product", side_effect=inventory_app.ExternalAPIError("boom")):
        assert client.get("/external/product?barcode=123").status_code == 502