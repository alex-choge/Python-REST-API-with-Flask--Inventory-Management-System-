"""Unit tests for fetch_product(): requests.get is mocked, no real network calls."""
from unittest.mock import MagicMock, patch

import pytest
import requests

import app as inventory_app


def make_response(json_data=None, status_error=None, json_error=None):
    """Build a fake requests.Response."""
    response = MagicMock()
    if status_error:
        response.raise_for_status.side_effect = status_error
    if json_error:
        response.json.side_effect = json_error
    else:
        response.json.return_value = json_data
    return response


BARCODE_PAYLOAD = {
    "status": 1,
    "code": "3017620422003",
    "product": {
        "product_name": "Nutella",
        "brands": "Ferrero",
        "ingredients_text": "Sugar, palm oil",
        "categories": "Spreads",
        "quantity": "400 g",
        "extra_field_we_ignore": "x",
    },
}


def test_fetch_by_barcode_success():
    with patch("app.requests.get", return_value=make_response(BARCODE_PAYLOAD)) as mock_get:
        result = inventory_app.fetch_product(barcode="3017620422003")
    assert result["barcode"] == "3017620422003"
    assert result["product"]["product_name"] == "Nutella"
    assert "extra_field_we_ignore" not in result["product"]
    called_url = mock_get.call_args[0][0]
    assert called_url.endswith("/api/v2/product/3017620422003.json")


def test_fetch_by_barcode_not_found_returns_none():
    with patch("app.requests.get", return_value=make_response({"status": 0})):
        assert inventory_app.fetch_product(barcode="0000") is None


def test_fetch_by_name_uses_first_result():
    payload = {"products": [{"code": "42", "product_name": "Almond Milk", "brands": "Silk"}]}
    with patch("app.requests.get", return_value=make_response(payload)) as mock_get:
        result = inventory_app.fetch_product(name="almond milk")
    assert result["barcode"] == "42"
    assert result["product"]["brands"] == "Silk"
    assert result["product"]["ingredients_text"] == ""  # missing fields become ""
    assert mock_get.call_args[1]["params"]["search_terms"] == "almond milk"


def test_fetch_by_name_no_results_returns_none():
    with patch("app.requests.get", return_value=make_response({"products": []})):
        assert inventory_app.fetch_product(name="zzzz") is None


def test_fetch_with_no_arguments_returns_none():
    assert inventory_app.fetch_product() is None


@pytest.mark.parametrize(
    "side_effect",
    [requests.ConnectionError("no network"), requests.Timeout("slow"), requests.RequestException("odd")],
)
def test_fetch_converts_network_errors(side_effect):
    with patch("app.requests.get", side_effect=side_effect):
        with pytest.raises(inventory_app.ExternalAPIError):
            inventory_app.fetch_product(barcode="123")


def test_fetch_converts_http_errors():
    resp = make_response(status_error=requests.HTTPError("500 Server Error"))
    with patch("app.requests.get", return_value=resp):
        with pytest.raises(inventory_app.ExternalAPIError):
            inventory_app.fetch_product(barcode="123")


def test_fetch_converts_invalid_json():
    resp = make_response(json_error=ValueError("bad json"))
    with patch("app.requests.get", return_value=resp):
        with pytest.raises(inventory_app.ExternalAPIError):
            inventory_app.fetch_product(barcode="123")


def test_user_agent_header_is_sent():
    with patch("app.requests.get", return_value=make_response(BARCODE_PAYLOAD)) as mock_get:
        inventory_app.fetch_product(barcode="3017620422003")
    assert "InventoryManagementLab/" in mock_get.call_args[1]["headers"]["User-Agent"]


@pytest.mark.parametrize("status_code", [429, 503])
def test_rate_limit_gives_clear_error(status_code):
    resp = make_response({})
    resp.status_code = status_code
    with patch("app.requests.get", return_value=resp):
        with pytest.raises(inventory_app.ExternalAPIError, match="rate limit"):
            inventory_app.fetch_product(barcode="123")