import { useState } from "react";
import { changePassword, updateCurrentUser } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Profile() {
  const { user, setSession, session } = useAuth();
  const [profile, setProfile] = useState({
    full_name: user?.full_name || "",
    avatar_url: user?.avatar_url || "",
  });
  const [password, setPassword] = useState({ current_password: "", new_password: "" });
  const [message, setMessage] = useState("");

  const saveProfile = async (event) => {
    event.preventDefault();
    const result = await updateCurrentUser(profile);
    setSession({ ...session, user: result.user }, true);
    setMessage("Profile updated successfully.");
  };

  const savePassword = async (event) => {
    event.preventDefault();
    await changePassword(password);
    setPassword({ current_password: "", new_password: "" });
    setMessage("Password changed successfully.");
  };

  return (
    <div>
      <div className="page-header">
        <p className="eyebrow">Account</p>
        <h2>Profile</h2>
        <p>Manage your account details, password and workspace identity.</p>
      </div>

      {message && <div className="auth-message profile-message">{message}</div>}

      <div className="settings-grid">
        <form className="card settings-card auth-form" onSubmit={saveProfile}>
          <h3>Personal details</h3>
          <label>
            Full name
            <input
              value={profile.full_name}
              onChange={(event) => setProfile({ ...profile, full_name: event.target.value })}
            />
          </label>
          <label>
            Avatar URL
            <input
              value={profile.avatar_url}
              onChange={(event) => setProfile({ ...profile, avatar_url: event.target.value })}
              placeholder="https://..."
            />
          </label>
          <button className="btn btn-primary">Save profile</button>
        </form>

        <form className="card settings-card auth-form" onSubmit={savePassword}>
          <h3>Change password</h3>
          <label>
            Current password
            <input
              type="password"
              value={password.current_password}
              onChange={(event) => setPassword({ ...password, current_password: event.target.value })}
              required
            />
          </label>
          <label>
            New password
            <input
              type="password"
              minLength={8}
              value={password.new_password}
              onChange={(event) => setPassword({ ...password, new_password: event.target.value })}
              required
            />
          </label>
          <button className="btn btn-primary">Change password</button>
        </form>

        <div className="card settings-card">
          <h3>Account statistics</h3>
          <p>Email: {user?.email}</p>
          <p>Created: {user?.created_at ? new Date(user.created_at).toLocaleString() : "Unknown"}</p>
          <p>Last login: {user?.last_login_at ? new Date(user.last_login_at).toLocaleString() : "First session"}</p>
        </div>
      </div>
    </div>
  );
}
