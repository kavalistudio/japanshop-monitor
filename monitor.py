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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
}

def fetch_json(url, timeout=30):
    req = Request(url, method="GET", headers=BROWSER_HEADERS)
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        raise RuntimeError(f"Hostinger API HTTP {e.code}: {e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"Hostinger API network error: {e.reason}") from e

def current_api_url():
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return API_BASE + "?" + urlencode({
        "offset": 0, "limit": 30, "exclude_types": "subscription", "to_date": now
    })

def price_text(product):
    try:
        variants = product.get("variants") or []
        prices = variants[0].get("prices") or [] if variants else []
        if prices:
            p = prices[0]
            amount = p.get("amount")
            currency = p.get("currency") or {}
            symbol = currency.get("symbol", "") if isinstance(currency, dict) else ""
            code = currency.get("code", "") if isinstance(currency, dict) else ""
            if amount is not None:
                return f"{symbol or code}{float(amount)/100:.2f}"
    except (TypeError, ValueError, KeyError, IndexError):
        pass
    return ""

def telegram_send(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    req = Request(url, method="POST",
                  data=urlencode({"chat_id": chat_id, "text": text,
                                  "disable_web_page_preview": "true"}).encode("utf-8"),
                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=30) as r:
            response = json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Telegram HTTP {e.code}: {detail}") from e
    if not response.get("ok"):
        raise RuntimeError(f"Telegram rejected message: {response}")

def chunks_for_telegram(products, max_chars=3500):
    # Telegram limit is 4096 characters. Leave headroom for Unicode and formatting.
    heading = "В JapanShop появились новые товары:\n\n"
    chunk = heading
    for product in products:
        title = product.get("title") or "(без названия)"
        slug = product.get("slug") or ""
        price = price_text(product)
        link = f"https://japanshop.lt/{slug}" if slug else "https://japanshop.lt/"
        item = f"• {title}" + (f" — {price}" if price else "") + f"\n{link}\n\n"
        # Extremely long individual fields should not break all notifications.
        if len(item) > max_chars - len(heading):
            item = item[:max_chars - len(heading) - 30] + "\n[длинная запись сокращена]\n\n"
        if len(chunk) + len(item) > max_chars:
            yield chunk.rstrip()
            chunk = heading
        chunk += item
    if chunk != heading:
        yield chunk.rstrip()

def main():
    try:
        data = fetch_json(current_api_url())
        products = data.get("products") or []
        if not products:
            raise RuntimeError("Hostinger API returned no products")
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        last_id = str(state["last_id"])
        new_products = sorted(
            (p for p in products if str(p.get("id", "")) > last_id),
            key=lambda p: str(p.get("id", ""))
        )
        if not new_products:
            print(f"API OK. Products received: {len(products)}. No new product IDs.")
            return 0

        token = os.environ.get("TELEGRAM_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat_id:
            raise RuntimeError("TELEGRAM_TOKEN or TELEGRAM_CHAT_ID secret is missing")

        parts = list(chunks_for_telegram(new_products))
        for i, part in enumerate(parts, 1):
            telegram_send(token, chat_id, part)
            print(f"Telegram notification {i}/{len(parts)} delivered")

        newest_product = max(new_products, key=lambda p: str(p["id"]))
        state["last_id"] = str(newest_product["id"])
        state["last_title"] = newest_product.get("title") or ""
        state["saved_at_utc"] = datetime.now(timezone.utc).isoformat()
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
        print(f"STATE_UPDATED={state['last_id']}")
        return 0
    except Exception as e:
        # Preserve the old baseline if anything fails. Some messages may have
        # been delivered before failure and may be repeated on the next run.
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
