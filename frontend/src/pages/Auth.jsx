import React, { useState } from "react";
import axios from "axios";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { LogIn, UserPlus, MailCheck, Video } from "lucide-react";
import { API_URL } from "../config";

function Auth({ page, onAuthenticated }) {
  const location = useLocation();
  const navigate = useNavigate();
  const isVerifyPage = page === "verify";
  const isForgotPage = page === "forgot";
  const [resetRequested, setResetRequested] = useState(false);
  const [email, setEmail] = useState(location.state?.email || "");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(location.state?.notice || "");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setLoading(true);
    try {
      const endpoint = isVerifyPage
        ? "/auth/verify-email"
        : isForgotPage
          ? resetRequested ? "/auth/reset-password" : "/auth/forgot-password"
          : page === "login" ? "/auth/login" : "/auth/register";
      const payload = isVerifyPage
        ? { email, code: verificationCode }
        : isForgotPage
          ? resetRequested ? { email, code: verificationCode, password } : { email }
          : page === "register" ? { email, password, full_name: fullName, phone } : { email, password };
      const response = await axios.post(`${API_URL}${endpoint}`, payload);
      if (response.data.verification_required) {
        navigate("/verify-email", { state: { email } });
      } else if (response.data.reset_required) {
        setResetRequested(true);
        setNotice("A password reset code was sent. Check your inbox and spam folder.");
      } else if (response.data.reset) {
        navigate("/login", { state: { notice: "Password reset successfully. You can now log in." } });
      } else {
        onAuthenticated(response.data);
      }
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to complete that request.");
    } finally {
      setLoading(false);
    }
  };

  const resendVerification = async () => {
    setError("");
    setNotice("");
    setLoading(true);
    try {
      await axios.post(`${API_URL}/auth/resend-verification`, { email });
      setNotice("A new verification code was sent. Check your inbox and spam folder.");
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to resend the verification code.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="auth-brand"><Video size={28} /><span>YouTube AI Assistant</span></div>
        <div className="auth-heading">
          <p className="eyebrow">Your private workspace</p>
          <h1>{isVerifyPage || (isForgotPage && resetRequested) ? "Check your email" : isForgotPage ? "Reset your password" : page === "login" ? "Welcome back" : "Create your account"}</h1>
          <p>{isVerifyPage || (isForgotPage && resetRequested) ? `Enter the 6-digit code sent to ${email}.` : isForgotPage ? "We will send a secure reset code to your email." : page === "login" ? "Continue your personalized video conversations." : "Save your video conversations to your own account."}</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {isVerifyPage ? <>
            <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>
            <label>Verification code<input type="text" value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required autoComplete="one-time-code" /></label>
          </> : isForgotPage ? <>
            <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>
            {resetRequested && <>
              <label>Reset code<input type="text" value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required autoComplete="one-time-code" /></label>
              <label>New password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required autoComplete="new-password" /></label>
            </>}
          </> : <>
          {page === "register" && <>
            <label>Full name<input type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} required autoComplete="name" /></label>
            <label>Phone number<input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} required autoComplete="tel" /></label>
          </>}
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required autoComplete={page === "login" ? "current-password" : "new-password"} /></label>
          </>}
          {error && <p className="auth-error">{error}</p>}
          {notice && <p className="auth-notice">{notice}</p>}
          <button className="auth-submit" type="submit" disabled={loading}>
            {isVerifyPage || isForgotPage ? <MailCheck size={18} /> : page === "login" ? <LogIn size={18} /> : <UserPlus size={18} />}
            {loading ? "Working..." : isVerifyPage ? "Verify email" : isForgotPage ? resetRequested ? "Reset password" : "Send reset code" : page === "login" ? "Log in" : "Register"}
          </button>
        </form>
        {!isVerifyPage && !isForgotPage && <>
          <div className="auth-divider"><span>or</span></div>
          <a className="google-auth-btn" href={`${API_URL}/auth/google/login`}>
            <span className="google-mark">G</span>
            Continue with Google
          </a>
        </>}
        {page === "login" && <>
          <div className="auth-links">
            <Link className="auth-switch" to="/register">Need an account? Register</Link>
            <Link className="auth-switch" to="/verify-email" state={{ email }}>Verify your email</Link>
            <Link className="auth-switch" to="/forgot-password" state={{ email }}>Forgot password?</Link>
          </div>
        </>}
        {page === "register" && <Link className="auth-switch" to="/login">Already have an account? Log in</Link>}
        {isVerifyPage && <Link className="auth-switch" to="/login">Back to login</Link>}
        {isVerifyPage && <button className="auth-switch" type="button" onClick={resendVerification} disabled={loading || !email}>Resend verification code</button>}
        {isForgotPage && <Link className="auth-switch" to="/login">Back to login</Link>}
      </section>
    </main>
  );
}

export default Auth;
