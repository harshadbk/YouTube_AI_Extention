import React, { useState } from "react";
import axios from "axios";
import { LogIn, UserPlus, Video } from "lucide-react";

const API_URL = "http://localhost:8000";

function Auth({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const payload = mode === "register" ? { email, password, full_name: fullName, phone } : { email, password };
      const response = await axios.post(`${API_URL}${endpoint}`, payload);
      onAuthenticated(response.data);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || "Unable to complete that request.");
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
          <h1>{mode === "login" ? "Welcome back" : "Create your account"}</h1>
          <p>{mode === "login" ? "Continue your personalized video conversations." : "Save your video conversations to your own account."}</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && <>
            <label>Full name<input type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} required autoComplete="name" /></label>
            <label>Phone number<input type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} required autoComplete="tel" /></label>
          </>}
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required autoComplete="email" /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required autoComplete={mode === "login" ? "current-password" : "new-password"} /></label>
          {error && <p className="auth-error">{error}</p>}
          <button className="auth-submit" type="submit" disabled={loading}>
            {mode === "login" ? <LogIn size={18} /> : <UserPlus size={18} />}
            {loading ? "Working..." : mode === "login" ? "Log in" : "Register"}
          </button>
        </form>
        <button className="auth-switch" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
          {mode === "login" ? "Need an account? Register" : "Already have an account? Log in"}
        </button>
      </section>
    </main>
  );
}

export default Auth;
