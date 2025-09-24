import os
from datetime import datetime
from amazon_paapi import AmazonApi
import pandas as pd

# Load secrets from GitHub
ACCESS = os.getenv("AMZ_ACCESS_KEY")
SECRET = os.getenv("AMZ_SECRET_KEY")
TAG    = os.getenv("AMZ_PARTNER_TAG")

api = AmazonApi(ACCESS, SECRET, TAG, "us")

# 👉 Edit these keywords for your niche
KEYWORDS = [
    "petite plus dress",
    "curvy petite tops",
    "petite plus jeans",
    "petite plus cardigan"
]

MIN_STARS = 4.2
MIN_REVIEWS = 200

rows = []
for kw in KEYWORDS:
    try:
        results = api.search_items(keywords=kw, search_index="Fashion", item_count=10)
        for item in results.items:
            title = item.item_info.title.display_value if item.item_info and item.item_info.title else "Amazon Item"
            asin = item.asin
            url = f"https://www.amazon.com/dp/{asin}?tag={TAG}"
            img = item.images.primary.large.url if item.images and item.images.primary and item.images.primary.large else ""
            rating = item.customer_reviews.star_rating if item.customer_reviews else None
            reviews = item.customer_reviews.count if item.customer_reviews else None
            price = (item.offers.listings[0].price.amount
                     if item.offers and item.offers.listings and item.offers.listings[0].price else None)

            # Filter by rating/reviews
            if rating and reviews and rating >= MIN_STARS and reviews >= MIN_REVIEWS:
                rows.append({
                    "product_title": title,
                    "image_url": img,
                    "affiliate_url": url,
                    "rating": f"{rating:.1f}",
                    "reviews": reviews,
                    "price": price
                })
    except Exception as e:
        print(f"Error fetching {kw}: {e}")

df = pd.DataFrame(rows).drop_duplicates(subset=["affiliate_url"])
df.to_csv("daily_curated.csv", index=False)

# Simple HTML storefront
css = """body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px;background:#fff}
h1{font-size:26px;margin:0 0 10px}
.sub{opacity:.75;margin:0 0 18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
.card{display:block;border:1px solid #eee;border-radius:12px;padding:12px;text-decoration:none;color:#111;background:#fff}
.card img{width:100%;height:260px;object-fit:cover;border-radius:8px}
.card h3{font-size:14px;line-height:1.3;margin:8px 0 6px}
.card p{opacity:.8;margin:0}
.footer{margin-top:24px;font-size:12px;opacity:.7;text-align:center}
"""

cards=[]
for _, r in df.iterrows():
    meta = " · ".join([
        (f"{r['rating']}★" if r.get('rating') else ""),
        (f"{r['reviews']} reviews" if r.get('reviews') else ""),
        (f"${r['price']}" if str(r.get('price')) not in ("","None") else "")
    ]).strip(" ·")
    title = (r['product_title'][:90] + "…") if len(str(r['product_title'])) > 95 else str(r['product_title'])
    cards.append(
        f"<a class='card' href='{r['affiliate_url']}' target='_blank' rel='nofollow sponsored noreferrer'>"
        f"<img src='{r['image_url']}' alt='{title}'/>"
        f"<h3>{title}</h3><p>{meta}</p></a>"
    )

os.makedirs("docs", exist_ok=True)
html = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Daily Petite-Curvy Finds</title>
<style>{css}</style></head><body>
<h1>Daily Petite-Curvy Finds</h1>
<p class='sub'>Curated for petite + curvy fits (4.2★+, 200+ reviews).</p>
<div class='grid'>{''.join(cards)}</div>
<div class='footer'><p>Updated {datetime.now():%Y-%m-%d}. Disclosure: As an Amazon Associate, I earn from qualifying purchases.</p></div>
</body></html>"""

with open("docs/storefront.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Built docs/storefront.html and daily_curated.csv")
