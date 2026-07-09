import { useState } from "react";

export default function GeneratedTestsList({ tests = [], metadata = {} }) {
  const humanDesign = metadata.needs_human_test_design || [];
  const skippedReasons = metadata.skipped_generation_reasons || {};
  const [expanded, setExpanded] = useState({});

  if (!tests.length && !humanDesign.length) {
    return <p className="muted-text">No generated tests available yet.</p>;
  }

  return (
    <div className="detail-list">
      {tests.slice(0, 5).map((test, index) => (
        <div className="test-row" key={`${test.file}-${index}`}>
          <div className="test-row-header">
            <strong>{test.target}</strong>
            <div className="test-actions">
              <button
                className="copy-code-btn"
                onClick={() => setExpanded((current) => ({
                  ...current,
                  [`${test.file}-${index}`]: !current[`${test.file}-${index}`],
                }))}
              >
                {expanded[`${test.file}-${index}`] ? "Collapse" : "Expand"}
              </button>
              <button
                className="copy-code-btn"
                onClick={() => navigator.clipboard?.writeText(test.test_code || "")}
              >
                Copy
              </button>
            </div>
          </div>
          <p>
            {test.test_type || "unit"} | confidence: {test.confidence || "medium"}
            {test.framework ? ` | ${test.framework}` : ""}
            {` | category: ${test.generated_test_category || test.test_type || "unit"}`}
            {` | assertions: ${test.assertion_strength || "medium"}`}
            {` | safety: ${test.execution_safety || "safe"}`}
            {test.test_type === "smoke" ? " | smoke" : " | executable"}
          </p>
          <p>{test.rationale}</p>
          {expanded[`${test.file}-${index}`] ? (
            <pre>{test.test_code}</pre>
          ) : (
            <div className="code-collapsed">Code collapsed. Expand to inspect generated test source.</div>
          )}
        </div>
      ))}

      {humanDesign.length ? (
        <div className="detail-row">
          <div>
            <strong>Targets requiring human test design</strong>
            {humanDesign.slice(0, 8).map((item) => (
              <p key={`${item.target}-${item.signature}-${item.reason}`}>
                {item.target}: {item.reason}
              </p>
            ))}
          </div>
          <span className="severity medium">{humanDesign.length}</span>
        </div>
      ) : null}

      {Object.keys(skippedReasons).length ? (
        <div className="detail-row">
          <div>
            <strong>Skipped generation reasons</strong>
            {Object.entries(skippedReasons).slice(0, 6).map(([reason, count]) => (
              <p key={reason}>{reason}: {count}</p>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
