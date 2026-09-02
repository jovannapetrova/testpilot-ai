import { Link } from "react-router-dom";
import {
  Bot,
  Code2,
  FileText,
  GitBranch,
  ShieldCheck,
  Sparkles,
  TestTube2,
} from "lucide-react";

const features = [
  {
    icon: Bot,
    title: "Multi-Agent Orchestration",
    text: "Coordinated AI agents analyze code, security, testing and reporting workflows.",
  },
  {
    icon: TestTube2,
    title: "Generated Test Candidates",
    text: "Create executable candidate tests and separate targets that require human fixture design.",
  },
  {
    icon: ShieldCheck,
    title: "Security Analysis",
    text: "Detect suspicious patterns, hardcoded secrets and common security risks.",
  },
  {
    icon: FileText,
    title: "Audit-Ready Reports",
    text: "Export structured PDF, JSON, CSV and Markdown reports for review and presentation.",
  },
];

export default function Landing() {
  return (
    <main className="landing">
      <nav className="landing-nav">
        <div className="brand compact">
          <div className="brand-icon">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h2>TestPilot AI</h2>
            <p>Software QA Agents</p>
          </div>
        </div>

        <div className="landing-links">
          <Link to="/about">About</Link>
          <Link to="/docs">Docs</Link>
          <Link to="/login" className="btn btn-ghost">
            Sign in
          </Link>
        </div>
      </nav>

      <section className="hero card">
        <div className="hero-content">
          <div className="hero-badge">
            <Sparkles size={16} />
            AI-powered multi-agent QA platform
          </div>

          <h1>
            Analyze software projects with specialized AI quality agents.
          </h1>

          <p>
            TestPilot AI helps analyze software projects, generate tests,
            identify quality risks and produce professional reports through an
            orchestrated multi-agent workflow.
          </p>

          <div className="hero-actions">
            <Link to="/projects" className="btn btn-primary">
              Analyze a Project
            </Link>
            <Link to="/docs" className="btn btn-ghost">
              View Documentation
            </Link>
          </div>
        </div>

        <div className="hero-panel">
          <div className="capability-panel">
            <div>
              <ShieldCheck size={20} />
              <strong>Security Analysis</strong>
              <span>Severity, confidence, context and remediation.</span>
            </div>
            <div>
              <Code2 size={20} />
              <strong>Code Quality</strong>
              <span>Maintainability, complexity and production hotspots.</span>
            </div>
            <div>
              <TestTube2 size={20} />
              <strong>Testing Intelligence</strong>
              <span>Generated candidates, smoke tests and human-design targets.</span>
            </div>
            <div>
              <GitBranch size={20} />
              <strong>Repository Analysis</strong>
              <span>ZIP uploads and public GitHub repositories.</span>
            </div>
          </div>
        </div>
      </section>

      <section className="features-grid">
        {features.map((feature) => {
          const Icon = feature.icon;

          return (
            <div className="feature-card card" key={feature.title}>
              <div className="feature-icon">
                <Icon size={22} />
              </div>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
            </div>
          );
        })}
      </section>
      <footer className="landing-footer">
        TestPilot AI protects each user workspace with JWT authentication and user-scoped report history.
      </footer>
    </main>
  );
}
