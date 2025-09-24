# Daily Amazon Storefront (No-Spreadsheets Setup)

You do **not** need a spreadsheet open. This builds a daily product page automatically.

## 1) Make a GitHub repo
- Create a new public repo, e.g., `petite-curvy-daily`.

## 2) Upload these files
- `build_storefront.py`
- `requirements.txt`
- `.github/workflows/daily.yml`

(Just drag-drop them in the GitHub web UI.)

## 3) Add Secrets (Amazon API keys)
Repo → Settings → Secrets and variables → Actions → **New repository secret**
- `AMZ_ACCESS_KEY` → your PA-API access key
- `AMZ_SECRET_KEY` → your PA-API secret key
- `AMZ_PARTNER_TAG` → `heydealdiva-20`

## 4) Turn on Pages
Repo → Settings → Pages → Source: **Deploy from a branch**, Branch: `main`, Folder: `/docs`

## 5) Run it once
Repo → Actions → select `Build daily storefront` → **Run workflow**.
After it finishes, your page is at:
`https://YOUR_GITHUB_USERNAME.github.io/REPO_NAME/storefront.html`

## 6) Put that link in Lnk.bio
Edit the ✨ Daily Petite‑Curvy Finds button → paste the link above.

Done. It will refresh **daily at 7am ET** on its own.

### Change what it fetches
Edit `KEYWORDS` or review thresholds in `build_storefront.py`.
