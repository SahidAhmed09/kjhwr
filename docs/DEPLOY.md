# Deploying to Vercel

How this repo is shaped for Vercel, why, and the commands. Facts about Vercel come from its current docs (linked below);
anything not confirmed by a docs page or by the local build output is marked as unverified.

## Shape

| Piece | File | Notes |
|---|---|---|
| Python function | `app.py` (repo root) | Defines `app = create_app()`. Vercel's FastAPI preset looks for a top-level `app` in a root `app.py`. It adds `backend/` to `sys.path`, since the code lives there. |
| Dependencies and Python | `pyproject.toml`, `.python-version` | FastAPI is detected from `pyproject.toml`. Python 3.13 (Vercel supports 3.12 default, 3.13, 3.14). Pins must equal `backend/requirements.txt`; a test enforces it. |
| Static front end | `public/` | The built React app. Vercel serves `public/` from its CDN at the matching root paths. Rebuild with `npm run build:public` in `frontend/`. |
| Function config | `vercel.json` | `maxDuration` 30 s, `includeFiles` for the snapshot, `excludeFiles` to keep dev files out of the bundle. |
| Snapshot | `backend/data/snapshot.json.gz` | 107 KB, bundled into the function and read lazily on the first request. |

The preset sends every path that is not a static file to the single function, so `/api/*`, `/docs` and `/openapi.json` reach FastAPI
and `/` is the CDN's `index.html`. All front-end state is in the query string (`/?view=accuracy&day=...`), so no client-side route needs a fallback.

## Limits that apply

- Python function bundle: **500 MB uncompressed** (250 MB for other runtimes). Estimated here: about **15 MB** (3%), almost all `pydantic_core` and `pydantic`.
- Max duration: Hobby 300 s default and maximum; this app sets 30 s. Memory 2 GB on Hobby.
- Request and response bodies: 4.5 MB each. The largest response is `/api/series` at about 234 KB.
- Python bundles include every project file reachable at build time, with no tree-shaking, which is why `excludeFiles` exists.
- The function filesystem should be treated as read-only; this app writes nothing.

## Commands

Run these yourself; nothing here logs in for you.

```powershell
# 0. Once: install or update the CLI (FastAPI support needs 48.1.8 or newer)
npm install -g vercel@latest
vercel --version
vercel whoami            # shows the account you are logged in as; run `vercel login` only if it says you are not

# 1. From the repo root, make sure public/ is the current front-end build, then test everything
cd F:\demo\lov\frontend
npm ci
npm run build:public
cd ..\backend
python -m unittest discover -s tests

# 2. Link the folder to a Vercel project (asks for scope and project name; pick or create one)
cd F:\demo\lov
vercel link

# 3. Deploy to production. Use --prod: Standard Protection covers every URL except production domains,
#    so a preview URL would answer 401 to anyone not signed in to Vercel (including a test script).
vercel deploy --prod --logs
```

The last line of output is the deployment URL. For a production deployment the project's `*.vercel.app` domain is the public one.

### Afterwards

```powershell
# Compare the live API and front end with the local build (needs backend/requirements-dev.txt installed)
python backend\scripts\compare_deploy.py https://YOUR-PROJECT.vercel.app
```

### Redeploying after a change

- Front-end change: `cd frontend; npm run build:public`, then `vercel deploy --prod`.
- Snapshot change: rebuild it (`docker compose --profile tools run --rm snapshot`), review `backend/data/REPORT.txt`, then redeploy.

## Front end on a different Vercel project than the back end

The default is one project: the front end calls `/api` on its own origin. To host the front end apart from the back end:

- The front end reads `VITE_API_BASE` at build time. `frontend/.env.vercel` sets it to the back end's URL (`https://kjhwr-tau-blue.vercel.app`),
  and `npm run build:vercel` uses it. Plain `npm run build` (local, Docker, `build:public`) does not, so those keep calling their own origin.
- In the front-end Vercel project set Root Directory `frontend`, Build Command `npm run build:vercel`, Output Directory `dist`.
- The back end must allow the browser to call it from another origin. It now answers GET requests from any origin (no cookies or credentials), or only from
  the origins in the `CORS_ALLOW_ORIGINS` environment variable (comma-separated). The deployed back end has to be redeployed once to pick this up.

## Why the front end is committed

`public/` holds build output and is committed so the Vercel build needs no Node step. Whether Node is available inside a Python
project's build on Vercel is not something the docs state, so this avoids depending on it. The cost is that `public/` can go stale;
`test_vercel_ready.py` fails if `public/index.html` differs from a fresh `frontend/dist`.

## What was verified locally, and what was not

Verified, by running the Vercel CLI's local build on a copy of this repo and reading the generated `.vercel/output`:
- It detects FastAPI, uses Python 3.13 from `.python-version`, and installs from `pyproject.toml` with uv.
- The function's file map contains `app.py`, all of `backend/wind_api`, `wind_analysis`, `wind_data` and `backend/data/snapshot.json.gz`,
  and does not contain `frontend/`, `docs/`, tests, scripts or markdown.
- `public/` becomes static files (`static/index.html`, `static/assets/*`); every other path is rewritten to the single `fastapi` function.

Not verified: behaviour on Vercel's runtime (cold start time, whether the snapshot path resolves inside the deployed bundle),
Fluid-compute instance reuse, and anything about the live URL. Those need the deployment.

## Sources

- Python runtime: https://vercel.com/docs/functions/runtimes/python
- FastAPI on Vercel: https://vercel.com/docs/frameworks/backend/fastapi
- Function limits: https://vercel.com/docs/functions/limitations
- Python version: https://vercel.com/docs/functions/runtimes/python/python-version
- `vercel deploy`: https://vercel.com/docs/cli/deploy
- Deployment Protection: https://vercel.com/docs/deployment-protection
