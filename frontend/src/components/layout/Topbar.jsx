import { Bell, LogOut, Moon, Search, Sun } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext.jsx";
import { useTheme } from "../../context/ThemeContext.jsx";

export default function Topbar() {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
        <p className="eyebrow">AI-powered software quality assurance</p>
        <h1>TestPilot AI Console</h1>
      </div>

      <div className="topbar-actions">
        <div className="search-box">
          <Search size={17} />
          <input placeholder="Search projects, agents, reports..." />
        </div>

        <button className="icon-btn">
          <Bell size={18} />
        </button>

        <button className="icon-btn" onClick={toggleTheme}>
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
