import { useState } from "react";
import { changePassword, updateCurrentUser } from "../api/client";
import { useAuth } from "../context/AuthContext";
import Toast from "../components/ui/Toast";
import ErrorState from "../components/ui/ErrorState";

export default function Profile() {
  const { user, setSession, session } = useAuth();
  const [profile, setProfile] = useState({
    full_name: user?.full_name || "",
  });
  const [password, setPassword] = useState({ current_password: "", new_password: "" });
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  const saveProfile = async (event) => {
    event.preventDefault();
    try {
      setSavingProfile(true);
      setError("");
      const result = await updateCurrentUser({ full_name: profile.full_name });
      setSession({ ...session, user: result.user }, session?.remember_me ?? true);
      setToast("Profile updated successfully.");
    } catch (err) {
      setError(err.userMessage || "Unable to update your profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const savePassword = async (event) => {
    event.preventDefault();
    try {
      setSavingPassword(true);
      setError("");
      await changePassword(password);
      setPassword({ current_password: "", new_password: "" });
      setToast("Password changed successfully.");
    } catch (err) {
      setError(err.userMessage || "Unable to change your password.");
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <p className="eyebrow">Account</p>
        <h2>Profile</h2>
        <p>Manage your account details, password and workspace identity.</p>
      </div>

      {error ? <ErrorState title="Account update failed" message={error} /> : null}

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
          <button className="btn btn-primary" disabled={savingProfile}>
            {savingProfile ? "Saving profile..." : "Save profile"}
          </button>
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
          <button className="btn btn-primary" disabled={savingPassword}>
            {savingPassword ? "Changing password..." : "Change password"}
          </button>
        </form>

        <div className="card settings-card">
          <h3>Account statistics</h3>
          <p>Email: {user?.email}</p>
          <p>Created: {user?.created_at ? new Date(user.created_at).toLocaleString() : "Unknown"}</p>
          <p>Last login: {user?.last_login_at ? new Date(user.last_login_at).toLocaleString() : "First session"}</p>
        </div>
      </div>

      <Toast message={toast} onClose={() => setToast("")} />
    </div>
  );
}
