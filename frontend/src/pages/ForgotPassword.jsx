import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, ShieldCheck } from "lucide-react";
import { requestPasswordReset, resetPassword, verifyResetCode } from "../api/client";

const defaultResetMessage = "If an account exists for that email, a verification code will be sent shortly.";

export default function ForgotPassword() {
  const [step, setStep] = useState("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState("");
  const [message, setMessage] = useState("");
  const [messageTone, setMessageTone] = useState("info");
  const [resendSeconds, setResendSeconds] = useState(0);

  useEffect(() => {
    if (resendSeconds <= 0) return undefined;
    const timer = setTimeout(() => setResendSeconds((value) => Math.max(0, value - 1)), 1000);
    return () => clearTimeout(timer);
  }, [resendSeconds]);

  const startResendTimer = (seconds) => {
    const nextSeconds = Number.isFinite(Number(seconds)) ? Number(seconds) : 60;
    setResendSeconds(Math.max(0, nextSeconds));
  };

  const sendCode = async (event) => {
    event?.preventDefault();
    setLoading("send");
    setMessage("");
    setMessageTone("info");
    try {
      const result = await requestPasswordReset(email);
      if (result.delivery_configured === false) {
        setMessageTone("error");
        setMessage("Password reset email delivery is not configured. Contact your administrator.");
        return;
      }
      setStep("code");
      setMessageTone("success");
      setMessage(result.message || defaultResetMessage);
      startResendTimer(result.resend_after_seconds ?? 60);
    } catch (error) {
      setMessageTone("error");
      setMessage(error.userMessage || "Unable to send a verification code right now.");
    } finally {
      setLoading("");
    }
  };

  const verifyCode = async (event) => {
    event.preventDefault();
    if (code.length !== 6) {
      setMessageTone("error");
      setMessage("Enter the 6-digit verification code.");
      return;
    }

    setLoading("verify");
    setMessage("");
    try {
      const result = await verifyResetCode({ email, code });
      setStep("password");
      setMessageTone("success");
      setMessage(result.message || "Verification code accepted. Choose a new password.");
    } catch (error) {
      setMessageTone("error");
      setMessage(error.userMessage || "The verification code is invalid or expired.");
    } finally {
      setLoading("");
    }
  };

  const submitNewPassword = async (event) => {
    event.preventDefault();
    if (newPassword.length < 8) {
      setMessageTone("error");
      setMessage("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setMessageTone("error");
      setMessage("Password confirmation does not match.");
      return;
    }

    setLoading("reset");
    setMessage("");
    try {
      const result = await resetPassword({
        email,
        code,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      setStep("success");
      setMessageTone("success");
      setMessage(result.message || "Password reset successful. You can now sign in.");
    } catch (error) {
      setMessageTone("error");
      setMessage(error.userMessage || "Unable to reset your password.");
    } finally {
      setLoading("");
    }
  };

  const handleCodeChange = (event) => {
    setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
  };

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-brand">
          <span><ShieldCheck size={24} /></span>
          <div>
            <h1>Forgot password</h1>
            <p>Reset your password with a one-time email code.</p>
          </div>
        </div>

        <div className="auth-stepper" aria-label="Password reset progress">
          {["Email", "Code", "Password"].map((label, index) => {
            const activeIndex = step === "email" ? 0 : step === "code" ? 1 : 2;
            return (
              <span
                key={label}
                className={`auth-step ${index <= activeIndex ? "auth-step-active" : ""}`}
              >
                {label}
              </span>
            );
          })}
        </div>

        {message && (
          <div className={`auth-message ${messageTone === "error" ? "auth-message-error" : "auth-message-success"}`}>
            {message}
          </div>
        )}

        {step === "email" && (
          <form className="auth-form" onSubmit={sendCode}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@company.com"
                autoComplete="email"
                required
              />
            </label>

            <button className="btn btn-primary auth-submit" disabled={loading === "send"}>
              {loading === "send" ? (
                <>
                  <Loader2 className="spin" size={17} />
                  Sending code...
                </>
              ) : (
                "Send verification code"
              )}
            </button>
          </form>
        )}

        {step === "code" && (
          <form className="auth-form" onSubmit={verifyCode}>
            <label>
              Verification code
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                value={code}
                onChange={handleCodeChange}
                placeholder="123456"
                autoComplete="one-time-code"
                required
              />
            </label>

            <button className="btn btn-primary auth-submit" disabled={loading === "verify"}>
              {loading === "verify" ? (
                <>
                  <Loader2 className="spin" size={17} />
                  Verifying...
                </>
              ) : (
                "Verify code"
              )}
            </button>

            <button
              type="button"
              className="btn btn-ghost auth-submit"
              disabled={Boolean(loading) || resendSeconds > 0}
              onClick={sendCode}
            >
              {resendSeconds > 0 ? `Resend code in ${resendSeconds}s` : "Resend code"}
            </button>
          </form>
        )}

        {step === "password" && (
          <form className="auth-form" onSubmit={submitNewPassword}>
            <label>
              New password
              <input
                type="password"
                minLength={8}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                required
              />
            </label>

            <label>
              Confirm new password
              <input
                type="password"
                minLength={8}
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="Repeat your new password"
                autoComplete="new-password"
                required
              />
            </label>

            <button className="btn btn-primary auth-submit" disabled={loading === "reset"}>
              {loading === "reset" ? (
                <>
                  <Loader2 className="spin" size={17} />
                  Resetting password...
                </>
              ) : (
                "Reset password"
              )}
            </button>
          </form>
        )}

        {step === "success" && (
          <div className="auth-success-panel">
            <CheckCircle2 size={32} />
            <p>Password reset successful.</p>
            <Link className="btn btn-primary auth-submit" to="/login">
              Back to Sign In
            </Link>
          </div>
        )}

        {step !== "success" && (
          <p className="auth-switch">
            Remember your password? <Link to="/login">Sign in</Link>
          </p>
        )}
      </section>
    </main>
  );
}
