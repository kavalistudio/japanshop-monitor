import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://api-ecommerce.hostinger.com/store/store_01JE1XBKR8H9CV333XYDSG520W/products"
STATE_FILE = Path(__file__).with_name("state.json")

def fetch_json(url, method="GET", data=None, headers=None, timeout=30):
    req = Request(url, method=method, data=data, headers=headers or {})
    with urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def current_api_url():
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    q = urlencode({
        "offset": 0,
        "limit": 30,
        "exclude_types": "subscription",
        "to_date": now,
    })
    return f"{API_BASE}?{q}"

def price_text(product):
    # Hostinger structures can vary; try a few likely places.
    try:
        variants = product.get("variants") or []
        prices = (variants[0].get("prices") or []) if variants else []
        if prices:
            p = prices[0]
            amount = p.get("amount")
            currency = p.get("currency") or {}
            symbol = currency.get("symbol") if isinstance(currency, dict) else ""
            code = currency.get("code") if isinstance(currency, dict) else ""
            if amount is not None:
                value = float(amount) / 100.0
                return f"{symbol or code}{value:.2f}".strip()
    except Exception:
        pass
    return ""

def send_ntfy(topic, title, message):
    if not topic:
        return
    url = "https://ntfy.sh/"
    payload = json.dumps({
        "topic": topic,
        "title": title,
        "message": message,
        "priority": 5,
        "tags": ["shopping_bags"],
    }, ensure_ascii=False).encode("utf-8")
    req = Request(
        url,
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urlopen(req, timeout=30) as r:
        r.read()

def main():
    # If the API fails, exit quietly; the next scheduled run will try again.
    try:
        data = fetch_json(current_api_url())
    except Exception as e:
        print(f"API unavailable: {e}")
        return 0

    products = data.get("products") or []
    if not products:
        print("No products returned.")
        return 0

    ids = sorted(str(p.get("id", "")) for p in products if p.get("id"))
    if not ids:
        print("No product IDs returned.")
        return 0

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    last_id = state["last_id"]

    new_products = sorted(
        [p for p in products if str(p.get("id", "")) > last_id],
        key=lambda p: str(p.get("id", "")),
    )

    if not new_products:
        print("No new product IDs.")
        return 0

    lines = ["Мама, в JapanShop появились новые товары", ""]
    for p in new_products:
        title = p.get("title") or "(без названия)"
        slug = p.get("slug") or ""
        price = price_text(p)
        url = f"https://japanshop.lt/{slug}" if slug else "https://japanshop.lt/"
        lines.append(f"• {title}" + (f" — {price}" if price else ""))
        lines.append(url)
        lines.append("")

    message = "\n".join(lines).strip()

    # Push notification.
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    try:
        send_ntfy(topic, "JapanShop: новые товары", message)
    except Exception as e:
        # Do NOT advance the state if notification failed, so it retries.
        print(f"Notification failed: {e}")
        return 1

    newest = max(str(p["id"]) for p in new_products)
    state["last_id"] = newest
    state["last_title"] = next((p.get("title") for p in reversed(new_products) if str(p.get("id")) == newest), "")
    state["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(message)
    print(f"\nSTATE_UPDATED={newest}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
