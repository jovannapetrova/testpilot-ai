import { GitBranch, PackageOpen } from "lucide-react";
import StatusBadge from "../ui/StatusBadge";

function statusFor(projectStatus) {
  if (projectStatus === "completed") return "completed";
  if (projectStatus === "failed") return "failed";
  if (projectStatus === "running") return "analyzing";
  return "queued";
}

export default function ProjectCard({ project }) {
  const isCompleted = project.status === "completed";
  const SourceIcon = project.source_type === "github" ? GitBranch : PackageOpen;

  return (
    <div className="card project-card">
      <div className="project-card-header">
        <div className="project-source-icon">
          <SourceIcon size={18} />
        </div>
        <StatusBadge status={statusFor(project.status)} />
      </div>

      <h3>{project.name}</h3>
      <p>{project.language || "Unknown language"}</p>
      {project.framework ? <p>{project.framework}</p> : null}

      {["queued", "running"].includes(project.status) ? (
        <div className="project-progress">
          <div className="progress-header">
            <span>{project.progress || 0}%</span>
            <strong>{project.current_stage || "Queued"}</strong>
          </div>
          <div className="progress-track compact">
            <div className="progress-fill" style={{ width: `${project.progress || 0}%` }} />
          </div>
        </div>
      ) : null}

      {project.status === "failed" ? (
        <p className="project-error">{project.error || "Analysis failed."}</p>
      ) : null}

      <div className="project-card-footer">
        <span>{project.source_type === "github" ? "GitHub" : "ZIP Upload"}</span>
        <strong>{isCompleted ? `${Math.round(project.quality || 0)}/100` : "Report pending"}</strong>
      </div>
    </div>
  );
}
