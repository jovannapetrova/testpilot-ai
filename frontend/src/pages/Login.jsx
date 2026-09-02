import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Loader2, Mail, ShieldCheck } from "lucide-react";
import { requestMagicLink } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { authNotice, clearAuthNotice, login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "", remember_me: true });
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState("info");
  const [loading, setLoading] = useState(false);
  const [magicLoading, setMagicLoading] = useState(false);
  const [slowLogin, setSlowLogin] = useState(false);
  const slowLoginTimer = useRef(null);

  useEffect(() => () => clearTimeout(slowLoginTimer.current), []);

  const submit = async (event) => {
    event.preventDefault();
    clearTimeout(slowLoginTimer.current);
    setLoading(true);
    setSlowLogin(false);
    setMessage("");
    clearAuthNotice?.();
    slowLoginTimer.current = setTimeout(() => setSlowLogin(true), 4500);
    try {
      await login(form);
      navigate("/dashboard");
    } catch (error) {
      setMessageTone("error");
      setMessage(error.userMessage || "Unable to sign in. Check your credentials and try again.");
    } finally {
      clearTimeout(slowLoginTimer.current);
      setLoading(false);
    }
  };

  const handleMagicLink = async () => {
    if (!form.email) {
      setMessageTone("error");
      setMessage("Enter your email first, then request a sign-in link.");
      return;
    }

    try {
      setMagicLoading(true);
      setMessage("");
      const result = await requestMagicLink({ email: form.email });
      setMessageTone(result.delivery_configured ? "success" : "info");
      setMessage(result.message || "If this account exists, a sign-in link will be sent.");
    } catch (error) {
      setMessageTone("error");
      setMessage(error.userMessage || "Unable to request a sign-in link right now.");
    } finally {
      setMagicLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-brand">
          <span><ShieldCheck size={24} /></span>
          <div>
            <h1>Welcome back</h1>
            <p>Sign in to your TestPilot AI workspace.</p>
          </div>
        </div>

        <form className="auth-form" onSubmit={submit}>
          <label>
            Email
            <input
              type="email"
              required
              value={form.email}
              onChange={(event) => setForm({ ...form, email: event.target.value })}
              placeholder="you@company.com"
            />
          </label>

          <label>
            Password
            <input
              type="password"
              required
              value={form.password}
              onChange={(event) => setForm({ ...form, password: event.target.value })}
              placeholder="Enter your password"
            />
          </label>

          <div className="auth-row">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={form.remember_me}
                onChange={(event) => setForm({ ...form, remember_me: event.target.checked })}
              />
              Remember me
            </label>
            <Link className="link-button" to="/forgot-password">
              Forgot password?
            </Link>
          </div>

          {(authNotice || message || slowLogin) && (
            <div className={`auth-message ${messageTone === "error" ? "auth-message-error" : ""}`}>
              {authNotice || message || "Server is taking longer than usual. Please keep this page open."}
            </div>
          )}

          <button className="btn btn-primary auth-submit" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="spin" size={17} />
                Signing you in...
              </>
            ) : (
              "Sign in"
            )}
          </button>

          <button
            type="button"
            className="btn btn-ghost auth-submit"
            onClick={handleMagicLink}
            disabled={loading || magicLoading}
          >
            {magicLoading ? (
              <>
                <Loader2 className="spin" size={17} />
                Sending link...
              </>
            ) : (
              <>
                <Mail size={17} />
                Email me a sign-in link
              </>
            )}
          </button>
        </form>

        <p className="auth-switch">
          New to TestPilot AI? <Link to="/register">Create an account</Link>
        </p>
      </section>
    </main>
  );
}
