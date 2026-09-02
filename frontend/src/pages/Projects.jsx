import { useEffect, useMemo, useState } from "react";
import { FileArchive, GitBranch, PackageOpen, RefreshCw, Search } from "lucide-react";

import UploadPanel from "../components/projects/UploadPanel";
import GithubPanel from "../components/projects/GithubPanel";
import ProjectCard from "../components/projects/ProjectCard";
import AnalysisResultPanel from "../components/analysis/AnalysisResultPanel";
import EmptyState from "../components/ui/EmptyState";
import ErrorState from "../components/ui/ErrorState";
import Skeleton from "../components/ui/Skeleton";

import { getProjects, getReport } from "../api/client";

function displayLanguage(value) {
  if (!value) return "Unknown";
  return value === "python" ? "Python" : value;
}

function buildProjectCards(items) {
  return items.map((project) => ({
    id: project.project_id || project.id,
    name: project.project_name || project.name,
    source_url: project.source_url || "",
    source_type: project.source_type || "upload",
    framework: Array.isArray(project.frameworks)
      ? project.frameworks.join(", ")
      : project.framework || "",
    language: displayLanguage(project.language),
    status: project.status || "queued",
    progress: Number(project.progress || 0),
    current_stage: project.current_stage || "",
    error: project.error || "",
    quality: Number(project.overall_score || 0),
    created_at: project.created_at,
    completed_at: project.completed_at,
  }));
}

export default function Projects() {
  const [sourceMode, setSourceMode] = useState("zip");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [projects, setProjects] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [loadingReport, setLoadingReport] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const filteredProjects = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return projects.filter((project) => {
      if (statusFilter !== "all" && project.status !== statusFilter) return false;
      if (sourceFilter !== "all" && project.source_type !== sourceFilter) return false;
      if (!needle) return true;
      const haystack = [
        project.name,
        project.source_url,
        project.language,
        project.framework,
        project.status,
        project.source_type,
        project.current_stage,
      ].join(" ").toLowerCase();
      return haystack.includes(needle);
    });
  }, [projects, query, sourceFilter, statusFilter]);

  const activeJobCount = projects.filter((project) => ["queued", "running"].includes(project.status)).length;

  const loadProjects = async ({ silent = false } = {}) => {
    try {
      if (!silent) setLoadingProjects(true);
      setError("");
      const response = await getProjects();
      setProjects(buildProjectCards(response.projects || []));
    } catch (err) {
      setError(err.userMessage || "Projects could not be loaded.");
      setProjects([]);
    } finally {
      if (!silent) setLoadingProjects(false);
    }
  };

  const openProject = async (project) => {
    setSelectedProjectId(project.id);
    if (project.status !== "completed") {
      setSelectedReport(null);
      setNotice(
        project.status === "failed"
          ? project.error || "This analysis failed before a report was generated."
          : "This project is still queued or running. The report will be available when analysis completes.",
      );
      return;
    }

    try {
      setLoadingReport(true);
      setNotice("");
      setError("");
      const response = await getReport(project.id);
      setSelectedReport(response.report);
    } catch (err) {
      setSelectedReport(null);
      setError(err.userMessage || "This completed project does not have an available report.");
    } finally {
      setLoadingReport(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  useEffect(() => {
    if (!activeJobCount) return undefined;
    const timer = setInterval(() => loadProjects({ silent: true }), 2500);
    return () => clearInterval(timer);
  }, [activeJobCount]);

  return (
    <>
      <div className="page-header">
        <p className="eyebrow">Analysis workspace</p>
        <h2>Projects</h2>
        <p>Analyze source code and track current ZIP or GitHub analysis jobs.</p>
      </div>

      <div className="source-switch">
        <button
          type="button"
          className={sourceMode === "zip" ? "source-tab active" : "source-tab"}
          onClick={() => setSourceMode("zip")}
        >
          <PackageOpen size={17} />
          ZIP Upload
        </button>
        <button
          type="button"
          className={sourceMode === "github" ? "source-tab active" : "source-tab"}
          onClick={() => setSourceMode("github")}
        >
          <GitBranch size={17} />
          GitHub Repository
        </button>
      </div>

      <div className="dashboard-grid single-workflow">
        {sourceMode === "zip" ? (
          <UploadPanel onAnalysisComplete={() => loadProjects()} />
        ) : (
          <GithubPanel onAnalysisComplete={() => loadProjects()} />
        )}
      </div>

      <div className="section-heading project-archive-heading">
        <div>
          <p className="eyebrow">Stored analyses</p>
          <h2>Project Archive</h2>
        </div>
        <button className="btn btn-ghost" onClick={() => loadProjects()} disabled={loadingProjects}>
          <RefreshCw size={16} className={loadingProjects ? "spin" : ""} />
          {loadingProjects ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="project-toolbar">
        <div className="project-search">
          <Search size={17} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by project, repo URL, language, framework or status"
          />
        </div>

        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="all">All statuses</option>
          <option value="queued">Queued</option>
          <option value="running">Analyzing</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>

        <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}>
          <option value="all">All sources</option>
          <option value="upload">ZIP Upload</option>
          <option value="github">GitHub</option>
        </select>
      </div>

      {error ? <ErrorState title="Projects unavailable" message={error} onRetry={() => loadProjects()} /> : null}
      {notice ? <div className="auth-message project-notice">{notice}</div> : null}

      {loadingProjects && !projects.length ? (
        <Skeleton rows={4} />
      ) : (
        <div className="grid-4 project-grid">
          {filteredProjects.map((project) => (
            <button
              key={project.id}
              type="button"
              className={`project-card-button ${selectedProjectId === project.id ? "active" : ""}`}
              onClick={() => openProject(project)}
            >
              <ProjectCard project={project} />
            </button>
          ))}
        </div>
      )}

      {!loadingProjects && !filteredProjects.length ? (
        <EmptyState
          icon={FileArchive}
          title="No matching projects"
          message="Try another search term or start a ZIP/GitHub analysis from the workflow above."
        />
      ) : null}

      {loadingReport && (
        <p className="muted-text analysis-loading-text">
          Loading stored analysis details...
        </p>
      )}

      {selectedReport && (
        <div className="selected-analysis">
          <AnalysisResultPanel report={selectedReport} />
        </div>
      )}
    </>
  );
}
