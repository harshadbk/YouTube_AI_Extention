import React from "react";
import { Video, MessageSquare, Globe } from "lucide-react";

function Features() {
  return (
    <div className="info-section">
      <h2 className="section-title">Features</h2>
      <div className="features-grid">
        <div className="feature-card">
          <Video className="feature-icon" size={32} />
          <h3>Smart Summaries</h3>
          <p>Instantly get the gist of long YouTube videos without watching the whole thing.</p>
        </div>
        <div className="feature-card">
          <MessageSquare className="feature-icon" size={32} />
          <h3>Interactive Q&A</h3>
          <p>Ask specific questions about the video content and get precise answers powered by RAG.</p>
        </div>
        <div className="feature-card">
          <Globe className="feature-icon" size={32} />
          <h3>Persistent History</h3>
          <p>Your conversations are saved securely in a database, allowing you to resume at any time.</p>
        </div>
      </div>
    </div>
  );
}

export default Features;
