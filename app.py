import os

import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

inventory = [
    {
        "id": 1,
        "barcode": "3017620422003",
        "status": 1,
        "product": {
            "product_name": "Nutella",
            "brands": "Ferrero",
            "ingredients_text": "Sugar, palm oil, hazelnuts, skimmed milk powder, cocoa",
            "categories": "Spreads, Hazelnut spreads",
            "quantity": "400 g",
        },
        "price": 5.49,
        "stock": 40,
    },
    {
        "id": 2,
        "barcode": "5449000000996",
        "status": 1,
        "product": {
            "product_name": "Coca-Cola",
            "brands": "Coca-Cola",
            "ingredients_text": "Carbonated water, sugar, colour (caramel E150d), phosphoric acid, natural flavourings",
            "categories": "Beverages, Sodas",
            "quantity": "330 ml",
        },
        "price": 1.25,
        "stock": 120,
    },
    {
        "id": 3,
        "barcode": "0025293000316",
        "status": 1,
        "product": {
            "product_name": "Organic Almond Milk",
            "brands": "Silk",
            "ingredients_text": "Filtered water, almonds, cane sugar, sea salt, sunflower lecithin",
            "categories": "Beverages, Plant-based milks",
            "quantity": "1 L",
        },
        "price": 3.99,
        "stock": 25,
    },
    {
        "id": 4,
        "barcode": "8000500310427",
        "status": 1,
        "product": {
            "product_name": "Kinder Bueno",
            "brands": "Kinder",
            "ingredients_text": "Milk chocolate, sugar, vegetable oils, hazelnuts, wheat flour",
            "categories": "Snacks, Chocolate bars",
            "quantity": "43 g",
        },
        "price": 1.1,
        "stock": 80,
    },
    {
        "id": 5,
        "barcode": "7622210449283",
        "status": 1,
        "product": {
            "product_name": "Oreo Original",
            "brands": "Oreo",
            "ingredients_text": "Wheat flour, sugar, palm oil, cocoa powder, glucose syrup",
            "categories": "Snacks, Biscuits",
            "quantity": "154 g",
        },
        "price": 2.3,
        "stock": 60,
    },
]

PRODUCT_FIELDS = [
    "product_name",
    "brands",
    "ingredients_text",
    "categories",
    "quantity",
]

# -----------------------------------------------------------------------------
# OPENFOODFACTS SETTINGS
# -----------------------------------------------------------------------------
OFF_BASE_URL = "https://world.openfoodfacts.org"
OFF_TIMEOUT = 10  
OFF_HEADERS = {
    "User-Agent": os.environ.get(
        "OFF_USER_AGENT", "InventoryManagementLab/1.0 (your-email@example.com)"
    )
}

OFF_FIELDS = "code,product_name,brands,ingredients_text,categories,quantity"


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def find_item(item_id):
    """
    Search for an item by ID.

    This is a LINEAR SEARCH because we may need to check each item one by one.
    If there are n items, the worst-case time complexity is O(n).
    """
    for item in inventory:
        if item["id"] == item_id:
            return item
    return None


def parse_price(value):
    """Validate a price: it must be a number that is not negative."""

    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("price must be a non-negative number")
    return round(float(value), 2)


def parse_stock(value):
    """Validate stock: it must be a whole number that is not negative."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("stock must be a non-negative whole number")
    return value


class ExternalAPIError(Exception):
    """Raised when the OpenFoodFacts API cannot be reached or answers badly."""


def get_json_from_api(url, params):
    """GET a URL and return the JSON, turning every failure into ExternalAPIError."""
    try:
        response = requests.get(
            url, params=params, headers=OFF_HEADERS, timeout=OFF_TIMEOUT
        )
       
        if response.status_code in (429, 503):
            raise ExternalAPIError(
                "OpenFoodFacts rate limit reached - wait a minute and try again"
            )
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise ExternalAPIError("OpenFoodFacts request timed out") from exc
    except requests.RequestException as exc:
        raise ExternalAPIError(f"OpenFoodFacts request failed: {exc}") from exc
    except ValueError as exc:  
        raise ExternalAPIError("OpenFoodFacts returned invalid JSON") from exc


def fetch_product(barcode=None, name=None):
    """
    Look a product up on OpenFoodFacts by barcode (preferred) or by name.

    Returns {"barcode": ..., "product": {...}}, or None if nothing matched.
    Raises ExternalAPIError if the external API fails.

    Barcode lookups use the v2 product endpoint (its response matches the lab's
    {"status": 1, "product": {...}} example). Name lookups use the legacy
    /cgi/search.pl keyword search, because full-text search does not exist in the
    v2/v3 API (OpenFoodFacts points to Search-a-licious for that).
    """
    if barcode:
        data = get_json_from_api(
            f"{OFF_BASE_URL}/api/v2/product/{barcode}.json", {"fields": OFF_FIELDS}
        )
        
        if data.get("status") != 1 or not data.get("product"):
            return None
        raw = data["product"]
        found_barcode = data.get("code") or raw.get("code") or barcode
    elif name:
        data = get_json_from_api(
            f"{OFF_BASE_URL}/cgi/search.pl",
            {
                "search_terms": name,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 1,
                "fields": OFF_FIELDS,
            },
        )
        products = data.get("products") or []
        if not products:
            return None
        raw = products[0]
        found_barcode = raw.get("code", "")
    else:
        return None

    
    product = {field: raw.get(field) or "" for field in PRODUCT_FIELDS}
    return {"barcode": str(found_barcode), "product": product}


# -----------------------------------------------------------------------------
# CRUD ROUTES - INVENTORY ITEMS
# -----------------------------------------------------------------------------
@app.route("/inventory", methods=["GET"])
def get_inventory():
    #
    return jsonify(inventory), 200


@app.route("/inventory/<int:item_id>", methods=["GET"])
def get_item(item_id):

    item = find_item(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    return jsonify(item), 200


@app.route("/inventory", methods=["POST"])
def create_item():
  
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    barcode = str(data.get("barcode") or "").strip()
    name = str(data.get("product_name") or "").strip()

    if not name and not barcode:
        return jsonify({"error": "Provide at least a product_name or a barcode"}), 400
    if barcode and not barcode.isdigit():
        return jsonify({"error": "barcode must contain digits only"}), 400

   
    try:
        price = parse_price(data.get("price", 0))
        stock = parse_stock(data.get("stock", 0))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    
    product = {field: str(data.get(field) or "").strip() for field in PRODUCT_FIELDS}

  
    if barcode:
        try:
            api_result = fetch_product(barcode=barcode)
        except ExternalAPIError as exc:
            if not name:
            
                return jsonify({"error": str(exc)}), 502
            api_result = None 

        if api_result is None and not name:
            return jsonify(
                {"error": "Barcode not found on OpenFoodFacts - supply a product_name instead"}
            ), 404

        if api_result is not None:
           
            for field, value in api_result["product"].items():
                if not product[field]:
                    product[field] = value

    new_item = {
        "id": max([item["id"] for item in inventory], default=0) + 1,
        "barcode": barcode,
        "status": 1,
        "product": product,
        "price": price,
        "stock": stock,
    }

    inventory.append(new_item)
    return jsonify(new_item), 201


@app.route("/inventory/<int:item_id>", methods=["PATCH"])
def update_item(item_id):
    item = find_item(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Request body must be a non-empty JSON object"}), 400

    allowed_fields = ["price", "stock"] + PRODUCT_FIELDS
    unknown_fields = [field for field in data if field not in allowed_fields]
    if unknown_fields:
        return jsonify(
            {"error": f"Cannot update field(s): {', '.join(sorted(unknown_fields))}"}
        ), 400
    try:
        if "price" in data:
            data["price"] = parse_price(data["price"])
        if "stock" in data:
            data["stock"] = parse_stock(data["stock"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if "product_name" in data and not str(data["product_name"] or "").strip():
        return jsonify({"error": "product_name cannot be empty"}), 400

    for field in allowed_fields:
        if field in data:
            if field in PRODUCT_FIELDS:
                item["product"][field] = str(data[field] or "").strip()
            else:
                item[field] = data[field]

    return jsonify(item), 200


@app.route("/inventory/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    item = find_item(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    inventory.remove(item)
    return jsonify({"message": "Item deleted successfully"}), 200


# -----------------------------------------------------------------------------
# EXTERNAL API ROUTE - FIND A PRODUCT ON OPENFOODFACTS
# -----------------------------------------------------------------------------
@app.route("/external/product", methods=["GET"])
def external_product():
   
    barcode = request.args.get("barcode", "").strip()
    name = request.args.get("name", "").strip()

    if not barcode and not name:
        return jsonify({"error": "Provide a barcode or name query parameter"}), 400
    if barcode and not barcode.isdigit():
        return jsonify({"error": "barcode must contain digits only"}), 400

    try:
        result = fetch_product(barcode=barcode or None, name=name or None)
    except ExternalAPIError as exc:
        return jsonify({"error": str(exc)}), 502

    if result is None:
        return jsonify({"error": "No matching product found on OpenFoodFacts"}), 404

    return jsonify({"status": 1, **result}), 200


if __name__ == "__main__":
    app.run(debug=True)