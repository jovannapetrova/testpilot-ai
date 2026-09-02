import { LogOut, Moon, Sun } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { useTheme } from "../../context/ThemeContext.jsx";

const pageMeta = {
  "/dashboard": ["Dashboard", "Account-level quality intelligence"],
  "/projects": ["Projects", "Analyze repositories and track active jobs"],
  "/reports": ["Reports", "Completed analysis evidence and exports"],
  "/agents": ["AI Agents", "Multi-agent analysis pipeline"],
  "/profile": ["Profile", "Account identity and password"],
  "/settings": ["Settings", "Workspace preferences and system health"],
};

export default function Topbar() {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [title, subtitle] = pageMeta[location.pathname] || ["TestPilot AI Console", "Software quality workspace"];

  const initials = (user?.full_name || user?.email || "TP")
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <header className="topbar">
      <div>
        <p className="eyebrow">{subtitle}</p>
        <h1>{title}</h1>
      </div>

      <div className="topbar-actions">
        <button className="icon-btn" onClick={toggleTheme} title="Switch theme">
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <button className="icon-btn" onClick={handleLogout} title="Log out">
          <LogOut size={18} />
        </button>

        <button className="avatar avatar-button" onClick={() => navigate("/profile")}>
          {initials}
        </button>
      </div>
    </header>
  );
}
