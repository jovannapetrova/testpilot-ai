# TestPilot AI Deployment

TestPilot AI is split into a FastAPI backend and a Vite/React frontend.

## Backend on Render

Use the root-level `render.yaml` Blueprint when connecting the GitHub repository to Render. The Blueprint pins Python to `3.11.9`, sets the backend root directory, configures the build/start commands, and leaves deployment-specific frontend URLs for Render environment configuration instead of committing localhost values.

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
CORS_ORIGIN_REGEX=https://.*\.vercel\.app
ENABLE_TEST_EXECUTION=false
PASSWORD_RESET_CODE_MINUTES=30
PASSWORD_RESET_RESEND_SECONDS=60
MAX_UPLOAD_SIZE_MB=50
MAX_EXTRACTED_SIZE_MB=150
MAX_ARCHIVE_FILES=5000
SMTP_HOST=<smtp-host-for-password-reset-email>
SMTP_PORT=587
SMTP_USERNAME=<smtp-username>
SMTP_PASSWORD=<smtp-password>
SMTP_FROM=<verified-from-address>
SMTP_USE_TLS=true
```

The backend uses SQLite automatically for local development. Production should use PostgreSQL through `DATABASE_URL` so users, projects, reports and generated artifacts survive restarts and deployments. SMTP variables are required for production password-reset emails to be delivered.

The Blueprint generates `JWT_SECRET`, attaches `DATABASE_URL` from the managed PostgreSQL database, and prompts for `CORS_ORIGINS`. Set it to the deployed Vercel frontend URL.

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

Node version:

```text
20.19.0 or newer
```

Environment variables:

```bash
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

Local frontend development still works without an env file because it falls back to:

```text
http://127.0.0.1:8000
```

## Validation Commands

Backend:

```bash
cd backend
python -m py_compile main.py
pytest
```

Frontend:

```bash
cd frontend
npm test
npm run build
```

## Production Checklist

- Render backend responds at `/health`.
- Vercel `VITE_API_BASE_URL` points to the Render backend URL.
- Render `CORS_ORIGINS` includes the Vercel frontend URL or `CORS_ORIGIN_REGEX` allows the Vercel deployment domain.
- Frontend upload, GitHub analysis, reports, exports, comparison and progress tracking work end to end.
