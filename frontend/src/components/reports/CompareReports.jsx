import { useState } from "react";
import { compareReports } from "../../api/client";
import ErrorState from "../ui/ErrorState";

function deltaLabel(value) {
  const number = Number(value || 0);
  if (number > 0) return `+${number}`;
  return `${number}`;
}

export default function CompareReports({ reports = [], onMessage }) {
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const runCompare = async () => {
    setError("");
    setResult(null);

    if (!first || !second) {
      setError("Select two reports before comparing.");
      return;
    }
    if (first === second) {
      setError("Choose two different reports to compare.");
      return;
    }

    try {
      setLoading(true);
      const data = await compareReports(first, second);
      setResult(data.comparison);
      onMessage?.("Reports compared successfully.");
    } catch (err) {
      setError(err.userMessage || "Unable to compare these reports.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card compare-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Evidence comparison</p>
          <h2>Compare Reports</h2>
        </div>
      </div>

      <div className="compare-controls">
        <select value={first} onChange={(e) => setFirst(e.target.value)}>
          <option value="">First report</option>
          {reports.map((r) => (
            <option key={r.project_id} value={r.project_id}>{r.project_name}</option>
          ))}
        </select>

        <select value={second} onChange={(e) => setSecond(e.target.value)}>
          <option value="">Second report</option>
          {reports.map((r) => (
            <option key={r.project_id} value={r.project_id}>{r.project_name}</option>
          ))}
        </select>

        <button className="btn btn-primary" onClick={runCompare} disabled={loading}>
          {loading ? "Comparing..." : "Compare"}
        </button>
      </div>

      {error ? <ErrorState title="Comparison unavailable" message={error} /> : null}

      {result && (
        <div className="compare-result">
          <div><span>Overall delta</span><strong>{deltaLabel(result.delta.overall)}</strong></div>
          <div><span>Quality delta</span><strong>{deltaLabel(result.delta.quality)}</strong></div>
          <div><span>Security delta</span><strong>{deltaLabel(result.delta.security)}</strong></div>
          <div><span>Testing delta</span><strong>{deltaLabel(result.delta.testing)}</strong></div>
        </div>
      )}
    </div>
  );
}
