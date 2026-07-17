import React from "react";
import { Link } from "react-router-dom";

function About() {
  return (
    <div className="info-section">
      <h2 className="section-title">About Us</h2>
      <div className="about-content">
        <p>The YouTube AI Assistant is built to enhance your video learning experience. Powered by advanced AI and Retrieval-Augmented Generation (RAG) technology, we make it effortless to extract knowledge from video content.</p>
        <p>Whether you are a student, researcher, or just a curious mind, this tool is designed to save you time and provide you with instant insights.</p>
        <Link to="/">
          <button className="primary-btn">Try it now</button>
        </Link>
      </div>
    </div>
  );
}

export default About;
