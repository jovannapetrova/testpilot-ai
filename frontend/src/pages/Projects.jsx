import { useEffect, useMemo, useState } from "react";
import { GitBranch, PackageOpen, RefreshCw, Search } from "lucide-react";

import UploadPanel from "../components/projects/UploadPanel";
import GithubPanel from "../components/projects/GithubPanel";
import ProjectCard from "../components/projects/ProjectCard";
import AnalysisResultPanel from "../components/analysis/AnalysisResultPanel";

import { getProjects, getReport } from "../api/client";

export default function Projects() {
  const [sourceMode, setSourceMode] = useState("zip");
  const [query, setQuery] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loadingReport, setLoadingReport] = useState(false);
  const [error, setError] = useState("");

  const buildProjectCards = (items) => {
    return items.map((project) => ({
      id: project.project_id || project.id,
      name: project.project_name || project.name,
      source_url: project.source_url || "",
      source_type: project.source_type || "upload",
      framework: Array.isArray(project.frameworks)
        ? project.frameworks.join(", ")
        : project.framework || "",
      language:
        project.language === "python"
          ? "Python"
          : project.language || "Unknown",
      status: project.status || "queued",
      quality: Number(project.overall_score || project.progress || 0),
      created_at: project.created_at,
    }));
  };

  const filteredProjects = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter((project) => {
      const haystack = [
        project.name,
        project.source_url,
        project.language,
        project.framework,
        project.status,
        project.source_type,
      ].join(" ").toLowerCase();
      return haystack.includes(needle);
    });
  }, [projects, query]);

  const loadProjects = async () => {
    try {
      setError("");
      const response = await getProjects();
      const cards = buildProjectCards(response.projects || []);

      setProjects(cards);

      if (cards.length && !selectedReport) {
        await openReport(cards[0].id);
      }
    } catch (err) {
      setError(err.userMessage || "Projects could not be loaded.");
      setProjects([]);
    }
  };

  const openReport = async (projectId) => {
    try {
      setLoadingReport(true);
      setError("");
      const response = await getReport(projectId);
      setSelectedReport(response.report);
    } catch (err) {
      setSelectedReport(null);
      setError(err.userMessage || "This project does not have an available report yet.");
    } finally {
      setLoadingReport(false);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  return (
    <>
      <div className="page-header">
        <p className="eyebrow">AI Project Workspace</p>

        <h2>Projects</h2>

        <p>Upload software projects, analyze GitHub repositories and reopen stored project analysis details.</p>
      </div>

      <div className="source-switch">
        <button
          className={sourceMode === "zip" ? "source-tab active" : "source-tab"}
          onClick={() => setSourceMode("zip")}
        >
          <PackageOpen size={17} />
          ZIP Upload
        </button>
        <button
          className={sourceMode === "github" ? "source-tab active" : "source-tab"}
          onClick={() => setSourceMode("github")}
        >
          <GitBranch size={17} />
          GitHub Repository
        </button>
      </div>

      <div className="dashboard-grid single-workflow">
        {sourceMode === "zip" ? <UploadPanel onAnalysisComplete={loadProjects} /> : <GithubPanel onAnalysisComplete={loadProjects} />}
      </div>

      <div className="section-heading" style={{ marginTop: "26px" }}>
        <div>
          <p className="eyebrow">Stored analyses</p>
          <h2>Project Archive</h2>
        </div>
        <button className="btn btn-ghost" onClick={loadProjects}>
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="project-search">
        <Search size={17} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search by project, repo URL, language, framework or status"
        />
      </div>

      {error && (
        <div className="card error-state">
          <strong>{error}</strong>
          <button className="btn btn-ghost" onClick={loadProjects}>
            Retry
          </button>
        </div>
      )}

      <div className="grid-4" style={{ marginTop: "14px" }}>
        {filteredProjects.map((project) => (
          <button
            key={project.id}
            className="project-card-button"
            onClick={() => openReport(project.id)}
          >
            <ProjectCard project={project} />
          </button>
        ))}
      </div>

      {!filteredProjects.length && (
        <div className="card empty-card">
          <h3>No matching projects</h3>
          <p>Try another search term or run a ZIP/GitHub analysis from the workflow above.</p>
        </div>
      )}

      {loadingReport && (
        <p className="muted-text" style={{ marginTop: "18px" }}>
          Loading stored analysis details...
        </p>
      )}

      {selectedReport && (
        <div style={{ marginTop: "28px" }}>
          <AnalysisResultPanel report={selectedReport} />
        </div>
      )}
    </>
  );
}
