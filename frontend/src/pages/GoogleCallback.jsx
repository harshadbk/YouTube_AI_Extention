import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

function GoogleCallback({ onAuthenticated }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const fragmentParams = new URLSearchParams(window.location.hash.slice(1));
    const token = fragmentParams.get("token");
    const email = fragmentParams.get("email");
    const googleError = searchParams.get("google_error");
    if (token && email) {
      window.history.replaceState({}, document.title, window.location.pathname);
      onAuthenticated({ token, email });
      return;
    }
    setError(googleError ? "Google sign-in could not be completed." : "Missing Google sign-in response.");
    const timer = window.setTimeout(() => navigate("/login", { replace: true }), 1800);
    return () => window.clearTimeout(timer);
  }, [navigate, onAuthenticated, searchParams]);

  return <main className="auth-page"><section className="auth-panel"><div className="auth-heading"><h1>{error || "Signing you in..."}</h1></div></section></main>;
}

export default GoogleCallback;