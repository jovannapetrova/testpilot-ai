import { Link } from "react-router-dom";
import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { requestPasswordReset } from "../api/client";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [debugToken, setDebugToken] = useState("");

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setDebugToken("");
    try {
      const result = await requestPasswordReset(email);
      setMessage(result.message || "Password reset instructions were requested.");
      setDebugToken(result.debug_reset_token || "");
    } catch (error) {
      setMessage(error.userMessage || "Unable to request password reset instructions.");
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
            <h1>Reset password</h1>
            <p>Request a secure one-time reset link.</p>
          </div>
        </div>

        {message && <div className="auth-message">{message}</div>}

        <form className="auth-form" onSubmit={submit}>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              required
            />
          </label>

          <button className="btn btn-primary auth-submit" disabled={loading}>
            {loading ? "Requesting link..." : "Send reset link"}
          </button>
        </form>

        {debugToken && (
          <div className="auth-debug-token">
            <strong>Development reset link</strong>
            <Link to={`/reset-password?token=${encodeURIComponent(debugToken)}`}>
              Open reset link
            </Link>
          </div>
        )}

        <p className="auth-switch">
          Remember your password? <Link to="/login">Sign in</Link>
        </p>
      </section>
    </main>
  );
}
