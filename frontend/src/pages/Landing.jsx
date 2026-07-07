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
    title: "Automated Test Generation",
    text: "Generate test scenarios, edge cases and structured QA recommendations.",
  },
  {
    icon: ShieldCheck,
    title: "Security Analysis",
    text: "Detect suspicious patterns, hardcoded secrets and common security risks.",
  },
  {
    icon: FileText,
    title: "Audit-Ready Reports",
    text: "Export structured PDF and JSON reports for documentation and presentation.",
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

        <Link to="/dashboard" className="btn btn-ghost">
          Open Console
        </Link>
      </nav>

      <section className="hero card">
        <div className="hero-content">
          <div className="hero-badge">
            <Sparkles size={16} />
            AI-powered multi-agent QA platform
          </div>

          <h1>
            Automate software testing, security analysis and quality evaluation
            with AI agents.
          </h1>

          <p>
            TestPilot AI helps analyze software projects, generate tests,
            identify quality risks and produce professional reports through an
            orchestrated multi-agent workflow.
          </p>

          <div className="hero-actions">
            <Link to="/dashboard" className="btn btn-primary">
              Get Started
            </Link>
            <Link to="/projects" className="btn btn-ghost">
              Analyze Project
            </Link>
          </div>
        </div>

        <div className="hero-panel">
          <div className="terminal-card">
            <div className="terminal-dots">
              <span />
              <span />
              <span />
            </div>
            <pre>{`> TestPilot Manager Agent started
> Code Analyzer Agent completed
> Security Agent completed
> Test Generator Agent running
> Quality report ready`}</pre>
          </div>

          <div className="hero-stats">
            <div>
              <Code2 size={20} />
              <strong>42</strong>
              <span>Generated tests</span>
            </div>
            <div>
              <GitBranch size={20} />
              <strong>3</strong>
              <span>Projects analyzed</span>
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
    </main>
  );
}