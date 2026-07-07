# TestPilot AI Deployment

TestPilot AI is split into a FastAPI backend and a Vite/React frontend.

## Backend on Render

Create a Render Web Service from the repository and set the root directory to `backend`.

Build command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Environment variables:

```bash
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-vercel-app.vercel.app
```

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
