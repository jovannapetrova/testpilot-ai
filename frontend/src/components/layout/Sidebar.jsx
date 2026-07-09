import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FolderGit2,
  Bot,
  FileText,
  Settings,
  ShieldCheck,
  GitBranch,
  GitCompare,
  UserCircle,
} from "lucide-react";

const links = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/projects", label: "Projects", icon: FolderGit2 },
  { to: "/github", label: "GitHub Analysis", icon: GitBranch },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/comparison", label: "Comparison", icon: GitCompare },
  { to: "/agents", label: "AI Agents", icon: Bot },
  { to: "/profile", label: "Profile", icon: UserCircle },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">
          <ShieldCheck size={24} />
        </div>
        <div>
          <h2>TestPilot AI</h2>
          <p>Multi-Agent QA Platform</p>
        </div>
      </div>

      <nav className="nav">
        {links.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <Icon size={19} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
