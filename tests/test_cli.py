"""Unit tests for the CLI: cli.requests.request is mocked, no server needed."""
from unittest.mock import MagicMock, patch

import pytest
import requests

import cli

ITEM = {
    "id": 1,
    "barcode": "3017620422003",
    "status": 1,
    "product": {
        "product_name": "Nutella", "brands": "Ferrero", "ingredients_text": "Sugar",
        "categories": "Spreads", "quantity": "400 g",
    },
    "price": 5.49,
    "stock": 40,
}


def fake_response(json_data, status=200):
    response = MagicMock()
    response.ok = status < 400
    response.status_code = status
    response.json.return_value = json_data
    return response


def test_list_prints_items(capsys):
    with patch("cli.requests.request", return_value=fake_response([ITEM])):
        assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Nutella" in out and "5.49" in out


def test_list_empty_inventory(capsys):
    with patch("cli.requests.request", return_value=fake_response([])):
        assert cli.main(["list"]) == 0
    assert "empty" in capsys.readouterr().out


def test_view_calls_correct_route(capsys):
    with patch("cli.requests.request", return_value=fake_response(ITEM)) as mock_req:
        assert cli.main(["view", "1"]) == 0
    assert mock_req.call_args[0][:2] == ("GET", f"{cli.API_URL}/inventory/1")
    assert "Ferrero" in capsys.readouterr().out


def test_view_missing_item_shows_api_error(capsys):
    with patch("cli.requests.request", return_value=fake_response({"error": "Item 9 not found"}, 404)):
        assert cli.main(["view", "9"]) == 1
    assert "Item 9 not found" in capsys.readouterr().err


def test_add_sends_expected_payload(capsys):
    with patch("cli.requests.request", return_value=fake_response(ITEM, 201)) as mock_req:
        code = cli.main(["add", "--name", "Nutella", "--price", "5.49", "--stock", "40"])
    assert code == 0
    assert mock_req.call_args[0][:2] == ("POST", f"{cli.API_URL}/inventory")
    assert mock_req.call_args[1]["json"] == {"product_name": "Nutella", "price": 5.49, "stock": 40}


def test_add_requires_name_or_barcode(capsys):
    with patch("cli.requests.request") as mock_req:
        assert cli.main(["add", "--price", "2"]) == 1
    mock_req.assert_not_called()
    assert "--name" in capsys.readouterr().err


def test_update_sends_patch(capsys):
    with patch("cli.requests.request", return_value=fake_response(ITEM)) as mock_req:
        assert cli.main(["update", "1", "--price", "6", "--stock", "3"]) == 0
    assert mock_req.call_args[0][0] == "PATCH"
    assert mock_req.call_args[1]["json"] == {"price": 6.0, "stock": 3}


def test_update_without_fields_is_error(capsys):
    with patch("cli.requests.request") as mock_req:
        assert cli.main(["update", "1"]) == 1
    mock_req.assert_not_called()


def test_delete_with_yes_flag(capsys):
    with patch("cli.requests.request", return_value=fake_response({"message": "Item 1 deleted"})) as mock_req:
        assert cli.main(["delete", "1", "--yes"]) == 0
    assert mock_req.call_args[0][0] == "DELETE"
    assert "deleted" in capsys.readouterr().out


def test_delete_cancelled_at_prompt(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with patch("cli.requests.request") as mock_req:
        assert cli.main(["delete", "1"]) == 0
    mock_req.assert_not_called()
    assert "Cancelled" in capsys.readouterr().out


def test_delete_confirmed_at_prompt(capsys, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    with patch("cli.requests.request", return_value=fake_response({"message": "Item 1 deleted"})) as mock_req:
        assert cli.main(["delete", "1"]) == 0
    mock_req.assert_called_once()


def test_search_by_barcode(capsys):
    result = {"status": 1, "barcode": "3017620422003", "product": ITEM["product"]}
    with patch("cli.requests.request", return_value=fake_response(result)) as mock_req:
        assert cli.main(["search", "--barcode", "3017620422003"]) == 0
    assert mock_req.call_args[1]["params"] == {"barcode": "3017620422003"}
    assert "Found on OpenFoodFacts" in capsys.readouterr().out


def test_search_by_name(capsys):
    result = {"status": 1, "barcode": "1", "product": ITEM["product"]}
    with patch("cli.requests.request", return_value=fake_response(result)) as mock_req:
        assert cli.main(["search", "--name", "nutella"]) == 0
    assert mock_req.call_args[1]["params"] == {"name": "nutella"}


# ---------- error handling ----------
def test_server_down_gives_friendly_message(capsys):
    with patch("cli.requests.request", side_effect=requests.ConnectionError()):
        assert cli.main(["list"]) == 1
    assert "Is the Flask server running" in capsys.readouterr().err


def test_timeout_gives_friendly_message(capsys):
    with patch("cli.requests.request", side_effect=requests.Timeout()):
        assert cli.main(["list"]) == 1
    assert "timed out" in capsys.readouterr().err


def test_api_502_is_reported(capsys):
    with patch("cli.requests.request", return_value=fake_response({"error": "OpenFoodFacts request failed"}, 502)):
        assert cli.main(["search", "--name", "x"]) == 1
    assert "OpenFoodFacts request failed" in capsys.readouterr().err


def test_non_json_error_response(capsys):
    response = MagicMock(ok=False, status_code=500)
    response.json.side_effect = ValueError()
    with patch("cli.requests.request", return_value=response):
        assert cli.main(["list"]) == 1
    assert "HTTP 500" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["view", "abc"],                      # id not a number
        ["view", "0"],                        # id must be >= 1
        ["add", "--name", "X", "--price", "-3"],   # negative price
        ["add", "--name", "X", "--stock", "2.5"],  # stock not whole
        ["add", "--barcode", "12ab"],         # barcode not digits
        ["search"],                           # needs --barcode or --name
        ["search", "--barcode", "1", "--name", "x"],  # mutually exclusive
        [],                                   # no command
    ],
)
def test_invalid_input_is_rejected_before_any_request(argv):
    with patch("cli.requests.request") as mock_req:
        with pytest.raises(SystemExit) as exc:
            cli.main(argv)
    assert exc.value.code == 2
    mock_req.assert_not_called()