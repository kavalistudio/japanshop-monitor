import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API_BASE = "https://api-ecommerce.hostinger.com/store/store_01JE1XBKR8H9CV333XYDSG520W/products"
STATE_FILE = Path(__file__).with_name("state.json")

BROWSER_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "lt-LT,lt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://japanshop.lt",
    "Referer": "https://japanshop.lt/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
}

def fetch_json(url, timeout=30):
    req = Request(url, method="GET", headers=BROWSER_HEADERS)
    try:
        with urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw)
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Hostinger API HTTP {e.code}: {e.reason}. {body}".strip()) from e
    except URLError as e:
        raise RuntimeError(f"Hostinger API network error: {e.reason}") from e

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

def send_telegram(token, chat_id, text):
    if not token:
        raise RuntimeError("GitHub secret TELEGRAM_TOKEN is missing")
    if not chat_id:
        raise RuntimeError("GitHub secret TELEGRAM_CHAT_ID is missing")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "true",
    }).encode("utf-8")

    req = Request(
        url,
        method="POST",
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": BROWSER_HEADERS["User-Agent"],
        },
    )

    try:
        with urlopen(req, timeout=30) as r:
            response = json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Telegram HTTP {e.code}: {e.reason}. {body}".strip()) from e

    if not response.get("ok"):
        raise RuntimeError(f"Telegram rejected message: {response}")

def main():
    try:
        data = fetch_json(current_api_url())
    except Exception as e:
        # IMPORTANT: fail the GitHub Action. A green run must mean the API actually worked.
        print(f"ERROR: {e}")
        return 1

    products = data.get("products") or []
    if not products:
        print("ERROR: Hostinger API returned no products.")
        return 1

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    last_id = str(state["last_id"])

    new_products = sorted(
        [p for p in products if str(p.get("id", "")) > last_id],
        key=lambda p: str(p.get("id", "")),
    )

    if not new_products:
        print(f"API OK. Products received: {len(products)}. No new product IDs.")
        return 0

    lines = ["В JapanShop появились новые товары:", ""]
    for p in new_products:
        title = p.get("title") or "(без названия)"
        slug = p.get("slug") or ""
        price = price_text(p)
        url = f"https://japanshop.lt/{slug}" if slug else "https://japanshop.lt/"
        lines.append(f"• {title}" + (f" — {price}" if price else ""))
        lines.append(url)
        lines.append("")

    message = "\n".join(lines).strip()

    token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    try:
        send_telegram(token, chat_id, message)
    except Exception as e:
        # Do not advance baseline when notification fails.
        print(f"ERROR: Notification failed: {e}")
        return 1

    newest = max(str(p["id"]) for p in new_products)
    newest_product = next(p for p in new_products if str(p.get("id")) == newest)

    state["last_id"] = newest
    state["last_title"] = newest_product.get("title") or ""
    state["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(message)
    print(f"\nSTATE_UPDATED={newest}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
