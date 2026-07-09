import { useMemo } from "react";

export default function SecurityFindingsList({ findings = [] }) {
  const groupedFindings = useMemo(() => {
    const map = new Map();

    findings.forEach((item) => {
      const key = item.fingerprint || `${item.issue}-${item.severity}-${item.context}-${item.file}`;

      if (!map.has(key)) {
        map.set(key, {
          ...item,
          count: item.occurrences || 1,
          lines: item.line ? [item.line] : [],
        });
      } else {
        const existing = map.get(key);
        existing.count += item.occurrences || 1;
        if (item.line) existing.lines.push(item.line);
      }
    });

    return Array.from(map.values());
  }, [findings]);

  if (!findings.length) {
    return <p className="muted-text">No security findings detected.</p>;
  }

  return (
    <div className="detail-list">
      {groupedFindings.map((item, index) => (
        <div className="detail-row" key={`${item.fingerprint || item.file}-${index}`}>
          <div>
            <strong>{item.issue}</strong>
            <p>
              {item.file} | {item.context || "production"} | confidence: {item.confidence || "medium"}
              {` | false-positive likelihood: ${item.false_positive_likelihood || "medium"}`}
              {item.count ? ` | ${item.count} occurrence(s)` : ""}
            </p>
            {item.impact ? <p>{item.impact}</p> : null}
            {item.remediation ? <p>{item.remediation}</p> : null}
            {item.evidence ? <p>Evidence: {item.evidence}</p> : null}
            {item.affected_files?.length ? (
              <p>Affected files: {item.affected_files.slice(0, 3).join(", ")}</p>
            ) : null}
          </div>

          <span className={`severity ${item.severity}`}>
            {item.severity} x {item.count}
          </span>
        </div>
      ))}
    </div>
  );
}
