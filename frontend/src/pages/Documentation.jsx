import { Link } from "react-router-dom";

export default function Documentation() {
  return (
    <main className="landing content-page">
      <nav className="landing-nav">
        <Link to="/" className="btn btn-ghost">Back</Link>
        <Link to="/login" className="btn btn-primary">Sign in</Link>
      </nav>
      <section className="page-header">
        <p className="eyebrow">Documentation</p>
        <h2>How TestPilot AI works</h2>
        <p>
          Upload a ZIP or analyze a GitHub repository, track progress in the project archive,
          review generated findings, and export PDF, JSON, CSV or Markdown reports from your private workspace.
        </p>
      </section>
    </main>
  );
}
