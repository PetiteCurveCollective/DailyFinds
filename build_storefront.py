# build_storefront.py

import os, time, csv, re, random
from datetime import datetime, timezone
from html import escape

# Use the python-amazon-paapi wrapper
from amazon_paapi import AmazonApi

# --- Credentials from GitHub Secrets ---
ACCESS_KEY  = os.getenv("AMZ_ACCESS_KEY")
SECRET_KEY  = os.getenv("AMZ_SECRET_KEY")
PARTNER_TAG = os.getenv("AMZ_PARTNER_TAG") or "heydealdiva-20"
COUNTRY     = "US"

print("[env] HAVE_ACCESS_KEY =", bool(ACCESS_KEY))
print("[env] HAVE_SECRET_KEY =", bool(SECRET_KEY))
print("[env] TAG_SUFFIX      =", (PARTNER_TAG or "")[-4:])

api = None
try:
    api = AmazonApi(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, COUNTRY)
    print("[info] AmazonApi initialized")
except Exception as e:
    print(f"[warn] Could not init AmazonApi: {e}")

    # Plus only (adds inventory; size gate will still apply)
    "women plus size dress", "women plus size tops", "women plus size jeans",
    "women plus size cardigan", "women plus size sweater", "women plus size blazer",
    "women plus size trousers", "women plus size coat", "women plus size workwear",

    # Petite with explicit XL hints
    "women petite dress xl", "women petite tops xl",
    "women petite cardigan xl", "women petite blazer xl", "women petite coat xl",
]

# Filters (adaptive fallback)
TARGET_MIN = 12
STRICT_MIN_STARS   = 4.2
STRICT_MIN_REVIEWS = 200
RELAX1_MIN_STARS   = 4.2
RELAX1_MIN_REVIEWS = 100
RELAX2_MIN_STARS   = 4.0
RELAX2_MIN_REVIEWS = 100

# Hard size rule: must contain one of these sizes in title/features
REQUIRED_SIZE_PATTERN = re.compile(r"\b(0X|XL|XXL|1X|2X|3X)\b", re.I)

# Amazon search
SEARCH_INDEX = "Fashion"
COUNTRY      = "US"
RESOURCES = [
    "CustomerReviews.Count",
    "CustomerReviews.StarRating",
    "Images.Primary.Large",
    "ItemInfo.Title",
    "ItemInfo.Features",
    "Offers.Listings.Price",
]

# Throttling / retry
REQUEST_DELAY_SEC     = 6          # polite base delay between calls
JITTER_SEC            = 1.5        # random jitter
MAX_RETRIES_PER_CALL  = 6
BACKOFF_MULTIPLIER    = 2.0
MAX_API_CALLS_PER_RUN = 120

# Branding / pages
SITE_URL   = "https://petitecurvecollective.github.io/DailyFinds/"
DISCLOSURE = ("As an Amazon Associate, I earn from qualifying purchases. "
              "I also work with other top retailers and may earn when you shop my links. "
              "At no additional cost to you.")
FALLBACK_ON_EMPTY  = True
FALLBACK_IMAGE     = "header.png"
FALLBACK_HASHTAGS  = "#petite #curvy #petitecurvy #amazonfinds #dailyfinds #outfitideas"
CAPTION_STYLE      = "rich"   # for RSS descriptions

# ============================== AMAZON ===============================

USE_API = True
try:
    # pip package: python-amazon-paapi  →  module: amazon_paapi
    from amazon_paapi import AmazonApi
except Exception as e:
    print(f"[warn] amazon_paapi import failed: {e}")
    USE_API = False

ACCESS_KEY  = os.getenv("AMZ_ACCESS_KEY")
SECRET_KEY  = os.getenv("AMZ_SECRET_KEY")
PARTNER_TAG = os.getenv("AMZ_PARTNER_TAG") or "heydealdiva-20"

print("[env] HAVE_ACCESS_KEY =", bool(ACCESS_KEY))
print("[env] HAVE_SECRET_KEY =", bool(SECRET_KEY))
print("[env] TAG_SUFFIX      =", (PARTNER_TAG or "")[-4:])

api = None
if USE_API and ACCESS_KEY and SECRET_KEY and PARTNER_TAG:
    try:
        api = AmazonApi(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, COUNTRY)
        print("[info] AmazonApi initialized")
    except Exception as e:
        print(f"[warn] Could not init AmazonApi: {e}")
        USE_API = False

_api_calls = 0
def _budget_ok(): return _api_calls < MAX_API_CALLS_PER_RUN
def _sleep_politely():
    time.sleep(REQUEST_DELAY_SEC + random.random() * JITTER_SEC)

def _is_throttle(err: Exception) -> bool:
    m = str(err).lower()
    return any(s in m for s in ["throttle", "limit", "too many requests", "rate"])

def call_with_retry(func, *args, **kwargs):
    global _api_calls
    if not _budget_ok():
        raise RuntimeError("API call budget reached")
    delay = REQUEST_DELAY_SEC
    for attempt in range(1, MAX_RETRIES_PER_CALL + 1):
        try:
            _api_calls += 1
            return func(*args, **kwargs), None
        except Exception as e:
            if _is_throttle(e) and attempt < MAX_RETRIES_PER_CALL:
                wait = delay + random.random() * JITTER_SEC
                print(f"[throttle] attempt {attempt}/{MAX_RETRIES_PER_CALL} – waiting {wait:.1f}s")
                time.sleep(wait); delay *= BACKOFF_MULTIPLIER
                continue
            return None, e

# ============================== HELPERS ==============================

def extract(item):
    """Pull fields we need; keep raw title/features for size checks."""
    title = "Amazon Item"
    try:
        if getattr(item, "item_info", None) and getattr(item.item_info, "title", None):
            title = item.item_info.title.display_value or title
    except Exception:
        pass

    features = []
    try:
        if getattr(item, "item_info", None) and getattr(item.item_info, "features", None):
            features = item.item_info.features.display_values or []
    except Exception:
        features = []

    asin = getattr(item, "asin", "") or ""
    url  = f"https://www.amazon.com/dp/{asin}?tag={PARTNER_TAG}" if asin else ""

    img = ""
    try:
        if getattr(item, "images", None) and getattr(item.images, "primary", None) and getattr(item.images.primary, "large", None):
            img = item.images.primary.large.url or ""
    except Exception:
        pass

    rating  = getattr(getattr(item, "customer_reviews", None), "star_rating", None)
    reviews = getattr(getattr(item, "customer_reviews", None), "count", None)

    price = ""
    try:
        offers = getattr(item, "offers", None)
        if offers and getattr(offers, "listings", None):
            lst = offers.listings[0]
            if lst and getattr(lst, "price", None) and lst.price.amount is not None:
                price = f"${lst.price.amount}"
    except Exception:
        pass

    short_title = (str(title)[:90] + "…") if len(str(title)) > 95 else str(title)
    return {
        "asin": asin,
        "title": short_title,
        "title_raw": title,
        "features": features,
        "url": url,
        "image": img,
        "rating": rating,
        "reviews": reviews,
        "price": price,
    }

def size_gate(p) -> bool:
    """Enforce XL / XXL / 0X / 1X / 2X / 3X in title or features."""
    text = " ".join([p.get("title_raw","")] + p.get("features", []))
    return bool(REQUIRED_SIZE_PATTERN.search(text))

def passes_filters(p, min_stars, min_reviews) -> bool:
    if not (p["rating"] and p["reviews"]):
        return False
    if p["rating"] < min_stars or p["reviews"] < min_reviews:
        return False
    if not size_gate(p):
        return False
    return True

def fetch_with_threshold(min_stars, min_reviews, need=TARGET_MIN):
    products, seen = [], set()
    if not api:
        print("[info] API unavailable"); return products

    for kw in KEYWORDS:
        if not _budget_ok(): break
        print(f"[info] search: '{kw}' (≥{min_stars}★, ≥{min_reviews} reviews | sizes: XL/XXL/0X/1X–3X)")
        _sleep_politely()
        for page in (1, 2):  # two pages per keyword is usually plenty
            if not _budget_ok(): break
            res, err = call_with_retry(
                api.search_items,
                keywords=kw,
                search_index=SEARCH_INDEX,
                item_count=10,
                item_page=page,
                resources=RESOURCES
            )
            if err:
                print(f"[warn] search failed '{kw}' p{page}: {err}")
                continue
            for it in getattr(res, "items", []):
                d = extract(it)
                if not d or not d["url"] or d["url"] in seen:
                    continue
                if not passes_filters(d, min_stars, min_reviews):
                    continue
                seen.add(d["url"])
                products.append(d)
                if len(products) >= need:
                    print(f"[info] reached target {need} at ≥{min_stars}★/≥{min_reviews}")
                    return products
    return products

def fetch_products():
    items = fetch_with_threshold(STRICT_MIN_STARS, STRICT_MIN_REVIEWS, TARGET_MIN)
    if len(items) >= TARGET_MIN:
        print(f"[info] total products (strict): {len(items)}"); return items

    print(f"[info] relaxing → ≥{RELAX1_MIN_STARS}★ & ≥{RELAX1_MIN_REVIEWS} reviews")
    more = fetch_with_threshold(RELAX1_MIN_STARS, RELAX1_MIN_REVIEWS, TARGET_MIN)
    urls = {p["url"] for p in items}
    for m in more:
        if m["url"] not in urls:
            items.append(m); urls.add(m["url"])

    if len(items) < 8:
        print(f"[info] relaxing more → ≥{RELAX2_MIN_STARS}★ & ≥{RELAX2_MIN_REVIEWS} reviews")
        more2 = fetch_with_threshold(RELAX2_MIN_STARS, RELAX2_MIN_REVIEWS, 8)
        for m in more2:
            if m["url"] not in urls:
                items.append(m); urls.add(m["url"])

    print(f"[info] total products: {len(items)}")
    return items

# ============================== OUTPUT ===============================

def build_html(products):
    css = """
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#fff}
    .header{padding:20px 0;text-align:center}
    .header img{max-width:320px;height:auto}
    .wrap{padding:24px}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
    .card{display:block;border:1px solid #eee;border-radius:12px;padding:12px;text-decoration:none;color:#111;background:#fff}
    .card img{width:100%;height:260px;object-fit:cover;border-radius:8px}
    .card h3{font-size:14px;line-height:1.3;margin:8px 0 6px}
    .card p{opacity:.8;margin:0}
    .empty{opacity:.75;text-align:center;margin:40px 0}
    .footer{margin:28px 0;font-size:12px;opacity:.7;text-align:center}
    """
    if products:
        cards = []
        for p in products:
            cards.append(
                f"<a class='card' href='{p['url']}' target='_blank' rel='nofollow sponsored noreferrer'>"
                f"<img src='{p['image']}' alt='{escape(p['title'])}'/>"
                f"<h3>{escape(p['title'])}</h3>"
                f"<p>{escape(p['price'])}</p>"
                f"</a>"
            )
        grid = "".join(cards)
    else:
        grid = """
        <div class='empty'>
          <p>New picks are loading — check back soon.</p>
          <p style='font-size:12px;opacity:.7'>(No items passed today’s filters: rating/reviews + size gate)</p>
        </div>"""

    return f"""<!doctype html>
<html><head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Daily Petite-Curvy Finds</title>
  <style>{css}</style>
</head>
<body>
  <div class="header"><img src="header.png" alt="Petite Curve Collective"></div>
  <div class="wrap">
    <div class="grid">{grid}</div>
    <div class="footer"><p>Updated {datetime.now():%Y-%m-%d}. {escape(DISCLOSURE)}</p></div>
  </div>
</body></html>"""

def write_csv(products, path):
    fields = ["title","url","image","price","rating","reviews","date"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for p in products:
            r = dict(p); r["date"] = datetime.now().strftime("%Y-%m-%d"); w.writerow(r)
    print(f"[info] wrote {path}")

def rss_caption(p):
    title, price = p["title"], p["price"]
    if CAPTION_STYLE == "short":
        lines = [title, price, "Shop ⤵", p["url"],
                 "#petite #curvy #petitecurvy #amazonfinds #dailyfinds #outfitideas"]
    else:
        lines = [title,
                 (f"{price} · Petite + Curvy find" if price else "Petite + Curvy find"),
                 "Shop ⤵", p["url"],
                 "#petite #curvy #petitecurvy #amazonfinds #dailyfinds #outfitideas"]
    return "\n".join([x for x in lines if x and x.strip()])

def write_rss(products, path, site_url):
    updated = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []
    if products:
        for p in products:
            items.append(f"""
      <item>
        <title>{escape(p['title'])}</title>
        <link>{p['url']}</link>
        <guid isPermaLink="false">{escape(p.get('asin') or p['url'])}</guid>
        <pubDate>{updated}</pubDate>
        <description><![CDATA[{rss_caption(p)}]]></description>
        <enclosure url="{p['image']}" type="image/jpeg"/>
      </item>""")
    elif FALLBACK_ON_EMPTY:
        desc = f"Fresh petite + curvy finds are up now.\nShop ⤵\n{site_url}\n{FALLBACK_HASHTAGS}"
        items.append(f"""
      <item>
        <title>New Petite-Curvy picks are live</title>
        <link>{site_url}</link>
        <guid isPermaLink="false">{escape(site_url + 'fallback-' + datetime.now().strftime('%Y%m%d'))}</guid>
        <pubDate>{updated}</pubDate>
        <description><![CDATA[{desc}]]></description>
        <enclosure url="{site_url}{FALLBACK_IMAGE}" type="image/jpeg"/>
      </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Petite Curve Collective — Daily Picks</title>
    <link>{site_url}</link>
    <description>Daily curated petite+curvy Amazon finds (XL/XXL/0X/1X–3X).</description>
    <lastBuildDate>{updated}</lastBuildDate>
    {''.join(items)}
  </channel>
</rss>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(feed)
    print(f"[info] wrote {path}")

# ============================== MAIN ===============================

def main():
    items = fetch_products()
    os.makedirs("docs", exist_ok=True)

    # HTML
    html = build_html(items)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote docs/index.html")

    # CSV + RSS
    write_csv(items, "docs/daily_curated.csv")
    write_rss(items, "docs/feed.xml", SITE_URL)

if __name__ == "__main__":
    main()
