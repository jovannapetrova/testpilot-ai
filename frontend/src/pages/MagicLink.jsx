import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { verifyMagicLink } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function MagicLink() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const token = params.get("token") || "";
  const [message, setMessage] = useState("Verifying secure sign-in link...");
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    let cancelled = false;

    const verify = async () => {
      if (!token) {
        setStatus("error");
        setMessage("This sign-in link is missing a token. Request a new link from the login page.");
        return;
      }

      try {
        const result = await verifyMagicLink(token);
        if (cancelled) return;
        setSession(result, true);
        setStatus("success");
        setMessage("Sign-in link verified. Opening your workspace...");
        setTimeout(() => navigate("/dashboard"), 800);
      } catch (error) {
        if (cancelled) return;
        setStatus("error");
        setMessage(error.userMessage || "This sign-in link is invalid or expired.");
      }
    };

    verify();
    return () => {
      cancelled = true;
    };
  }, [navigate, setSession, token]);

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-brand">
          <span><ShieldCheck size={24} /></span>
          <div>
            <h1>Magic link</h1>
            <p>One-time secure sign-in.</p>
          </div>
        </div>

        <div className={`auth-message ${status === "error" ? "auth-message-error" : ""}`}>
          {message}
        </div>

        {status === "error" && (
          <p className="auth-switch">
            <Link to="/login">Back to sign in</Link>
          </p>
        )}
      </section>
    </main>
  );
}
