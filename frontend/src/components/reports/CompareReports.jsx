import { useState } from "react";
import { compareReports } from "../../api/client";

export default function CompareReports({ reports = [] }) {
  const [first, setFirst] = useState("");
  const [second, setSecond] = useState("");
  const [result, setResult] = useState(null);

  const runCompare = async () => {
    if (!first || !second || first === second) return;
    const data = await compareReports(first, second);
    setResult(data.comparison);
  };

  return (
    <div className="card compare-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Project comparison</p>
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

        <button className="btn btn-primary" onClick={runCompare}>
          Compare
        </button>
      </div>

      {result && (
        <div className="compare-result">
          <div><span>Overall Δ</span><strong>{result.delta.overall}</strong></div>
          <div><span>Quality Δ</span><strong>{result.delta.quality}</strong></div>
          <div><span>Security Δ</span><strong>{result.delta.security}</strong></div>
          <div><span>Testing Δ</span><strong>{result.delta.testing}</strong></div>
        </div>
      )}
    </div>
  );
}