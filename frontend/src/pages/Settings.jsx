import { useTheme } from "../context/ThemeContext";
import { API_BASE_URL, deleteCurrentUser } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Settings() {
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuth();

  const handleDeleteAccount = async () => {
    const confirmed = window.confirm("Delete your account and all owned reports permanently?");
    if (!confirmed) return;
    await deleteCurrentUser();
    await logout();
    window.location.href = "/register";
  };

  return (
    <div>
      <div className="page-header">
        <p className="eyebrow">Production configuration</p>
        <h2>Settings</h2>
        <p>Configure workspace appearance and platform runtime settings.</p>
      </div>

      <div className="settings-grid">
        <div className="card settings-card">
          <h3>Appearance</h3>
          <p>
            Current theme: <strong>{theme}</strong>
          </p>

          <button className="btn btn-primary" onClick={toggleTheme}>
            Switch to {theme === "dark" ? "Light" : "Dark"} Mode
          </button>
        </div>

        <div className="card settings-card">
          <h3>Backend API</h3>
          <p>FastAPI backend: {API_BASE_URL}</p>
          <span className="status-badge success">
            <span className="status-dot" />
            Connected
          </span>
        </div>

        <div className="card settings-card">
          <h3>AI Engine</h3>
          <p>
            Multi-agent analysis pipeline with project detection, dependency
            analysis, security checks, quality scoring and report generation.
          </p>
          <span className="status-badge running">
            <span className="status-dot" />
            Ready
          </span>
        </div>

        <div className="card settings-card">
          <h3>Report Storage</h3>
          <p>Reports are persisted per user and can be exported as PDF, JSON, CSV and Markdown.</p>
          <span className="status-badge success">
            <span className="status-dot" />
            Enabled
          </span>
        </div>

        <div className="card settings-card">
          <h3>Account Security</h3>
          <p>Delete your account, projects, reports and stored analysis history.</p>
          <button className="btn btn-danger" onClick={handleDeleteAccount}>
            Delete Account
          </button>
        </div>
      </div>
    </div>
  );
}
