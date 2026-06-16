# Deploying ExploreTree to Azure App Service

This deploys ExploreTree as a **single service**: the FastAPI backend serves
both the built React frontend *and* the `/ws` WebSocket, so you get **one URL**
with no CORS or cross-origin configuration.

> **Cost note:** this is a public link. Anyone who opens it triggers real
> Microsoft AI Search + Azure AI Foundry calls **on your keys/quota**. The keys
> themselves are never exposed to visitors (they live only in server-side App
> Settings), but usage is. Add auth or rate-limiting later if that's a concern.

---

## Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed and logged in:
  ```bash
  az login
  ```
- An Azure subscription with permission to create App Service resources.
- Node 18+ and Python 3.12+ locally (to build the frontend before deploying).
- Your secret values ready (same ones as `backend/.env` — see step 4).

Pick names/region (change as you like):
```bash
RG=exploretree-rg
PLAN=exploretree-plan
APP=exploretree-demo          # must be globally unique -> https://exploretree-demo.azurewebsites.net
LOCATION=eastus
```

---

## 1. Build the frontend locally

The backend serves `frontend/dist`, which is **gitignored** and **not** built on
Azure (the Python runtime won't run `npm`). So build it locally first — every
time you change the frontend, rebuild before deploying.

```bash
cd frontend
npm install
npm run build        # produces frontend/dist
cd ..
```

---

## 2. Create the App Service (Linux, Python 3.12)

```bash
az group create --name $RG --location $LOCATION

az appservice plan create \
  --name $PLAN --resource-group $RG \
  --is-linux --sku B1            # B1 = cheapest tier that allows Always On

az webapp create \
  --name $APP --resource-group $RG --plan $PLAN \
  --runtime "PYTHON:3.12"
```

---

## 3. Enable WebSockets + Always On (important)

WebSockets are **off by default** on App Service — the app will load but the
live tree will never connect without this:

```bash
az webapp config set \
  --name $APP --resource-group $RG \
  --web-sockets-enabled true \
  --always-on true
```

---

## 4. Set the secrets as App Settings

These are the same variables as `backend/.env.example`. Fill in your real
values. App Service injects them as environment variables, which
`pydantic-settings` reads (it falls back to env vars when there's no `.env`).

```bash
az webapp config appsettings set \
  --name $APP --resource-group $RG \
  --settings \
    BING_SEARCH_KEY="<your-key>" \
    BING_SEARCH_ENDPOINT="https://api.microsoft.ai/v3/search/web" \
    BING_NEWS_ENDPOINT="https://api.microsoft.ai/v3/search/news" \
    BING_FINANCE_ENDPOINT="https://api.microsoft.ai/v3/search/finance" \
    BING_PLACES_ENDPOINT="https://api.microsoft.ai/v3/search/places" \
    BING_IMAGES_ENDPOINT="https://api.microsoft.ai/v3/search/images" \
    BING_VIDEOS_ENDPOINT="https://api.microsoft.ai/v3/search/videos" \
    OPENAI_API_KEY="<your-foundry-key>" \
    OPENAI_BASE_URL="https://<your-resource>.services.ai.azure.com/openai/v1" \
    OPENAI_PLANNER_MODEL="<deployment-name>" \
    OPENAI_SYNTH_MODEL="<deployment-name>" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"
```

> `SCM_DO_BUILD_DURING_DEPLOYMENT=true` makes Azure run `pip install -r
> requirements.txt` from `backend/` on deploy (Oryx auto-detects the Python app).

---

## 5. Set the startup command

App Service provides the port via `$PORT`. Run uvicorn from the `backend`
directory so `app.main:app` resolves:

```bash
az webapp config set \
  --name $APP --resource-group $RG \
  --startup-file "python -m uvicorn app.main:app --host 0.0.0.0 --port \$PORT"
```

Tell Azure the app root is `backend/` (so it finds `requirements.txt` and `app/`):

```bash
az webapp config appsettings set \
  --name $APP --resource-group $RG \
  --settings PROJECT="backend"
```

---

## 6. Deploy the code (backend + built frontend)

From the **repo root**, zip-deploy the `backend/` app and the built
`frontend/dist`. The simplest path that includes both:

```bash
# zip the backend app plus the built frontend it serves
zip -r deploy.zip backend frontend/dist \
  -x "backend/.venv/*" "backend/__pycache__/*" "backend/**/__pycache__/*"

az webapp deploy \
  --name $APP --resource-group $RG \
  --src-path deploy.zip --type zip
```

> The backend resolves the frontend at `../../frontend/dist` relative to
> `backend/app/main.py`, so the zip must preserve that `backend/` +
> `frontend/dist/` layout (it does, since you zip from the repo root).

---

## 7. Verify

```bash
# health route (proves the Python app booted)
curl https://$APP.azurewebsites.net/health        # -> {"status":"ok"}
```

Then open **https://&lt;APP&gt;.azurewebsites.net** in a browser:
- The ExploreTree home page loads (frontend served by FastAPI).
- Type a question and hit **Explore** — the tree/cards should start filling in.
  (This confirms the **WSS** WebSocket connected — the frontend derives
  `wss://<host>/ws` from the page origin automatically.)

If the page loads but nothing happens on Explore, re-check **step 3**
(WebSockets enabled) and the browser console for a failed `wss://` connection.

Logs:
```bash
az webapp log tail --name $APP --resource-group $RG
```

---

## 8. Put the link on GitHub

Add the live URL to `README.md`, e.g. near the top:

```markdown
**[▶ Live demo](https://exploretree-demo.azurewebsites.net)**
```

Commit and push.

---

## Redeploying after changes

- **Frontend change:** `cd frontend && npm run build`, then repeat **step 6**.
- **Backend change:** repeat **step 6** (no rebuild needed).
- App Settings/secrets persist across deploys — only re-run **step 4** to change them.
