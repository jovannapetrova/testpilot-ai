import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { compareReports } from "../../api/client";
import ErrorState from "../ui/ErrorState";

const metricConfig = [
  { key: "overall_score", deltaKey: "overall", label: "Overall Score" },
  { key: "quality_score", deltaKey: "quality", label: "Quality Score" },
  { key: "security_score", deltaKey: "security", label: "Security Score" },
  { key: "test_score", deltaKey: "testing", label: "Testing Score" },
];

function numericValue(value) {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? Math.round(number * 100) / 100 : null;
}

function formatValue(value) {
  const number = numericValue(value);
  return number === null ? "N/A" : `${number}`;
}

function reportLabel(report, other) {
  const name = report?.project_name || "Unnamed report";
  const otherName = other?.project_name || "Unnamed report";
  if (name === otherName && report?.project_id) {
    return `${name} (${String(report.project_id).slice(0, 8)})`;
  }
  return name;
}

function fallbackRows(result, firstReport, secondReport) {
  return metricConfig.map((metric) => {
    const firstValue = numericValue(firstReport?.[metric.key]);
    const secondValue = numericValue(secondReport?.[metric.key]);
    const delta = numericValue(result?.delta?.[metric.deltaKey]);
    if (firstValue === null || secondValue === null || delta === null) {
      return {
        key: metric.key,
        label: metric.label,
        first_value: firstValue,
        second_value: secondValue,
        direction: "missing",
        absolute_delta: null,
        summary: `${metric.label} is unavailable for one or both reports.`,
      };
    }

    const direction = delta > 0 ? "second_higher" : delta < 0 ? "second_lower" : "equal";
    return {
      key: metric.key,
      label: metric.label,
      first_value: firstValue,
      second_value: secondValue,
      direction,
      absolute_delta: Math.abs(delta),
    };
  });
}

function directionMeta(direction) {
  if (direction === "second_higher") {
    return { Icon: ArrowUpRight, className: "positive", label: "Second report is higher" };
  }
  if (direction === "second_lower") {
    return { Icon: ArrowDownRight, className: "negative", label: "Second report is lower" };
  }
  if (direction === "equal") {
    return { Icon: Minus, className: "neutral", label: "Reports are equal" };
  }
  return { Icon: Minus, className: "missing", label: "Metric unavailable" };
}

function rowSummary(row, firstLabel, secondLabel) {
  if (row.summary) return row.summary;
  if (row.direction === "missing") return `${row.label} is unavailable for one or both reports.`;
  const amount = formatValue(row.absolute_delta);
  if (row.direction === "second_higher") return `${secondLabel} is ${amount} points higher than ${firstLabel}.`;
  if (row.direction === "second_lower") return `${secondLabel} is ${amount} points lower than ${firstLabel}.`;
  return `${firstLabel} and ${secondLabel} are equal for ${row.label.toLowerCase()}.`;
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
        <>
          {(() => {
            const firstReport = result.first || reports.find((report) => report.project_id === first);
            const secondReport = result.second || reports.find((report) => report.project_id === second);
            const firstLabel = result.first_label || reportLabel(firstReport, secondReport);
            const secondLabel = result.second_label || reportLabel(secondReport, firstReport);
            const rows = result.metrics?.length ? result.metrics : fallbackRows(result, firstReport, secondReport);

            return (
              <div className="compare-output">
                <div className="compare-baseline">
                  <div>
                    <span>First report</span>
                    <strong>{firstLabel}</strong>
                  </div>
                  <div>
                    <span>Second report</span>
                    <strong>{secondLabel}</strong>
                  </div>
                </div>

                <div className="compare-result">
                  {rows.map((row) => {
                    const { Icon, className, label } = directionMeta(row.direction);
                    return (
                      <div className={`compare-metric ${className}`} key={row.key || row.label}>
                        <div className="compare-metric-head">
                          <span>{row.label}</span>
                          <span className={`compare-direction ${className}`} aria-label={label}>
                            <Icon size={16} aria-hidden="true" />
                          </span>
                        </div>
                        <div className="compare-values">
                          <span>{firstLabel}: {formatValue(row.first_value)}</span>
                          <span>{secondLabel}: {formatValue(row.second_value)}</span>
                        </div>
                        <strong>{row.direction === "missing" ? "N/A" : formatValue(row.absolute_delta)}</strong>
                        <p>{rowSummary(row, firstLabel, secondLabel)}</p>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}
        </>
      )}
    </div>
  );
}
