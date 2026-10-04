
import argparse
import os
import sys

import requests


API_URL = os.environ.get("INVENTORY_API_URL", "http://127.0.0.1:5000")
REQUEST_TIMEOUT = 15 


class CLIError(Exception):
    """A problem we want to show the user as a friendly message (no traceback)."""


# ---------------------------------------------------------------------------
# Talking to the API
# ---------------------------------------------------------------------------
def api_request(method, path, **kwargs):
    """
    Send one HTTP request to the API and return the parsed JSON body.
    Every failure (server down, timeout, 4xx/5xx) becomes a CLIError.
    """
    url = f"{API_URL}{path}"
    try:
        response = requests.request(method, url, timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.Timeout:
        raise CLIError("The API took too long to respond (timed out).")
    except requests.ConnectionError:
        raise CLIError(
            f"Cannot reach the API at {API_URL}. Is the Flask server running? (python app.py)"
        )
    except requests.RequestException as exc:
        raise CLIError(f"Request failed: {exc}")

    try:
        body = response.json()
    except ValueError:
        body = None

    if not response.ok:
      
        message = body.get("error") if isinstance(body, dict) else None
        raise CLIError(message or f"API returned HTTP {response.status_code}")
    return body


# ---------------------------------------------------------------------------
# Argument validators (invalid input is caught here, before any request is sent)
# ---------------------------------------------------------------------------
def positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a whole number")
    if value < 1:
        raise argparse.ArgumentTypeError("id must be 1 or greater")
    return value


def non_negative_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a whole number")
    if value < 0:
        raise argparse.ArgumentTypeError("value cannot be negative")
    return value


def non_negative_float(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{text}' is not a number")
    if value < 0:
        raise argparse.ArgumentTypeError("value cannot be negative")
    return value


def barcode_type(text):
    if not text.isdigit():
        raise argparse.ArgumentTypeError("barcode must contain digits only")
    return text


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------
def print_item(item):
    """Print one inventory item in a readable multi-line format."""
    product = item["product"]
    print(f"ID:           {item['id']}")
    print(f"Name:         {product.get('product_name', '')}")
    print(f"Brand:        {product.get('brands', '')}")
    print(f"Barcode:      {item.get('barcode') or '-'}")
    print(f"Price:        {item['price']:.2f}")
    print(f"Stock:        {item['stock']}")
    print(f"Categories:   {product.get('categories', '')}")
    print(f"Quantity:     {product.get('quantity', '')}")
    print(f"Ingredients:  {product.get('ingredients_text', '')}")


# ---------------------------------------------------------------------------
# Commands (each one maps to one API route)
# ---------------------------------------------------------------------------
def cmd_list(args):
    """GET /inventory"""
    items = api_request("GET", "/inventory")
    if not items:
        print("The inventory is empty.")
        return
    print(f"{'ID':<4} {'Name':<28} {'Brand':<14} {'Price':>8} {'Stock':>6}")
    print("-" * 64)
    for item in items:
        product = item["product"]
        print(
            f"{item['id']:<4} {product.get('product_name', '')[:27]:<28} "
            f"{product.get('brands', '')[:13]:<14} {item['price']:>8.2f} {item['stock']:>6}"
        )


def cmd_view(args):
    """GET /inventory/<id>"""
    print_item(api_request("GET", f"/inventory/{args.id}"))


def cmd_add(args):
    """POST /inventory"""
    if not args.name and not args.barcode:
        raise CLIError("Provide --name and/or --barcode to add an item.")
    payload = {}
    if args.name:
        payload["product_name"] = args.name
    if args.brand:
        payload["brands"] = args.brand
    if args.barcode:
        payload["barcode"] = args.barcode
    if args.price is not None:
        payload["price"] = args.price
    if args.stock is not None:
        payload["stock"] = args.stock

    item = api_request("POST", "/inventory", json=payload)
    print("Item added:")
    print_item(item)


def cmd_update(args):
    """PATCH /inventory/<id> (price, stock, name, brand)"""
    payload = {}
    if args.price is not None:
        payload["price"] = args.price
    if args.stock is not None:
        payload["stock"] = args.stock
    if args.name:
        payload["product_name"] = args.name
    if args.brand:
        payload["brands"] = args.brand
    if not payload:
        raise CLIError("Nothing to update. Use --price, --stock, --name or --brand.")

    item = api_request("PATCH", f"/inventory/{args.id}", json=payload)
    print("Item updated:")
    print_item(item)


def cmd_delete(args):
    """DELETE /inventory/<id> (asks for confirmation unless --yes is given)"""
    if not args.yes:
        answer = input(f"Delete item {args.id}? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Cancelled. Nothing was deleted.")
            return
    result = api_request("DELETE", f"/inventory/{args.id}")
    print(result["message"])


def cmd_search(args):
    """GET /external/product - find a product on OpenFoodFacts"""
    params = {"barcode": args.barcode} if args.barcode else {"name": args.name}
    result = api_request("GET", "/external/product", params=params)
    product = result["product"]
    print("Found on OpenFoodFacts:")
    print(f"Name:         {product.get('product_name', '')}")
    print(f"Brand:        {product.get('brands', '')}")
    print(f"Barcode:      {result.get('barcode', '')}")
    print(f"Categories:   {product.get('categories', '')}")
    print(f"Quantity:     {product.get('quantity', '')}")
    print(f"Ingredients:  {product.get('ingredients_text', '')}")
    print("\nTip: add it to your inventory with:")
    print(f"  python cli.py add --barcode {result.get('barcode', '<barcode>')} --price <price> --stock <stock>")


# ---------------------------------------------------------------------------
# Argument parser + entry point
# ---------------------------------------------------------------------------
def build_parser():
    parser = argparse.ArgumentParser(
        prog="cli.py", description="Inventory Management System CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="show every item")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("view", help="show one item in detail")
    p.add_argument("id", type=positive_int)
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("add", help="add a new item")
    p.add_argument("--name", help="product name")
    p.add_argument("--brand", help="brand")
    p.add_argument("--barcode", type=barcode_type, help="barcode (fills details from OpenFoodFacts)")
    p.add_argument("--price", type=non_negative_float)
    p.add_argument("--stock", type=non_negative_int)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("update", help="update price / stock / name / brand")
    p.add_argument("id", type=positive_int)
    p.add_argument("--price", type=non_negative_float)
    p.add_argument("--stock", type=non_negative_int)
    p.add_argument("--name")
    p.add_argument("--brand")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="delete an item")
    p.add_argument("id", type=positive_int)
    p.add_argument("--yes", "-y", action="store_true", help="skip the confirmation prompt")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("search", help="find a product on OpenFoodFacts")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--barcode", type=barcode_type)
    group.add_argument("--name")
    p.set_defaults(func=cmd_search)

    return parser


def main(argv=None):
    """Run the CLI. Returns an exit code (0 = success, 1 = error)."""
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except CLIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())