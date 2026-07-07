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
- Backend: FastAPI, Python 3.12, Pydantic
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
