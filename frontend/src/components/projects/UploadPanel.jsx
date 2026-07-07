import { useRef, useState } from "react";
import { CheckCircle2, Loader2, Play, UploadCloud } from "lucide-react";
import { analyzeProject, uploadProjectZip } from "../../api/client";
import AnalysisResultPanel from "../analysis/AnalysisResultPanel";

export default function UploadPanel() {
  const inputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [status, setStatus] = useState("idle");
  const [message, setMessage] = useState("");
  const [summary, setSummary] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState("idle");
  const [analysisReport, setAnalysisReport] = useState(null);

  const handleChoose = () => inputRef.current?.click();

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".zip")) {
      setStatus("error");
      setMessage("Please select a valid ZIP file.");
      setSummary(null);
      setAnalysisReport(null);
      return;
    }

    setSelectedFile(file);
    setStatus("selected");
    setMessage(`${file.name} selected`);
    setSummary(null);
    setAnalysisReport(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setStatus("error");
      setMessage("Choose a ZIP project first.");
      return;
    }

    try {
      setStatus("uploading");
      setMessage("Uploading and extracting project...");
      setSummary(null);
      setAnalysisReport(null);

      const result = await uploadProjectZip(selectedFile);

      if (!result.success) {
        setStatus("error");
        setMessage(result.message || "Upload failed.");
        return;
      }

      setStatus("success");
      setMessage(result.message || "Project uploaded successfully.");
      setSummary(result);
    } catch (error) {
      setStatus("error");
      setMessage(error.userMessage || "Upload failed. Check the backend connection.");
      setSummary(null);
    }
  };

  const handleAnalyze = async () => {
    if (!summary?.project_id) {
      setAnalysisStatus("error");
      return;
    }

    try {
      setAnalysisStatus("running");
      setAnalysisReport(null);

      const result = await analyzeProject(summary.project_id);

      if (!result.success) {
        setAnalysisStatus("error");
        return;
      }

      setAnalysisStatus("success");
      setAnalysisReport(result.report);
    } catch (error) {
      setAnalysisStatus("error");
      setMessage(error.userMessage || "Analysis failed. Check the backend connection.");
    }
  };

  return (
    <div className="card upload-panel">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Upload source code</p>
          <h2>Upload Project</h2>
        </div>
      </div>

      <div className={`upload-area ${status}`}>
        {status === "uploading" ? (
          <Loader2 className="spin" size={48} />
        ) : status === "success" ? (
          <CheckCircle2 size={48} />
        ) : (
          <UploadCloud size={48} />
        )}

        <h3>Drag & Drop ZIP Project</h3>
        <p>{message || "Upload a ZIP archive containing your software project."}</p>

        <input ref={inputRef} type="file" accept=".zip" hidden onChange={handleFileChange} />

        <div className="upload-actions">
          <button className="btn btn-ghost" onClick={handleChoose}>
            Choose ZIP
          </button>

          <button className="btn btn-primary" onClick={handleUpload}>
            Upload Project
          </button>
        </div>

        {summary && (
          <>
            <div className="upload-summary">
              <div><span>Language</span><strong>{summary.language}</strong></div>
              <div><span>Total files</span><strong>{summary.total_files}</strong></div>
              <div><span>Python</span><strong>{summary.python_files}</strong></div>
              <div><span>JavaScript</span><strong>{summary.javascript_files}</strong></div>
            </div>

            <button
              className="btn btn-primary analyze-btn"
              onClick={handleAnalyze}
              disabled={analysisStatus === "running"}
            >
              {analysisStatus === "running" ? (
                <>
                  <Loader2 className="spin" size={17} />
                  Running Agents...
                </>
              ) : (
                <>
                  <Play size={17} />
                  Run Multi-Agent Analysis
                </>
              )}
            </button>
          </>
        )}

        {analysisStatus === "error" && (
          <p className="upload-error">{message || "Analysis failed. Check the backend connection."}</p>
        )}

        <AnalysisResultPanel report={analysisReport} />
      </div>
    </div>
  );
}
