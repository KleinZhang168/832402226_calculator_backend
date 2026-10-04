# Deployment guide - 832402226_calculator_backend

This repository is one half of a two-repository assignment. The client lives in
the repository **832402226_calculator_frontend**. This document describes how to
put the pair on the public internet for free, then how to call the API and how
to hand the project to somebody else for review.

The short version: the back end is deployed alone, and it also serves a copy of
the front-end, so a single URL exposes both the page and the JSON API with no
cross origin requests.

---

## 1. Why a single service

The assignment requires two repositories, but the free tier of a cloud host
provides a single web service. The front-end is a zero-build static site, so the
cheapest arrangement is:

```
https://<service-name>.onrender.com/index.html   the H5 client (served by Flask)
https://<service-name>.onrender.com/api/...      the JSON API
```

The front-end stays an independent repository with its own history; only a
generated copy of it is vendored here, in `src/web`.

`render.yaml` describes this service, so a Render account can create it in one
step.

---

## 2. Before deploying: vendor the front-end

```powershell
# From this repository's root (Windows PowerShell)
powershell -NoProfile -File deploy\sync-frontend.ps1
```

The script copies `832402226_calculator_frontend\src` into `src\web` and prints
how many files were copied. Commit the result:

```powershell
git add -A
git commit -m "Vendor the front-end build into src/web for single-service deployment"
git push
```

> Every later change to the front-end must be followed by another run of this
> script and another push, otherwise the deployed page stays on the old version.

---

## 3. Deploy on Render (free plan, no credit card)

1. Create an account at <https://dashboard.render.com/register>; signing in with
   GitHub is the fastest option.
2. Open <https://dashboard.render.com/blueprints> and choose
   **New Blueprint Instance**.
3. Select this repository. Render reads `render.yaml` from the repository root.
4. Keep or change the service name (it becomes the URL prefix) and press
   **Apply**.
5. Wait two to five minutes for the first build. When the status is **Live**,
   the URL is `https://<service-name>.onrender.com`.

Configuration used by the blueprint:

| Setting | Value |
| --- | --- |
| Build command | `cd 832402226_calculator_backend && pip install -r requirements.txt` |
| Start command | `cd 832402226_calculator_backend && gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60` |
| Health check | `/api/health` |
| `PYTHON_VERSION` | `3.12.6` |
| `CALC_DEBUG` | `false` (a public debugger would expose source code) |
| `CALC_CORS_ORIGIN` | `*` (keeps LAN and phone testing working) |
| `CALC_FRONTEND_DIR` | `src/web` (enables the same origin static hosting) |

Manual alternative: **New + → Web Service**, then copy the settings above into
the form. The repository name in the build and start commands is the folder
Render checks out; adjust it if the repository itself is named
`832402226_calculator_backend` (in that case drop the `cd` prefix).

### Free plan behaviour to expect

| Observation | Reason |
| --- | --- |
| The first request after 15 idle minutes takes 30-60 seconds | The instance sleeps. Open the page once before a demonstration, and click the status chip to probe again if it shows "Backend offline" |
| The calculation history is empty after a redeploy | The free plan has no persistent disk. Persisting the SQLite file requires a paid instance with a disk |

### Other free hosts

| Host | Free offer | Notes |
| --- | --- | --- |
| Render | One web service | Used here; reads `render.yaml` directly |
| Hugging Face Spaces | Docker Space | Files can be uploaded through the web UI, so git is optional; the Space also sleeps |
| PythonAnywhere | One web app, always on | 100 CPU seconds per day, and the free web app must be renewed every three months |
| Vercel, Netlify, cloud functions | - | Not usable: their file systems are read-only or ephemeral, so SQLite cannot work |

---

## 4. Verify the deployment

| Check | Expected |
| --- | --- |
| `GET https://<service>.onrender.com/api/health` | `"success": true` with `"database": "ok"` |
| `GET https://<service>.onrender.com/` | The endpoint list as JSON |
| `GET https://<service>.onrender.com/index.html` | The calculator page, status chip green |
| Press `2`, long press `×`, press `3`, press `=` | The result `8` and "Saved to history" |
| Open the history view | The record is listed and can be deleted |

---

## 5. Calling the API

All responses follow the contract required by the assignment: success carries
`success: true` plus the business fields, failure carries `success: false` and a
`message` (plus a machine readable `code`).

```bash
BASE=https://<service>.onrender.com

# Health check
curl -s $BASE/api/health

# Evaluate and store
curl -s -X POST $BASE/api/calculate \
     -H "Content-Type: application/json" \
     -d '{"expression":"(1+2)*3"}'

# Evaluate without storing
curl -s -X POST $BASE/api/calculate/preview \
     -H "Content-Type: application/json" \
     -d '{"expression":"1/3"}'

# Paged history
curl -s "$BASE/api/history?page=1&pageSize=5"

# Delete one record / clear everything
curl -s -X DELETE $BASE/api/history/1
curl -s -X DELETE $BASE/api/history
```

PowerShell equivalent:

```powershell
$base = 'https://<service>.onrender.com'
Invoke-RestMethod "$base/api/health"
Invoke-RestMethod -Uri "$base/api/calculate" -Method Post `
  -ContentType 'application/json' -Body '{"expression":"(1+2)*3"}'
```

Status codes: 200 on success, 400 for validation or evaluation problems
(`VALIDATION_ERROR`, `INVALID_EXPRESSION`, `DIVIDE_BY_ZERO`,
`RESULT_OVERFLOW`), 404 for an unknown route or history id, 405 for a wrong
method, 500 for an unexpected failure.

---

## 6. Update and redeploy

```powershell
git add -A
git commit -m "Describe the change"
git push
```

Render redeploys automatically because `autoDeploy` is enabled in
`render.yaml`. The dashboard also offers **Manual Deploy → Deploy latest
commit**.

---

## 7. Handing the project to a reviewer

The reviewer does **not** need git. Three options, in increasing effort for that
person:

| Option | What the reviewer needs |
| --- | --- |
| Send the deployed URL | Nothing but a browser (a phone works too) |
| Send a source archive | Python 3.8+ only; Flask is installed from `requirements.txt` |
| Send the repository links | git only if they want to clone; browsing the site needs nothing |

A message you can copy:

> This is my front-end / back-end separated calculator: Flask + SQLite on the
> server, a plain H5 page on the client (no build step).
>
> Quick look, nothing to install:
> `https://<service-name>.onrender.com/index.html`
> The free instance sleeps after 15 idle minutes, so the first load can take
> 30-60 seconds. If the chip says "Backend offline", click it to probe again.
>
> Suggested tour (about a minute):
> 1. Check that the chip is green ("Backend online").
> 2. Type `2`, long press `×` (this inserts `^`), type `3`, press `=` - the
>    result is `8` and the note says "Saved to history".
> 3. Type `1/0` and press `=` - a red "Division by zero is not allowed" comes
>    from the server; the page never computes anything itself.
> 4. Type `0.1+0.2` and press `=` - the result is `0.3`, because the server uses
>    decimal arithmetic.
> 5. Open the history view to see, delete and clear the stored records.
>
> To run it locally instead (Python 3.8+, no git needed):
> ```
> cd 832402226_calculator_backend
> python -m venv .venv
> .venv\Scripts\python -m pip install -r requirements.txt
> .venv\Scripts\python run.py
>
> cd 832402226_calculator_frontend\src
> python -m http.server 8080
> ```
> Then open <http://127.0.0.1:8080/calculator.html>.
>
> To confirm the front-end cannot calculate on its own, stop the back-end and
> press `=` in the page: it shows "Cannot reach the backend service" instead of
> a result.

---

## 8. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `/index.html` returns 404 in the cloud | `src/web` was not committed. Run `deploy\sync-frontend.ps1`, commit and push |
| The page loads but shows "Backend offline" | The instance is still waking up, or `CALC_FRONTEND_DIR` does not point at `src/web` |
| The service fails to start | The start command must use `$PORT` (see `render.yaml`), not a hard-coded 5000 |
| History is empty after every deploy | Expected on the free plan, which has no persistent disk |
| A front-end change is not visible online | The vendored copy in `src/web` is stale: re-run the sync script and push |
