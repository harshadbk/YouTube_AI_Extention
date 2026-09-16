import React from "react";
import { useState } from "react";
import { Routes, Route, NavLink, Link, Navigate, useLocation } from "react-router-dom";
import { Video, Globe, Share2, LogOut, UserCircle, Menu, X } from "lucide-react";
import Home from "./pages/Home";
import Auth from "./pages/Auth";
import Features from "./pages/Features";
import About from "./pages/About";
import GoogleCallback from "./pages/GoogleCallback";
import Profile from "./pages/Profile";
import "./App.css";

function App() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const location = useLocation();
  const [session, setSession] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("youtube-ai-session")) || null;
    } catch {
      return null;
    }
  });

  const handleLogout = () => {
    localStorage.removeItem("youtube-ai-session");
    setMobileNavOpen(false);
    setSession(null);
  };

  const handleAuthenticated = (nextSession) => {
    localStorage.setItem("youtube-ai-session", JSON.stringify(nextSession));
    setSession(nextSession);
  };

  const handleProfileUpdated = (profile) => {
    setSession((current) => {
      const nextSession = { ...current, ...profile };
      localStorage.setItem("youtube-ai-session", JSON.stringify(nextSession));
      return nextSession;
    });
  };

  if (!session?.token) {
    return (
      <Routes>
        <Route path="/login" element={<Auth page="login" onAuthenticated={handleAuthenticated} />} />
        <Route path="/register" element={<Auth page="register" onAuthenticated={handleAuthenticated} />} />
        <Route path="/verify-email" element={<Auth page="verify" onAuthenticated={handleAuthenticated} />} />
        <Route path="/forgot-password" element={<Auth page="forgot" onAuthenticated={handleAuthenticated} />} />
        <Route path="/auth/google/callback" element={<GoogleCallback onAuthenticated={handleAuthenticated} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  const isChatPage = location.pathname === "/";

  return (
    <div className={`website-container ${isChatPage ? "chat-layout" : ""}`}>
      {/* Navbar */}
      <nav className="navbar">
        <Link to="/" className="nav-brand" style={{ textDecoration: 'none' }}>
          <Video className="header-icon" size={28} />
          <h1>YouTube AI Assistant</h1>
        </Link>
        <button
          className={`mobile-nav-toggle ${mobileNavOpen ? "is-open" : ""}`}
          onClick={() => setMobileNavOpen((open) => !open)}
          aria-label={mobileNavOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={mobileNavOpen}
        >
          {mobileNavOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
        <div className={`nav-links ${mobileNavOpen ? "mobile-nav-open" : ""}`}>
          <NavLink to="/" onClick={() => setMobileNavOpen(false)} className={({ isActive }) => (isActive ? "active-link" : "")}>Home</NavLink>
          <NavLink to="/features" onClick={() => setMobileNavOpen(false)} className={({ isActive }) => (isActive ? "active-link" : "")}>Features</NavLink>
          <NavLink to="/about" onClick={() => setMobileNavOpen(false)} className={({ isActive }) => (isActive ? "active-link" : "")}>About</NavLink>
          <NavLink to="/profile" onClick={() => setMobileNavOpen(false)} className={({ isActive }) => (isActive ? "active-link" : "")}><UserCircle size={16} /> Profile</NavLink>
          <button className="logout-btn" onClick={handleLogout} title={`Log out ${session.email}`}><LogOut size={16} /> Log out</button>
        </div>
      </nav>

      {/* Main Content (Routes) */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Home token={session.token} />} />
          <Route path="/features" element={<Features />} />
          <Route path="/about" element={<About />} />
          <Route path="/profile" element={<Profile token={session.token} onProfileUpdated={handleProfileUpdated} />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="/register" element={<Navigate to="/" replace />} />
          <Route path="/verify-email" element={<Navigate to="/" replace />} />
          <Route path="/forgot-password" element={<Navigate to="/" replace />} />
          <Route path="/auth/google/callback" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {!isChatPage && (
        <footer className="footer">
          <div>&copy; 2026 YouTube AI Assistant. Developed by <strong>Vivek Kumbhar</strong>.</div>
          <div className="footer-links">
            <a>Privacy Policy</a>
            <a>Terms of Service</a>
            <a><Globe size={18} /></a>
            <a><Share2 size={18} /></a>
          </div>
        </footer>
      )}
    </div>
  );
}

export default App;