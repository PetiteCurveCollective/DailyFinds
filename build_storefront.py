# build_storefront.py
import os
from datetime import datetime

USE_API = True
try:
    from amazon_paapi import AmazonApi
except Exception as e:
    print(f"[warn] amazon_paapi import failed: {e}")
    USE_API = False

# ---------- CRITERIA ----------
KEYWORDS = [
    "women petite plus dress",
    "women petite plus tops",
    "women petite plus jeans",
    "women petite plus cardigan",
    "women petite plus blazer",
]
MIN_STARS = 4.2
MIN_REVIEWS = 200
SEARCH_INDEX = "Fashion"
COUNTRY = "US"

# ---------- SECRETS ----------
ACCESS = os.getenv("AMZ_ACCESS_KEY")
SECRET = os.getenv("AMZ_SECRET_KEY")
TAG    = os.getenv("AMZ_PARTNER_TAG") or "heydealdiva-20"

api = None
if USE_API and ACCESS and SECRET and TAG:
    try:
        api = AmazonApi(ACCESS, SECRET, TAG, COUNTRY)
        print("[info] AmazonApi initialized")
    except Exception as e:
        print(f"[warn] Could not init AmazonApi: {e}")
        USE_API = False


def build_card_from_item(it):
    """Return one product card HTML if it passes filters."""
    title = "Amazon Item"
    if getattr(it, "item_info", None) and getattr(it.item_info, "title", None):
        title = it.item_info.title.display_value or title

    asin = getattr(it, "asin", "")
    url = f"https://www.amazon.com/dp/{asin}?tag={TAG}" if asin else "#"

    img = ""
    if getattr(it, "images", None) and getattr(it.images, "primary", None) and getattr(it.images.primary, "large", None):
        img = it.images.primary.large.url

    rating = getattr(getattr(it, "customer_reviews", None), "star_rating", None)
    reviews = getattr(getattr(it, "customer_reviews", None), "count", None)
    if not (rating and reviews and rating >= MIN_STARS and reviews >= MIN_REVIEWS):
        return None

    price = None
    offers = getattr(it, "offers", None)
    if offers and getattr(offers, "listings", None):
        listing0 = offers.listings[0]
        if listing0 and getattr(listing0, "price", None):
            price = listing0.price.amount

    short_title = (title[:90] + "…") if len(str(title)) > 95 else str(title)
    price_text = f"${price}" if price not in (None, "", "None") else ""

    return (
        f"<a class='card' href='{url}' target='_blank' rel='nofollow sponsored noreferrer'>"
        f"<img src='{img}' alt='{short_title}'/>"
        f"<h3>{short_title}</h3>"
        f"<p>{price_text}</p>"
        f"</a>"
    )


def fetch_cards():
    """Search by keywords and return filtered cards."""
    cards = []
    seen_urls = set()

    if not api:
        print("[info] API unavailable; returning no products.")
        return cards

    for kw in KEYWORDS:
        try:
            print(f"[info] search: '{kw}'")
            results = api.search_items(keywords=kw, search_index=SEARCH_INDEX, item_count=10)
            for it in getattr(results, "items", []):
                card = build_card_from_item(it)
                if card:
                    asin = getattr(it, "asin", "")
                    url = f"https://www.amazon.com/dp/{asin}?tag={TAG}"
                    if url not in seen_urls:
                        seen_urls.add(url)
                        cards.append(card)
        except Exception as e:
            print(f"[warn] search failed for '{kw}': {e}")
            continue

    print(f"[info] total cards: {len(cards)}")
    return cards


def build_html(cards):
    css = """
    body {font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#fff}
    .header {padding:20px 0;text-align:center}
    .header img {max-width:320px;height:auto}
    .wrap {padding:24px}
    .grid {display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
    .card {display:block;border:1px solid #eee;border-radius:12px;padding:12px;text-decoration:none;color:#111;background:#fff}
    .card img {width:100%;height:260px;object-fit:cover;border-radius:8px}
    .card h3 {font-size:14px;line-height:1.3;margin:8px 0 6px}
    .card p {opacity:.8;margin:0}
    .empty {opacity:.7;text-align:center;margin:40px 0}
    .footer {margin:28px 0;font-size:12px;opacity:.7;text-align:center}
    """

    grid_inner = ''.join(cards) if cards else "<p class='empty'>New picks are loading — check back soon.</p>"

    html = f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Daily Petite-Curvy Finds</title>
  <style>{css}</style>
</head>
<body>

  <div class="header">
    <img src="header.png" alt="Petite Curve Collective">
  </div>

  <div class="wrap">
    <div class='grid'>
      {grid_inner}
    </div>

    <div class='footer'>
      <p>Updated {datetime.now():%Y-%m-%d}. This page contains affiliate links; I may earn a commission at no extra cost to you. As an Amazon Associate, I earn from qualifying purchases.</p>
    </div>
  </div>

</body>
</html>"""
    return html


def main():
    cards = fetch_cards()
    html = build_html(cards)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote docs/index.html")


# --- Quick API Sanity Test ---
if __name__ == "__main__":
    # When run by GitHub Actions, try one small search and print results
    try:
        test_api = AmazonApi(ACCESS, SECRET, TAG, COUNTRY)
        res = test_api.search_items(keywords="petite dress", search_index="Fashion", item_count=3)
        print("✅ API sanity test worked. Found items:")
        for item in getattr(res, "items", []):
            title = getattr(item.item_info.title, "display_value", "No title")
            print("-", item.asin, title)
    except Exception as e:
        print("❌ API sanity test failed:", e)

    # Continue normal page build
    main()
