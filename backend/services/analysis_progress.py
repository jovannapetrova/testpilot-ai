from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

_PROGRESS: dict[str, dict] = {}
_LOCK = Lock()

AGENT_ORDER = [
    "Project Detector Agent",
    "Dependency Analyzer Agent",
    "Code Analyzer Agent",
    "Security Agent",
    "Quality Agent",
    "Test Generator Agent",
    "Coverage Agent",
    "Recommendation Agent",
    "Report Agent",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seconds_since(value: str | None) -> int:
    if not value:
        return 0

    try:
        started = datetime.fromisoformat(value)
        return max(0, int((datetime.now(timezone.utc) - started).total_seconds()))
    except Exception:
        return 0


def _estimate_eta(started_at: str | None, progress: int) -> int | None:
    elapsed = _seconds_since(started_at)

    if progress <= 0 or elapsed <= 0:
        return None

    if progress >= 100:
        return 0

    estimated_total = elapsed / (progress / 100)
    return max(0, int(estimated_total - elapsed))


def _completed_count(item: dict) -> int:
    return len([agent for agent in item["agents"] if agent["status"] == "completed"])


def start_analysis(project_id: str, project_name: str) -> None:
    with _LOCK:
        _PROGRESS[project_id] = {
            "project_id": project_id,
            "project_name": project_name,
            "status": "running",
            "progress": 0,
            "current_agent": "Preparing analysis",
            "started_at": now(),
            "finished_at": None,
            "elapsed_seconds": 0,
            "eta_seconds": None,
            "completed_agents": 0,
            "total_agents": len(AGENT_ORDER),
            "agents": [
                {
                    "name": name,
                    "status": "pending",
                    "message": "Pending",
                    "started_at": None,
                    "finished_at": None,
                }
                for name in AGENT_ORDER
            ],
            "error": None,
        }


def update_agent(project_id: str, agent_name: str, status: str, message: str = "") -> None:
    with _LOCK:
        item = _PROGRESS.get(project_id)
        if not item:
            return

        current_time = now()

        for agent in item["agents"]:
            if agent["name"] == agent_name:
                agent["status"] = status
                agent["message"] = message or status.title()

                if status == "running" and not agent.get("started_at"):
                    agent["started_at"] = current_time

                if status in ["completed", "failed"]:
                    agent["finished_at"] = current_time

        completed = _completed_count(item)
        progress = round((completed / len(item["agents"])) * 100)

        item["completed_agents"] = completed
        item["progress"] = progress
        item["current_agent"] = agent_name
        item["elapsed_seconds"] = _seconds_since(item.get("started_at"))
        item["eta_seconds"] = _estimate_eta(item.get("started_at"), progress)


def finish_analysis(project_id: str) -> None:
    with _LOCK:
        item = _PROGRESS.get(project_id)
        if item:
            item["status"] = "completed"
            item["progress"] = 100
            item["current_agent"] = "Completed"
            item["finished_at"] = now()
            item["elapsed_seconds"] = _seconds_since(item.get("started_at"))
            item["eta_seconds"] = 0
            item["completed_agents"] = len(item["agents"])


def fail_analysis(project_id: str, error: str) -> None:
    with _LOCK:
        item = _PROGRESS.get(project_id)
        if item:
            item["status"] = "failed"
            item["error"] = error
            item["finished_at"] = now()
            item["elapsed_seconds"] = _seconds_since(item.get("started_at"))
            item["eta_seconds"] = None


def get_progress(project_id: str) -> dict | None:
    with _LOCK:
        item = _PROGRESS.get(project_id)

        if not item:
            return None

        item["elapsed_seconds"] = _seconds_since(item.get("started_at"))
        item["eta_seconds"] = _estimate_eta(item.get("started_at"), item.get("progress", 0))

        return {
            **item,
            "agents": [dict(agent) for agent in item["agents"]],
        }