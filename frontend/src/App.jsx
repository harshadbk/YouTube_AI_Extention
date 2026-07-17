import React from "react";
import { Routes, Route, NavLink, Link } from "react-router-dom";
import { Video, Globe, Share2 } from "lucide-react";
import Home from "./pages/Home";
import Features from "./pages/Features";
import About from "./pages/About";
import "./App.css";

function App() {
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
        </div>
      </nav>

      {/* Main Content (Routes) */}
      <main className="main-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/features" element={<Features />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </main>

      {/* Footer */}
      <footer className="footer">
        <div>&copy; 2026 YouTube AI Assistant. All rights reserved.</div>
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