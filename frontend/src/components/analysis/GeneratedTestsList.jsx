import { useMemo, useState } from "react";
import Toast from "../ui/Toast";

const pageSize = 5;

export default function GeneratedTestsList({ tests = [], metadata = {} }) {
  const humanDesign = Array.isArray(metadata.needs_human_test_design)
    ? metadata.needs_human_test_design
    : [];
  const humanDesignCount = Array.isArray(metadata.needs_human_test_design)
    ? metadata.needs_human_test_design.length
    : Number(metadata.needs_human_test_design || 0);
  const skippedReasons = metadata.skipped_generation_reasons || {};
  const executionDisabled = metadata.execution_enabled === false || metadata.execution_status === "disabled";
  const [expanded, setExpanded] = useState({});
  const [page, setPage] = useState(0);
  const [toast, setToast] = useState("");

  const pageCount = Math.max(1, Math.ceil(tests.length / pageSize));
  const visibleTests = useMemo(
    () => tests.slice(page * pageSize, page * pageSize + pageSize),
    [page, tests],
  );

  if (!tests.length && !humanDesignCount) {
    return <p className="muted-text">No executable generated test candidates were inferred for this report.</p>;
  }

  const toggleAll = (open) => {
    const next = {};
    visibleTests.forEach((test, index) => {
      next[`${test.file}-${page}-${index}`] = open;
    });
    setExpanded((current) => ({ ...current, ...next }));
  };

  const copyTest = async (testCode) => {
    await navigator.clipboard?.writeText(testCode || "");
    setToast("Test copied to clipboard.");
  };

  return (
    <div className="detail-list">
      {tests.length ? (
        <div className="test-list-controls">
          <div className="pagination-controls">
            <button type="button" className="copy-code-btn" onClick={() => toggleAll(true)}>Expand visible</button>
            <button type="button" className="copy-code-btn" onClick={() => toggleAll(false)}>Collapse visible</button>
          </div>
          <div className="pagination-controls">
            <button
              type="button"
              className="copy-code-btn"
              disabled={page === 0}
              onClick={() => setPage((current) => current - 1)}
            >
              Previous
            </button>
            <span className="muted-text">Page {page + 1} of {pageCount}</span>
            <button
              type="button"
              className="copy-code-btn"
              disabled={page + 1 >= pageCount}
              onClick={() => setPage((current) => current + 1)}
            >
              Next
            </button>
          </div>
        </div>
      ) : null}

      {visibleTests.map((test, index) => {
        const key = `${test.file}-${page}-${index}`;
        return (
          <div className="test-row" key={key}>
            <div className="test-row-header">
              <strong>{test.target}</strong>
              <div className="test-actions">
                <button
                  type="button"
                  className="copy-code-btn"
                  onClick={() => setExpanded((current) => ({
                    ...current,
                    [key]: !current[key],
                  }))}
                >
                  {expanded[key] ? "Collapse" : "Expand"}
                </button>
                <button
                  type="button"
                  className="copy-code-btn"
                  onClick={() => copyTest(test.test_code || "")}
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
              {` | readiness: ${test.execution_readiness || (test.needs_review ? "needs human design" : "ready to execute")}`}
              {test.executed
                ? ` | executed: ${test.passed || 0} passed, ${test.failed || 0} failed`
                : executionDisabled
                  ? " | execution: not executed (disabled)"
                  : " | execution: not executed"}
            </p>
            <p>{test.rationale}</p>
            {expanded[key] ? (
              <pre>{test.test_code}</pre>
            ) : (
              <div className="code-collapsed">Code collapsed. Expand to inspect generated test source.</div>
            )}
          </div>
        );
      })}

      {humanDesignCount ? (
        <div className="detail-row">
          <div>
            <strong>Targets requiring human test design</strong>
            {humanDesign.length ? humanDesign.slice(0, 8).map((item) => (
              <p key={`${item.target}-${item.signature}-${item.reason}`}>
                {item.target}: {item.reason}
              </p>
            )) : <p>Some targets require project-specific fixtures or domain knowledge before safe test generation.</p>}
          </div>
          <span className="severity medium">{humanDesignCount}</span>
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

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
