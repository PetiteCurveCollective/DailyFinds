# build_storefront.py
import os, time, csv
from datetime import datetime, timezone
from html import escape

# ---------- CONFIG ----------
KEYWORDS = [
    "women petite plus dress",
    "women petite plus tops",
    "women petite plus jeans",
    "women petite plus cardigan",
    "women petite plus blazer",
    "women petite plus sweaters",
    "women petite plus jackets",
    "women petite plus activewear",
]
MIN_STARS = 4.2
MIN_REVIEWS = 200
SEARCH_INDEX = "Fashion"
COUNTRY = "US"

# Caption style for RSS ("short" or "rich")
CAPTION_STYLE = "rich"

# Disclosure only for the website footer
DISCLOSURE = ("As an Amazon Associate, I earn from qualifying purchases. "
              "I also work with other top retailers and may earn when you shop my links. "
              "At no additional cost to you.")

# Throttling/retry
REQUEST_DELAY_SEC = 4
MAX_RETRIES_PER_CALL = 6
BACKOFF_MULTIPLIER = 2.0

# ---------- AMAZON PA-API ----------
USE_API = True
try:
    from amazon_paapi import AmazonApi
except Exception as e:
    print(f"[warn] amazon_paapi import failed: {e}")
    USE_API = False

ACCESS = os.getenv("AMZ_ACCESS_KEY")
SECRET = os.getenv("AMZ_SECRET_KEY")
TAG    = os.getenv("AMZ_PARTNER_TAG") or "heydealdiva-20"

print("[env] HAVE_ACCESS_KEY =", bool(ACCESS))
print("[env] HAVE_SECRET_KEY =", bool(SECRET))
print("[env] TAG_SUFFIX =", (TAG or "")[-4:])

api = None
if USE_API and ACCESS and SECRET and TAG:
    try:
        api = AmazonApi(ACCESS, SECRET, TAG, COUNTRY)
        print("[info] AmazonApi initialized")
    except Exception as e:
        print(f"[warn] Could not init AmazonApi: {e}")
        USE_API = False


def _is_throttle_error(err: Exception) -> bool:
    msg = str(err).lower()
    return any(s in msg for s in ["limit", "throttle", "too many requests", "rate"])


def call_with_retry(func, *args, **kwargs):
    delay = REQUEST_DELAY_SEC
    for attempt in range(1, MAX_RETRIES_PER_CALL + 1):
        try:
            return func(*args, **kwargs), None
        except Exception as e:
            if _is_throttle_error(e) and attempt < MAX_RETRIES_PER_CALL:
                print(f"[throttle] attempt {attempt}/{MAX_RETRIES_PER_CALL} – waiting {delay:.1f}s then retrying…")
                time.sleep(delay); delay *= BACKOFF_MULTIPLIER
                continue
            return None, e


def to_dict(item):
    title = "Amazon Item"
    if getattr(item, "item_info", None) and getattr(item.item_info, "title", None):
        title = item.item_info.title.display_value or title

    asin = getattr(item, "asin", "")
    url = f"https://www.amazon.com/dp/{asin}?tag={TAG}" if asin else ""

    img = ""
    if getattr(item, "images", None) and getattr(item.images, "primary", None) and getattr(item.images.primary, "large", None):
        img = item.images.primary.large.url or ""

    rating = getattr(getattr(item, "customer_reviews", None), "star_rating", None)
    reviews = getattr(getattr(item, "customer_reviews", None), "count", None)
    if not (rating and reviews and rating >= MIN_STARS and reviews >= MIN_REVIEWS):
        return None

    price = None
    offers = getattr(item, "offers", None)
    if offers and getattr(offers, "listings", None):
        listing0 = offers.listings[0]
        if listing0 and getattr(listing0, "price", None):
            price = listing0.price.amount

    short_title = (title[:90] + "…") if len(str(title)) > 95 else str(title)
    return {
        "asin": asin,
        "title": short_title,
        "url": url,
        "image": img,
        "price": ("" if price in (None, "", "None") else f"${price}")
    }


def fetch_products():
    products, seen = [], set()
    if not api:
        print("[info] API unavailable; returning no products.")
        return products

    for kw in KEYWORDS:
        print(f"[info] search: '{kw}'")
        time.sleep(REQUEST_DELAY_SEC)
        for page in (1,):
            res, err = call_with_retry(
                api.search_items,
                keywords=kw,
                search_index=SEARCH_INDEX,
                item_count=10,
                item_page=page
            )
            if err:
                print(f"[warn] search failed for '{kw}' p{page}: {err}")
                continue
            for it in getattr(res, "items", []):
                d = to_dict(it)
                if not d or not d["url"]:
                    continue
                if d["url"] in seen:
                    continue
                seen.add(d["url"])
                products.append(d)
    print(f"[info] total products: {len(products)}")
    return products


def build_html(products):
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
        grid_inner = "".join(cards)
    else:
        grid_inner = "<p class='empty'>New picks are loading — check back soon.</p>"

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
    <div class='grid'>{grid_inner}</div>
    <div class='footer'>
      <p>Updated {datetime.now():%Y-%m-%d}. {escape(DISCLOSURE)}</p>
    </div>
  </div>
</body>
</html>"""
    return html


def write_csv(products, path):
    fieldnames = ["title", "url", "image", "price", "date"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for p in products:
            row = dict(p)
            row["date"] = datetime.now().strftime("%Y-%m-%d")
            w.writerow(row)
    print(f"[info] wrote {path}")


def rss_caption(p):
    title = p["title"]
    price = p["price"]
    if CAPTION_STYLE == "short":
        lines = [
            f"{title}",
            (price if price else ""),
            "Shop ⤵",
            p["url"],
            "#petite #curvy #petitecurvy #amazonfinds #dailyfinds #outfitideas"
        ]
    else:
        lines = [
            f"{title}",
            (f"{price} · Petite + Curvy find" if price else "Petite + Curvy find"),
            "Shop ⤵",
            p["url"],
            "#petite #curvy #petitecurvy #amazonfinds #dailyfinds #outfitideas"
        ]
    return "\n".join([l for l in lines if l.strip() != ""])


def write_rss(products, path, site_url):
    updated_rfc2822 = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items_xml = []
    for p in products:
        title = escape(p["title"])
        link = p["url"]
        img  = p["image"]
        guid = escape(p.get("asin") or p["url"])
        desc = rss_caption(p)
        items_xml.append(f"""
      <item>
        <title>{title}</title>
        <link>{link}</link>
        <guid isPermaLink="false">{guid}</guid>
        <pubDate>{updated_rfc2822}</pubDate>
        <description><![CDATA[{desc}]]></description>
        <enclosure url="{img}" type="image/jpeg"/>
      </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Petite Curve Collective — Daily Picks</title>
    <link>{site_url}</link>
    <description>Daily curated petite+curvy Amazon finds (rating ≥ 4.2, ≥ 200 reviews).</description>
    <lastBuildDate>{updated_rfc2822}</lastBuildDate>
    {''.join(items_xml)}
  </channel>
</rss>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(feed)
    print(f"[info] wrote {path}")


def main():
    products = fetch_products()
    os.makedirs("docs", exist_ok=True)

    # HTML page
    html = build_html(products)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote docs/index.html")

    # CSV + RSS
    write_csv(products, "docs/daily_curated.csv")
    write_rss(products, "docs/feed.xml", "https://petitecurvecollective.github.io/DailyFinds/")


if __name__ == "__main__":
    main()
