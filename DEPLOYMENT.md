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
https://<service-name>.onrender.com/            the JSON endpoint list (a smoke test)
https://<service-name>.onrender.com/index.html  forwards to the H5 client
https://<service-name>.onrender.com/calculator.html  the H5 client itself, served by Flask
https://<service-name>.onrender.com/api/...      the JSON API
```

The front-end stays an independent repository with its own history; only a
generated copy of it is vendored here, in `src/web`.

`render.yaml` describes this service, so a Render account can create it in one
step.

---

## 2. Before deploying: vendor the front-end

```powershell
# From this repository's root. PowerShell 7 (pwsh) is recommended.
pwsh -File deploy\sync-frontend.ps1
```

The script copies `832402226_calculator_frontend\src` into `src\web` and then
generates `src\web\index.html`. It prints how many files it wrote. Commit the
result:

```powershell
git add -A
git commit -m "Vendor the front-end build into src/web for single-service deployment"
git push
```

> Every later change to the front-end must be followed by another run of this
> script and another push, otherwise the deployed page stays on the old version.

### Why an index.html is generated

The client's own entry point is `calculator.html`. The application serves the
page at `/index.html` (and at the short alias `/app`) and enables its static
routes whenever the front-end directory holds an `index.html` **or** a
`calculator.html`. The generated `index.html` is a JavaScript-free redirect to
`./calculator.html`, so all three URLs reach the calculator:

| URL | What answers it |
| --- | --- |
| `https://<service>.onrender.com/index.html` | the redirect page |
| `https://<service>.onrender.com/app` | the redirect page |
| `https://<service>.onrender.com/calculator.html` | the calculator itself |

The bare root `/` is reserved for the JSON endpoint list, which is the quickest
way to confirm in a browser that the service is up. Never edit
`src/web/index.html` by hand: the next sync overwrites it. Edit the template
inside `deploy/sync-frontend.ps1` instead.

---

## 3. Deploy on Render (free plan, no credit card)

1. Create an account at <https://dashboard.render.com/register>; signing in with
   GitHub is the fastest option.
2. Open <https://dashboard.render.com/blueprints> and choose
   **New Blueprint Instance**.
3. Select the `832402226_calculator_backend` repository. Render reads
   `render.yaml` from the repository root.
4. Keep or change the service name (it becomes the URL prefix) and press
   **Apply**. The name in `render.yaml` is `calculator-832402226`; if that
   subdomain is already taken Render reports it and you must choose another.
5. Wait two to five minutes for the first build. When the status is **Live**,
   the URL is `https://<service-name>.onrender.com`.

Configuration used by the blueprint:

| Setting | Value |
| --- | --- |
| Root directory | `.` (the repository root; also the default) |
| Build command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start command | `gunicorn run:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60 --access-logfile - --error-logfile -` |
| Health check | `/api/health` |
| `PYTHON_VERSION` | `3.12.6` |
| `CALC_DEBUG` | `false` (a public debugger would expose source code) |
| `CALC_CORS_ORIGIN` | `*` (keeps LAN and phone testing working) |
| `CALC_FRONTEND_DIR` | `src/web` (enables the same origin static hosting) |

### The commands must not contain `cd`

Render checks the repository out into the working directory, so the application
files sit directly at its top:

```
<checkout>/run.py
<checkout>/requirements.txt
<checkout>/src/web/calculator.html
```

An earlier revision of `render.yaml` prefixed both commands with
`cd 832402226_calculator_backend`, assuming a folder of that name existed
*inside* the repository. It does not, so the build would stop with
`cd: No such file or directory` and the service would never start. Copy the
commands above exactly; do not add the prefix back. The prefix is only correct
when the service is created from a repository that *contains* this project as a
subfolder, which is not how this repository is laid out.

### Relative paths are anchored at the repository root, not at the working directory

On Render the repository is checked out at `/opt/render/project/src`, but the
build and start commands run with **`/opt/render/project`** as their working
directory. A relative `CALC_FRONTEND_DIR` was previously taken literally, so
`src/web` resolved to `/opt/render/project/src/web` - one level *above* the
vendored copy. The directory did not exist, the application never registered its
static routes, and every page request was answered by the JSON 404 handler:

```json
{"code":"NOT_FOUND","message":"No such endpoint: GET /index.html","success":false}
```

`src/config.py` now resolves a relative `CALC_FRONTEND_DIR` against the
repository root, so the value works no matter which working directory the process
was launched from, and `render.yaml` may keep using the readable `src/web`. If the
page still 404s, the start-up log now says so explicitly:

```
Static front-end hosting DISABLED: no index.html or calculator.html in <dir>
(cwd=..., repository root=...) ...
```

Search the Render logs for `Static front-end hosting` to see which directory was
tried and whether hosting was enabled.

Manual alternative: **New + → Web Service**, then copy the settings above into
the form.


### Free plan behaviour to expect

| Observation | Reason |
| --- | --- |
| The first request after 15 idle minutes takes about a minute | The instance spins down on idle. Render shows a loading page while it spins up. Open the page once before a demonstration, and click the status chip to probe again if it says "Backend offline" |
| The calculation history is empty after a redeploy, a restart **or a spin-down** | The free instance has an ephemeral filesystem: any local change, including the SQLite file, is lost on all three events. A persistent disk requires a paid instance, and free web services cannot attach one |
| The service is suspended before the month ends | Each workspace gets 750 free instance hours per month and a spun-down service does not consume them. A service that stays awake around the clock consumes roughly 720-744 |
| The page is served but the history is genuinely gone | This is a platform limit, not a bug. See below for the two ways to keep the data |

Two ways to keep the history, should the assignment require it:

* attach a **persistent disk** after upgrading the service to a paid plan. The
  tidiest mount path is the folder the application already writes to:

  | Runtime | Source code path | Disk mount path |
  | --- | --- | --- |
  | Python | `/opt/render/project/src` | `/opt/render/project/src/data` |

  The database then stays at its default `data/calculator.db`, so no environment
  variable has to change. Alternatively mount a standalone directory such as
  `/var/data` and point `CALC_DB_PATH` at a file inside it, for example
  `CALC_DB_PATH=/var/data/calculator.db`. Note that attaching a disk also
  disables zero-downtime deploys and prevents scaling past one instance;

* move the database off the instance entirely. A free Render Postgres also has
  limits (one per workspace, 1 GB, no backups, and it **expires 30 days after
  creation**), so it is not a permanent home for coursework data either.

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
| `GET https://<service>.onrender.com/api/health` | `"success": true` with `"database": "ok"` (a cold start takes about a minute) |
| `GET https://<service>.onrender.com/` | The endpoint list as JSON |
| `GET https://<service>.onrender.com/index.html` | Forwards to the calculator, status chip green |
| `GET https://<service>.onrender.com/app` | The same redirect |
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
| `/index.html` returns 404 in the cloud | Either `src/web` was not committed, or the vendored copy has no `index.html`, or `CALC_FRONTEND_DIR` resolves to the wrong directory. Run `deploy\sync-frontend.ps1`, commit and push; then check the start-up log line `Static front-end hosting` |
| `/index.html` 404s while `/api/health` works | The static routes were never registered. Usually a `CALC_FRONTEND_DIR` that points one level above the checkout; a relative value is now anchored at the repository root, so `src/web` is correct |
| The page loads but shows "Backend offline" | The instance is either still spinning up (a cold start takes about a minute) or `CALC_FRONTEND_DIR` does not point at `src/web`. Click the status chip to probe again |
| The service fails to start | The start command must use `$PORT` (see `render.yaml`), not a hard-coded 5000 |
| The build log says `cd: No such file or directory` | The build or start command was given a `cd` prefix again. This repository is checked out at the working directory root, so the prefix is wrong; see section 3 |
| History is empty after every deploy | Expected on the free plan: the filesystem is ephemeral, so the SQLite file is lost on redeploy, restart **and** spin-down |
| A front-end change is not visible online | The vendored copy in `src/web` is stale: re-run the sync script and push |
