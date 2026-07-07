import { Bell, Moon, Search, Sun } from "lucide-react";
import { useTheme } from "../../context/ThemeContext.jsx";

export default function Topbar() {
  const { theme, toggleTheme } = useTheme();

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

        <div className="avatar">JP</div>
      </div>
    </header>
  );
}