# BlockVerify — Deployment Guide

This guide covers deploying BlockVerify with the **Flask backend on Render** and the **frontend on Vercel**.

---

## Architecture Overview

```
Browser  →  Vercel (frontend/index.html)
               ↓ fetch() API calls
         Render (backend/app.py — Flask)
               ↓ reads/writes
         Persistent JSON files (Render disk)
```

---

## Part 1 — Deploy Backend on Render

### Prerequisites
- A [Render](https://render.com) account (free tier works)
- The repo pushed to GitHub

### Steps

**1. Go to Render Dashboard → New → Web Service**

**2. Connect your GitHub repo**
Select `innovation-space/course-project-submission-razor_hats` (or your fork).

**3. Configure the service**

| Field | Value |
|-------|-------|
| Name | `blockverify-backend` |
| Region | Singapore (or nearest) |
| Branch | `main` |
| Root Directory | *(leave blank)* |
| Runtime | `Python 3` |
| Build Command | `pip install -r backend/requirements.txt` |
| Start Command | `python backend/app.py` |

**4. Add Environment Variable**

| Key | Value |
|-----|-------|
| `PORT` | `5000` |

> Render automatically sets `PORT` — the app reads it via `os.environ.get("PORT", 5000)`.

**5. Click "Create Web Service"**

Render will build and deploy. Your backend URL will be:
```
https://<your-service-name>.onrender.com
```

**6. Test the backend**
```bash
curl https://<your-service-name>.onrender.com/api/stats
```
Expected response:
```json
{"totalBlocks": 1, "totalModels": 0, "totalVerifications": 0}
```

---

## Part 2 — Deploy Frontend on Vercel

### Prerequisites
- A [Vercel](https://vercel.com) account
- The `vercel.json` file already present in the repo root

### Steps

**1. Go to [vercel.com/new](https://vercel.com/new)**

**2. Import your GitHub repository**
Click "Add GitHub Account" if needed, then select the repo.

**3. Configure project settings**

| Field | Value |
|-------|-------|
| Framework Preset | `Other` |
| Root Directory | *(leave blank / `.`)* |
| Build Command | *(leave blank)* |
| Output Directory | `frontend` |

**4. Click Deploy**

Vercel will deploy `frontend/index.html` as a static site.

Your frontend URL will be:
```
https://blockverify-<hash>.vercel.app
```

---

## Part 3 — Connect Frontend to Backend

Open `frontend/index.html` and update the `API` constant:

```js
const API = window.location.hostname === 'localhost' || window.location.hostname === '0.0.0.0'
  ? 'http://localhost:5000/api'
  : 'https://<your-render-service>.onrender.com/api';
```

Replace `<your-render-service>` with your actual Render service name.

Redeploy the frontend on Vercel after this change.

---

## Part 4 — Running Locally

### Backend
```bash
cd blockverify/backend
pip install -r requirements.txt
python app.py
# → running on http://localhost:5000
```

### Frontend
```bash
cd blockverify/frontend
python3 -m http.server 8080
# → open http://localhost:8080
```

Or open `frontend/index.html` directly in a browser.

---

## Part 5 — Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `5000` | Port the Flask server listens on |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Failed to fetch` on frontend | Backend not running or wrong URL in `API` constant |
| Render build fails | Check `backend/requirements.txt` has all packages |
| `Cannot read properties of undefined` | Backend returned error — check Render logs |
| CORS error in browser | Ensure `flask-cors` is installed and `CORS(app)` is in `app.py` |
| Data lost on Render restart | Free tier has ephemeral disk — data resets on each deploy |

---

## render.yaml (auto-deploy config)

The repo includes `render.yaml` for one-click Render deployment:

```yaml
services:
  - type: web
    name: blockverify-backend
    runtime: python
    rootDir: .
    buildCommand: pip install -r backend/requirements.txt
    startCommand: python backend/app.py
```

---

*BlockVerify — razor_hats team, VIT*
