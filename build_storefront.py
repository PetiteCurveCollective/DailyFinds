import os, pandas as pd
from datetime import datetime
from paapi5_python_sdk.api.default_api import DefaultApi
from paapi5_python_sdk.configuration import Configuration
from paapi5_python_sdk.api_client import ApiClient
from paapi5_python_sdk.search_items_request import SearchItemsRequest
from paapi5_python_sdk.search_items_resource import SearchItemsResource
from paapi5_python_sdk.models import Condition

ACCESS = os.getenv('AMZ_ACCESS_KEY')
SECRET = os.getenv('AMZ_SECRET_KEY')
TAG    = os.getenv('AMZ_PARTNER_TAG')

if not (ACCESS and SECRET and TAG):
    raise SystemExit('Missing AMZ_ACCESS_KEY/AMZ_SECRET_KEY/AMZ_PARTNER_TAG env vars.')

cfg = Configuration(access_key=ACCESS, secret_key=SECRET,
                    host='webservices.amazon.com', region='us-east-1')
api = DefaultApi(ApiClient(cfg))

RES = [
  SearchItemsResource.ITEMINFO_TITLE,
  SearchItemsResource.IMAGES_PRIMARY_LARGE,
  SearchItemsResource.CUSTOMERREVIEWS_COUNT,
  SearchItemsResource.CUSTOMERREVIEWS_STAR_RATING,
  SearchItemsResource.OFFERS_LISTINGS_PRICE
]

KEYWORDS = [
  'petite plus dress',
  'curvy petite tops',
  'petite plus jeans',
  'petite plus cardigan'
]

MIN_STARS   = 4.2
MIN_REVIEWS = 200

def ok(item):
    cr = getattr(item, 'customer_reviews', None)
    return cr and cr.star_rating and cr.count and cr.star_rating>=MIN_STARS and cr.count>=MIN_REVIEWS

def aff(asin, tag): return f'https://www.amazon.com/dp/{asin}?tag={tag}'

rows = []
for kw in KEYWORDS:
    req = SearchItemsRequest(partner_tag=TAG, partner_type='Associates',
        marketplace='www.amazon.com', keywords=kw, search_index='Apparel',
        condition=Condition.NEW, item_count=10, resources=RES)
    resp = api.search_items(req)
    if not resp or not resp.search_result: continue
    for it in resp.search_result.items:
        if not ok(it): continue
        title = it.item_info.title.display_value if it.item_info and it.item_info.title else 'Amazon Item'
        img = it.images.primary.large.url if it.images and it.images.primary and it.images.primary.large else ''
        asin = it.asin
        stars = it.customer_reviews.star_rating if it.customer_reviews else ''
        reviews = it.customer_reviews.count if it.customer_reviews else ''
        price = (it.offers.listings[0].price.amount
                 if (it.offers and it.offers.listings and it.offers.listings[0].price) else '')
        rows.append({
            'product_title': title,
            'image_url': img,
            'affiliate_url': aff(asin, TAG),
            'rating': f"{stars:.1f}" if stars else '',
            'reviews': reviews,
            'price': price
        })

df = pandas.DataFrame(rows).drop_duplicates(subset=['affiliate_url'])
df.to_csv('daily_curated.csv', index=False)

css = 'body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:24px;background:#ffffff}'\
     'h1{font-size:26px;margin:0 0 10px}'\
     '.sub{opacity:.75;margin:0 0 18px}'\
     '.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}'\
     '.card{display:block;border:1px solid #eee;border-radius:12px;padding:12px;text-decoration:none;color:#111;background:#fff}'\
     '.card img{width:100%;height:260px;object-fit:cover;border-radius:8px}'\
     '.card h3{font-size:14px;line-height:1.3;margin:8px 0 6px}'\
     '.card p{opacity:.8;margin:0}'\
     '.footer{margin-top:24px;font-size:12px;opacity:.7;text-align:center}'

cards=[]
for _,r in df.iterrows():
    meta = ' · '.join([
        (f"{r['rating']}★" if r.get('rating') else ''),
        (f"{r['reviews']} reviews" if r.get('reviews') else ''),
        (f"${r['price']}" if str(r.get('price')) not in ('','None') else '')
    ]).strip(' ·')
    title = (str(r['product_title'])[:90] + '…') if len(str(r['product_title']))>95 else str(r['product_title'])
    cards.append(
        f"<a class='card' href='{r['affiliate_url']}' target='_blank' rel='nofollow sponsored noreferrer'>"
        f"<img src='{r['image_url']}' alt='{title}'/>"
        f"<h3>{title}</h3><p>{meta}</p></a>"
    )

os.makedirs('docs', exist_ok=True)
html = """<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Daily Petite‑Curvy Finds</title>
<style>""" + css + """</style></head><body>
<h1>Daily Petite‑Curvy Finds</h1>
<p class='sub'>Curated for petite + curvy fits (4.2★+, 200+ reviews).</p>
<div class='grid'>""" + ''.join(cards) + """</div>
<div class='footer'><p>Updated """ + datetime.now().strftime('%Y-%m-%d') + """. Disclosure: As an Amazon Associate, I earn from qualifying purchases.</p></div>
</body></html>"""
with open('docs/storefront.html','w',encoding='utf-8') as f:
    f.write(html)
print('Built docs/storefront.html and daily_curated.csv')
