# Inventory Management System - Flask REST API

A small Flask project: a REST API for managing retail inventory, a CLI to use it,
and OpenFoodFacts integration to fill in product details.

Built on the same blueprint as the help_desk_system learning project. The data lives in a
**Python list of dictionaries** (no database), and finding an item by id uses a linear search (`find_item()`, O(n)).

## 1. What the app does

- add, view, update and delete inventory items through a REST API
- look products up on [OpenFoodFacts](https://world.openfoodfacts.org) by barcode or name
- fill in missing product details (brand, ingredients, categories) automatically when you add an item by barcode
- use everything from the command line through `cli.py`

## 2. Project structure

```
inventory_system/
|
|-- app.py              # Flask API + OpenFoodFacts lookup
|-- cli.py              # command-line interface
|-- requirements.txt
|-- README.md
|-- .gitignore
|
`-- tests/
    |-- conftest.py         # fixtures (fresh data for every test)
    |-- test_api.py         # GET / POST / PATCH / DELETE endpoints
    |-- test_external_api.py# OpenFoodFacts function (mocked)
    `-- test_cli.py         # CLI commands (mocked)
```

## 3. Setup

```
python -m venv venv
```

Windows: `venv\Scripts\activate`  |  macOS/Linux: `source venv/bin/activate`

```
pip install -r requirements.txt
python app.py
```

The API runs at `http://127.0.0.1:5000` (Flask Debug Mode is on). Keep this terminal open and use a second terminal for the CLI.

## 4. API endpoints

| Purpose              | Method | Route                  | Success | Errors        |
| -------------------- | ------ | ---------------------- | ------- | ------------- |
| Read all items       | GET    | `/inventory`           | 200     |               |
| Read one item        | GET    | `/inventory/<id>`      | 200     | 404           |
| Create item          | POST   | `/inventory`           | 201     | 400, 404, 502 |
| Update item          | PATCH  | `/inventory/<id>`      | 200     | 400, 404      |
| Delete item          | DELETE | `/inventory/<id>`      | 200     | 404           |
| Search OpenFoodFacts | GET    | `/external/product`    | 200     | 400, 404, 502 |

### Item JSON

```json
{
  "id": 3,
  "barcode": "0025293000316",
  "status": 1,
  "product": {
    "product_name": "Organic Almond Milk",
    "brands": "Silk",
    "ingredients_text": "Filtered water, almonds, cane sugar, sea salt, sunflower lecithin",
    "categories": "Beverages, Plant-based milks",
    "quantity": "1 L"
  },
  "price": 3.99,
  "stock": 25
}
```

### POST /inventory

Send `product_name` and/or `barcode` (at least one). `price` and `stock` are optional and default to 0.
If you send a barcode, any blank product details are filled from OpenFoodFacts. Values you send always win over API values.

```json
{ "barcode": "3017620422003", "price": 5.49, "stock": 40 }
```

### PATCH /inventory/<id>

Allowed fields: `price`, `stock`, `product_name`, `brands`, `ingredients_text`, `categories`, `quantity`.
The request is all-or-nothing: if one field is invalid, nothing is changed.

```json
{ "price": 4.25, "stock": 18 }
```

### GET /external/product

Use `?barcode=3017620422003` or `?name=almond milk`. This only reads from OpenFoodFacts; it does not change the inventory.

### Error format

Every error is JSON: `{"error": "message"}`.
`400` bad input, `404` not found, `502` OpenFoodFacts unreachable or failing.

### Trying it in Postman / curl

```
curl http://127.0.0.1:5000/inventory
curl -X POST http://127.0.0.1:5000/inventory -H "Content-Type: application/json" -d '{"product_name":"Rice 1kg","price":2.5,"stock":10}'
curl -X PATCH http://127.0.0.1:5000/inventory/1 -H "Content-Type: application/json" -d '{"stock":7}'
curl -X DELETE http://127.0.0.1:5000/inventory/1
```

## 5. CLI usage

Start the API first (`python app.py`), then in another terminal:

```
python cli.py list
python cli.py view 3
python cli.py add --name "Rice 1kg" --price 2.50 --stock 10
python cli.py add --barcode 3017620422003 --price 5.49 --stock 40
python cli.py update 3 --price 4.25 --stock 18
python cli.py delete 3          # asks for confirmation
python cli.py delete 3 --yes    # skips the confirmation
python cli.py search --barcode 3017620422003
python cli.py search --name "almond milk"
python cli.py --help
```

| Command  | Calls                  | When you use it                                  |
| -------- | ---------------------- | ------------------------------------------------ |
| `list`   | GET /inventory         | see everything in stock                          |
| `view`   | GET /inventory/<id>    | see full details of one item                     |
| `add`    | POST /inventory        | receive a new product                            |
| `update` | PATCH /inventory/<id>  | change a price or stock level                    |
| `delete` | DELETE /inventory/<id> | remove a product                                 |
| `search` | GET /external/product  | find a product on OpenFoodFacts before adding it |

Error handling: invalid input (letters instead of a number, negative price, bad barcode) is rejected before anything is sent.
If the server is down, a request times out, or OpenFoodFacts fails, you get a short `Error: ...` message instead of a traceback.

To point the CLI at a different server: `INVENTORY_API_URL=http://host:port python cli.py list`

## 6. Running the tests

```
pytest                              # run everything
pytest -v                           # list each test by name
pytest tests/test_api.py            # only the API tests
pytest tests/test_external_api.py   # only the OpenFoodFacts tests
pytest tests/test_cli.py            # only the CLI tests
```

Tests use `pytest` and `unittest.mock`. No test touches the real network or needs the server running, so they are fast and repeatable. `tests/conftest.py` resets the inventory before every test so tests never affect each other.

### `tests/test_api.py` - the Flask endpoints

- GET all items, GET one item, and 404 for a missing item
- POST with a name, with a barcode, and with both (values you send win over API values)
- POST validation: missing name/barcode, bad price, bad stock, non-JSON body, non-digit barcode
- POST when OpenFoodFacts finds nothing (404) or is down (502, or still succeeds if a name was given)
- A new item's id is the highest current id plus one
- PATCH price, stock and name; unknown fields and empty bodies are rejected; an invalid value changes nothing
- DELETE an item and 404 for a missing item
- The `/external/product` route: missing parameters (400), found (200), not found (404), API failure (502)

### `tests/test_external_api.py` - the OpenFoodFacts function

`requests.get` is mocked, so these check how `fetch_product()` behaves for each kind of response:

- barcode found, and barcode not found (status 0)
- name search uses the first result, and returns nothing when there are no results
- only the fields we store are kept; missing fields become empty strings
- the correct URL and search parameters are sent
- the custom `User-Agent` header is sent
- connection errors, timeouts, HTTP errors and invalid JSON become a clear `ExternalAPIError`
- rate limit responses (429 and 503) give a "rate limit" message

### `tests/test_cli.py` - the command-line interface

`cli.requests.request` is mocked, so the CLI is tested without a running server:

- `list`, `view`, `add`, `update`, `delete` and `search` each call the correct API route with the correct data
- `delete` asks for confirmation, can be cancelled, and `--yes` skips the prompt
- `add` needs a name or a barcode, and `update` needs at least one field to change
- error handling: server down, timeout, API errors (404 and 502) and non-JSON error responses print a short `Error:` message and return exit code 1
- invalid input (letters for an id, negative price, bad barcode, missing command) is rejected before any request is sent

## 7. About the OpenFoodFacts API

Docs: https://openfoodfacts.github.io/openfoodfacts-server/api/

- **User-Agent:** OpenFoodFacts asks every app to send `AppName/Version (ContactEmail)`. Open `app.py` and replace `your-email@example.com`, or set it without editing code: `OFF_USER_AGENT="InventoryManagementLab/1.0 (you@example.com)"`.
- **Rate limits (per IP):** 15 product reads per minute and 10 searches per minute. Going over returns an error (the API shows it as a 502 with a "rate limit" message). Don't run searches in a loop.
- **Reading needs no login.** Only writing to their database does, and this project never writes to it.
- **Barcode lookups** call `GET /api/v2/product/<barcode>.json?fields=...`. The v2 API is marked deprecated in favour of v3, but it is still supported and its response (`status: 1` plus a `product` object) matches the shape this lab asks for.
- **Name lookups** call the legacy `/cgi/search.pl` keyword search. OpenFoodFacts says full-text search is not part of the v2/v3 API (their newer service is Search-a-licious), so treat name search as best-effort and prefer barcodes.
- Product data is added by volunteers, so fields can be missing or wrong.
- The data is licensed under the Open Database License. See the API docs' "Before You Start" section, which also asks developers to fill in their short API usage form.

## 8. Notes and limitations

- Data is stored in memory only. Restarting the server resets the inventory to the seed data.
- OpenFoodFacts data is community-contributed, so some fields may be blank.
- A new item gets the highest current id plus one, the same approach the help_desk_system blueprint uses.

## 9. Ideas to extend

- save the list to a JSON file or a database
- add a low-stock report
- filter or search the local inventory by name