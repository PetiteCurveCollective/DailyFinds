import os, re, csv, random
from datetime import datetime
from amazon_paapi import AmazonApi

# --- Credentials from environment ---
ACCESS_KEY  = os.getenv("AMZ_ACCESS_KEY")
SECRET_KEY  = os.getenv("AMZ_SECRET_KEY")
PARTNER_TAG = os.getenv("AMZ_PARTNER_TAG")
COUNTRY     = "US"

api = AmazonApi(ACCESS_KEY, SECRET_KEY, PARTNER_TAG, COUNTRY)

# --- Search terms (plus-size loungewear / activewear) ---
KEYWORDS = [
    "plus size loungewear",
    "plus size lounge set",
    "plus size pajamas",
    "plus size sweatpants",
    "plus size hoodie",
    "plus size sweatshirt",
    "plus size athletic wear",
    "plus size activewear",
    "plus size workout clothes",
    "plus size yoga pants",
    "plus size leggings",
    "plus size joggers",
    "plus size athleisure",
    "plus size sports bra",
    "plus size tank top athletic",
]

# --- Quality filters ---
MIN_STARS   = 4.2
MIN_REVIEWS = 100
TARGET_MIN  = 12

# --- Regex to confirm it's loungewear/athletic-related ---
CATEGORY_RE = re.compile(
    r"\b(lounge|sleep|pajama|sweat|hoodie|athletic|active|yoga|legging|jogger|athleisure|sports)\b",
    re.I
)

def looks_relevant(text: str) -> bool:
    return bool(CATEGORY_RE.search(text or ""))

def passes_filters(p: dict) -> bool:
    if not (p.get("rating") and p.get("reviews")):
        return False
    if p["rating"] < MIN_STARS or p["reviews"] < MIN_REVIEWS:
        return False
    blob = " ".join([p.get("title_raw","")] + p.get("features", []))
    if not looks_relevant(blob):
        return False
    return True

def main():
    all_results = []
    for kw in KEYWORDS:
        try:
            items = api.search_products(keywords=kw, search_index="Apparel", item_count=10)
            for it in items:
                p = {
                    "title": it.title,
                    "title_raw": it.title,
                    "url": it.detail_page_url,
                    "image": it.images.large if it.images and it.images.large else "",
                    "rating": it.reviews.rating if it.reviews else None,
                    "reviews": it.reviews.count if it.reviews else None,
                    "features": it.features or []
                }
                if passes_filters(p):
                    all_results.append(p)
        except Exception as e:
            print(f"[warn] search fail for {kw}: {e}")

    # Deduplicate by URL
    seen, results = set(), []
    for p in all_results:
        if p["url"] not in seen:
            seen.add(p["url"])
            results.append(p)

    # Shuffle + trim
    random.shuffle(results)
    results = results[:TARGET_MIN]

    print(f"[info] final products kept: {len(results)}")

    # --- Write CSV ---
    with open("docs/daily_curated.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Title", "URL", "Image", "Rating", "Reviews"])
        for p in results:
            w.writerow([p["title"], p["url"], p["image"], p["rating"], p["reviews"]])

    # --- Write HTML ---
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write("<!doctype html><html><head><meta charset='utf-8'>")
        f.write("<meta name='viewport' content='width=device-width,initial-scale=1'>")
        f.write("<title>Daily Plus-Size Loungewear & Activewear</title>")
        f.write("<style>body{font-family:sans-serif;margin:24px;background:#fff}")
        f.write(".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}")
        f.write(".card{border:1px solid #eee;border-radius:12px;padding:12px;text-decoration:none;color:#111;background:#fff}")
        f.write(".card img{width:100%;height:260px;object-fit:cover;border-radius:8px}")
        f.write(".card h3{font-size:14px;line-height:1.3;margin:8px 0 6px}")
        f.write(".card p{opacity:.8;margin:0}")
        f.write(".footer{margin-top:24px;font-size:12px;opacity:.7;text-align:center}</style></head><body>")
        f.write("<h1>Daily Plus-Size Loungewear & Activewear</h1>")
        f.write("<div class='grid'>")
        for p in results:
            f.write(f"<a class='card' href='{p['url']}' target='_blank'>")
            f.write(f"<img src='{p['image']}' alt=''>")
            f.write(f"<h3>{p['title']}</h3>")
            f.write(f"<p>{p['rating']}★ ({p['reviews']} reviews)</p>")
            f.write("</a>")
        f.write("</div>")
        f.write("<div class='footer'><p>Updated {}. Disclosure: As an Amazon Associate, I earn from qualifying purchases. At no additional cost to you.</p></div>".format(datetime.now().strftime("%Y-%m-%d")))
        f.write("</body></html>")

if __name__ == "__main__":
    main()