import { Link } from "react-router-dom";

export default function About() {
  return (
    <main className="landing content-page">
      <nav className="landing-nav">
        <Link to="/" className="btn btn-ghost">Back</Link>
        <Link to="/register" className="btn btn-primary">Create account</Link>
      </nav>
      <section className="page-header">
        <p className="eyebrow">About</p>
        <h2>Enterprise software quality intelligence</h2>
        <p>
          TestPilot AI combines project detection, security review, maintainability analysis,
          test generation, coverage intelligence and professional reporting in one authenticated workspace.
        </p>
      </section>
    </main>
  );
}
