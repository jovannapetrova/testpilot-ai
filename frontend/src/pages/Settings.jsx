import { useEffect, useState } from "react";
import { AlertTriangle, Moon, RefreshCw, Sun } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import { API_BASE_URL, deleteCurrentUser, getHealth } from "../api/client";
import { useAuth } from "../context/AuthContext";
import ConfirmDialog from "../components/ui/ConfirmDialog";
import Toast from "../components/ui/Toast";

export default function Settings() {
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState("");

  const loadHealth = async () => {
    try {
      setCheckingHealth(true);
      setHealthError("");
      const result = await getHealth();
      setHealth(result);
    } catch (error) {
      setHealth(null);
      setHealthError(error.userMessage || "Unable to verify backend health.");
    } finally {
      setCheckingHealth(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  const handleDeleteAccount = async () => {
    try {
      setDeleting(true);
      await deleteCurrentUser();
      await logout();
      navigate("/register", { replace: true });
    } catch (error) {
      setToast(error.userMessage || "Unable to delete your account right now.");
    } finally {
      setDeleting(false);
      setConfirmOpen(false);
    }
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
            {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            Switch to {theme === "dark" ? "Light" : "Dark"} Mode
          </button>
        </div>

        <div className="card settings-card">
          <h3>Backend API</h3>
          <p>FastAPI backend: {API_BASE_URL}</p>
          <span className={`status-badge ${health ? "success" : healthError ? "failed" : "running"}`}>
            <span className="status-dot" />
            {health ? "Healthy" : healthError ? "Unavailable" : "Checking"}
          </span>
          {health?.version ? <p>Version: {health.version}</p> : null}
          <button className="btn btn-ghost" onClick={loadHealth} disabled={checkingHealth}>
            <RefreshCw size={17} className={checkingHealth ? "spin" : ""} />
            Check health
          </button>
          {healthError ? <p className="inline-error">Health check failed: {healthError}</p> : null}
        </div>

        <div className="card settings-card">
          <h3>AI Engine</h3>
          <p>
            Multi-agent analysis pipeline with project detection, dependency
            analysis, security checks, quality scoring and report generation.
          </p>
          <span className="status-badge success">
            <span className="status-dot" />
            Configured
          </span>
        </div>

        <div className="card settings-card">
          <h3>Report Storage</h3>
          <p>Reports are persisted per user and can be exported as PDF, JSON, CSV and Markdown.</p>
          <span className="status-badge success">
            <span className="status-dot" />
            Database-backed
          </span>
        </div>

        <div className="card settings-card danger-zone">
          <h3>Danger Zone</h3>
          <p>Delete your account, projects, reports and stored analysis history.</p>
          <button className="btn btn-danger" onClick={() => setConfirmOpen(true)}>
            <AlertTriangle size={17} />
            Delete Account
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Delete account permanently?"
        message="This removes your account, projects, reports, generated exports and analysis history. This action cannot be undone."
        confirmLabel="Delete account"
        danger
        loading={deleting}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={handleDeleteAccount}
      />

      <Toast message={toast} tone="error" onClose={() => setToast("")} />
    </div>
  );
}
