import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { forgotPassword } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "", remember_me: true });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      await login(form);
      navigate("/dashboard");
    } catch (error) {
      setMessage(error.userMessage || "Unable to sign in. Check your credentials and try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleForgot = async () => {
    if (!form.email) {
      setMessage("Enter your email first, then request password reset instructions.");
      return;
    }
    const result = await forgotPassword(form.email);
    setMessage(result.message);
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
            <button type="button" className="link-button" onClick={handleForgot}>
              Forgot password?
            </button>
          </div>

          {message && <div className="auth-message">{message}</div>}

          <button className="btn btn-primary auth-submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="auth-switch">
          New to TestPilot AI? <Link to="/register">Create an account</Link>
        </p>
      </section>
    </main>
  );
}
