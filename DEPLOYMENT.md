# TestPilot AI Deployment

TestPilot AI is split into a FastAPI backend and a Vite/React frontend.

## Backend on Render

Use the root-level `render.yaml` Blueprint when connecting the GitHub repository to Render. The Blueprint pins Python to `3.11.9`, sets the backend root directory, and configures the build/start commands.

Render was previously able to choose Python `3.14.x` when the service was created manually or when a non-root Blueprint was not detected. Python 3.14 is newer than the wheel support used by this backend's pinned Pydantic stack, so `pydantic-core` tried to build from source with Rust/maturin. The root Blueprint and `.python-version` files prevent that by forcing Python 3.11 before dependency installation.

Blueprint file:

```text
render.yaml
```

Service root directory:

```text
backend
```

Build command:

```bash
python -m pip install --upgrade pip && pip install -r requirements.txt
```

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Environment variables:

```bash
PYTHON_VERSION=3.11.9
DATABASE_URL=<managed-postgres-connection-string>
JWT_SECRET=<generated-secret>
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-vercel-app.vercel.app
ENABLE_TEST_EXECUTION=false
```

The backend uses SQLite automatically for local development. Production should use PostgreSQL through `DATABASE_URL` so users, projects, reports and generated artifacts survive restarts and deployments.

Health check path:

```text
/health
```

Local backend development still works:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## Frontend on Vercel

Create a Vercel project with the root directory set to `frontend`.

Build command:

```bash
npm run build
```

Output directory:

```text
dist
```

Environment variables:

```bash
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

Local frontend development still works without an env file because it falls back to:

```text
http://127.0.0.1:8000
```

## Production Checklist

- Render backend responds at `/health`.
- Vercel `VITE_API_BASE_URL` points to the Render backend URL.
- Render `CORS_ORIGINS` includes the Vercel frontend URL.
- Frontend upload, GitHub analysis, reports, exports, comparison and progress tracking work end to end.
