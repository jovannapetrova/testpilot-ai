import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { resetPassword } from "../api/client";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    if (!token) {
      setMessage("This reset link is missing a token. Request a new reset link.");
      return;
    }

    setLoading(true);
    setMessage("");
    try {
      const result = await resetPassword({ token, new_password: newPassword });
      setSuccess(true);
      setMessage(result.message || "Password reset successfully.");
      setTimeout(() => navigate("/login"), 1200);
    } catch (error) {
      setMessage(error.userMessage || "Unable to reset your password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-brand">
          <span><ShieldCheck size={24} /></span>
          <div>
            <h1>Choose new password</h1>
            <p>Use at least 8 characters.</p>
          </div>
        </div>

        {message && <div className="auth-message">{message}</div>}

        <form className="auth-form" onSubmit={submit}>
          <label>
            New password
            <input
              type="password"
              minLength={8}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder="At least 8 characters"
              disabled={success}
              required
            />
          </label>

          <button className="btn btn-primary auth-submit" disabled={loading || success || !token}>
            {loading ? "Resetting password..." : "Reset password"}
          </button>
        </form>

        <p className="auth-switch">
          Need a new link? <Link to="/forgot-password">Request reset</Link>
        </p>
      </section>
    </main>
  );
}
