import { useTheme } from "../context/ThemeContext";

export default function Settings() {
  const { theme, toggleTheme } = useTheme();

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
          <p>FastAPI backend is expected at http://127.0.0.1:8000.</p>
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
          <p>Reports can be exported as PDF, JSON, CSV and Markdown.</p>
          <span className="status-badge success">
            <span className="status-dot" />
            Enabled
          </span>
        </div>
      </div>
    </div>
  );
}