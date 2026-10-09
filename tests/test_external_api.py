from unittest.mock import MagicMock, patch

import pytest
import requests

import app as inventory_app


def fake_response(data, status=200):
    """Build a pretend response so no real internet call is made."""
    response = MagicMock()
    response.status_code = status
    response.json.return_value = data
    return response


def test_find_by_barcode():
    data = {"status": 1, "product": {"product_name": "Nutella", "brands": "Ferrero", "ingredients_text": "Sugar"}}
    with patch("app.requests.get", return_value=fake_response(data)) as mock_get:
        result = inventory_app.fetch_product(barcode="3017620422003")
    assert result["barcode"] == "3017620422003"
    assert result["product"]["product_name"] == "Nutella"
    assert "3017620422003.json" in mock_get.call_args[0][0]


def test_barcode_not_found_status_zero():
    with patch("app.requests.get", return_value=fake_response({"status": 0})):
        assert inventory_app.fetch_product(barcode="0000") is None


def test_barcode_not_found_http_404():
    with patch("app.requests.get", return_value=fake_response({}, status=404)):
        assert inventory_app.fetch_product(barcode="0000") is None


def test_find_by_name():
    data = {"products": [{"code": "42", "product_name": "Almond Milk", "brands": "Silk"}]}
    with patch("app.requests.get", return_value=fake_response(data)) as mock_get:
        result = inventory_app.fetch_product(name="almond milk")
    assert result["barcode"] == "42"
    assert result["product"]["brands"] == "Silk"
    assert result["product"]["ingredients_text"] == ""  # missing fields become ""
    assert mock_get.call_args[1]["params"]["search_terms"] == "almond milk"


def test_name_with_no_results():
    with patch("app.requests.get", return_value=fake_response({"products": []})):
        assert inventory_app.fetch_product(name="zzzz") is None


def test_user_agent_is_sent():
    with patch("app.requests.get", return_value=fake_response({"status": 0})) as mock_get:
        inventory_app.fetch_product(barcode="123")
    assert "User-Agent" in mock_get.call_args[1]["headers"]


def test_network_error_is_raised():
    with patch("app.requests.get", side_effect=requests.ConnectionError()):
        with pytest.raises(requests.RequestException):
            inventory_app.fetch_product(barcode="123")


def test_http_error_is_raised():
    response = fake_response({}, status=500)
    response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    with patch("app.requests.get", return_value=response):
        with pytest.raises(requests.RequestException):
            inventory_app.fetch_product(barcode="123")