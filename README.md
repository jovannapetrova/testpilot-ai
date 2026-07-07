# TestPilot AI

**TestPilot AI** is an intelligent multi-agent platform for automated software testing and software quality evaluation.

It analyzes uploaded Python projects, orchestrates multiple specialized agents, generates test suggestions, runs security and quality analysis, calculates scores, and exports reports.

## Architecture

```text
React Dashboard -> FastAPI Backend -> Agent Orchestrator
                                   |-> Code Analyzer Agent
                                   |-> Security Agent
                                   |-> Quality Agent
                                   |-> Test Generator Agent
                                   |-> Coverage Agent
                                   |-> Recommendation Agent
                                   |-> Report Agent
```

## Tech Stack

- Frontend: React, Vite, Axios, Recharts, Framer Motion, Lucide React
- Backend: FastAPI, Python 3.11, Pydantic
- Quality/Security: Bandit, Radon, Pytest, Coverage.py
- Reports: ReportLab + JSON
- Free deployment: Vercel frontend + Render backend

## Run locally

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Backend: http://localhost:8000
API docs: http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

## Notes for diploma defense

Use `backend/sample_projects/vulnerable_python_app` as the main demo input. It contains intentional issues so agents can detect security and quality problems.

## Production Deployment

TestPilot AI is ready for a split deployment with the backend on Render and the frontend on Vercel.

### Render Backend

Use the root-level `render.yaml` Blueprint when connecting the GitHub repository to Render. It pins Python to `3.11.9`, sets `backend` as the service root, and configures the health check and startup command for Render Free.

- Root directory: `backend`
- Build command: `python -m pip install --upgrade pip && pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`

Required environment variables:

```bash
PYTHON_VERSION=3.11.9
LOG_LEVEL=INFO
CORS_ORIGINS=https://your-vercel-app.vercel.app
ENABLE_TEST_EXECUTION=false
```

### Vercel Frontend

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`

Required environment variable:

```bash
VITE_API_BASE_URL=https://your-render-service.onrender.com
```

For local development, the frontend falls back to `http://127.0.0.1:8000`, and the backend allows `localhost:5173` / `127.0.0.1:5173` by default.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the full deployment checklist.
