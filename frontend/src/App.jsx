import React from "react";
import { useState } from "react";
import { Routes, Route, NavLink, Link, Navigate } from "react-router-dom";
import { Video, Globe, Share2, LogOut, UserCircle } from "lucide-react";
import Home from "./pages/Home";
import Auth from "./pages/Auth";
import Features from "./pages/Features";
import About from "./pages/About";
import GoogleCallback from "./pages/GoogleCallback";
import Profile from "./pages/Profile";
import "./App.css";

function App() {
  const [session, setSession] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("youtube-ai-session")) || null;
    } catch {
      return null;
    }
  });

  const handleLogout = () => {
    localStorage.removeItem("youtube-ai-session");
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
        <Route path="/auth/google/callback" element={<GoogleCallback onAuthenticated={handleAuthenticated} />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="website-container">
      {/* Navbar */}
      <nav className="navbar">
        <Link to="/" className="nav-brand" style={{ textDecoration: 'none' }}>
          <Video className="header-icon" size={28} />
          <h1>YouTube AI Assistant</h1>
        </Link>
        <div className="nav-links">
          <NavLink to="/" className={({ isActive }) => (isActive ? "active-link" : "")}>Home</NavLink>
          <NavLink to="/features" className={({ isActive }) => (isActive ? "active-link" : "")}>Features</NavLink>
          <NavLink to="/about" className={({ isActive }) => (isActive ? "active-link" : "")}>About</NavLink>
          <NavLink to="/profile" className={({ isActive }) => (isActive ? "active-link" : "")}><UserCircle size={16} /> Profile</NavLink>
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
          <Route path="/auth/google/callback" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="footer">
        <div>&copy; 2026 YouTube AI Assistant. Developed by <strong>Harshad Khatale</strong>.</div>
        <div className="footer-links">
          <a>Privacy Policy</a>
          <a>Terms of Service</a>
          <a><Globe size={18} /></a>
          <a><Share2 size={18} /></a>
        </div>
      </footer>
    </div>
  );
}

export default App;