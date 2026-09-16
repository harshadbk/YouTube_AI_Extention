import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import { Send, Video, Bot, User, MessageSquare, Menu, X, Plus } from "lucide-react";
import { API_URL } from "../config";

function Home({ token }) {
  const [url, setUrl] = useState("");
  const [question, setQuestion] = useState("");
  
  // History state: { [url]: { title, messages } }
  const [chatHistory, setChatHistory] = useState({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(true);
  const chatEndRef = useRef(null);

  // Fetch history from backend on load
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const resp = await axios.get(`${API_URL}/history`, { headers: { Authorization: `Bearer ${token}` } });
        const history = Array.isArray(resp.data)
          ? Object.fromEntries(resp.data.map((chat) => [chat.url, { title: chat.title, messages: chat.messages }]))
          : Object.fromEntries(Object.entries(resp.data).map(([chatUrl, messages]) => [chatUrl, { title: chatUrl, messages }]));
        setChatHistory(history);
      } catch (err) {
        console.error("Failed to load history from database", err);
      } finally {
        setFetchingHistory(false);
      }
    };
    fetchHistory();
  }, [token]);

  const activeChat = chatHistory[url] || { title: "", messages: [] };
  const messages = activeChat.messages;

  // Scroll to newest message
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSend = async () => {
    if (!url || !question || loading) return;
    
    const userMsg = { role: "user", content: question };
    const currentQuestion = question;
    
    // Optimistic UI update
    setChatHistory(prev => ({
      ...prev,
      [url]: { ...activeChat, messages: [...activeChat.messages, userMsg] }
    }));
    
    setLoading(true);
    setQuestion("");
    
    try {
      const transcriptResponse = await axios.get(`${API_URL}/transcript`, {
        params: { url },
        headers: { Authorization: `Bearer ${token}` },
      });
      const resp = await axios.post(`${API_URL}/chat`, {
        url,
        video_title: transcriptResponse.data.title,
        question: currentQuestion,
        transcript_text: transcriptResponse.data.transcript_text,
      }, { headers: { Authorization: `Bearer ${token}` } });
      const aiMsg = { role: "assistant", content: resp.data.answer };
      
      setChatHistory(prev => ({
        ...prev,
        [url]: { title: resp.data.title || prev[url]?.title || url, messages: [...(prev[url]?.messages || []), aiMsg] }
      }));
    } catch (err) {
      const serverMessage = err?.response?.data?.detail;
      const errMsg = { role: "assistant", content: "Error: " + (serverMessage ?? err?.message ?? "unknown error") };
      setChatHistory(prev => ({
        ...prev,
        [url]: { ...prev[url], messages: [...(prev[url]?.messages || []), errMsg] }
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !loading) {
      handleSend();
    }
  };
  
  const startNewChat = () => {
    setUrl("");
    setSidebarOpen(false);
  };
  
  const loadChat = (targetUrl) => {
    setUrl(targetUrl);
    setSidebarOpen(false);
  };

  const markdownComponents = {
    table: ({ children }) => <div className="markdown-table-wrap"><table>{children}</table></div>,
    pre: ({ children }) => <pre className="markdown-code-block">{children}</pre>,
    code: ({ className, children, ...props }) => (
      <code className={className || "markdown-inline-code"} {...props}>{children}</code>
    ),
  };

  return (
    <div className="app-wrapper">
      {/* Sidebar Overlay */}
      {sidebarOpen && <div className="sidebar-overlay" onClick={() => setSidebarOpen(false)}></div>}
      
      {/* Sidebar */}
      <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h3>Chat History</h3>
          <button className="icon-btn" onClick={() => setSidebarOpen(false)}>
            <X size={20} />
          </button>
        </div>
        
        <button className="new-chat-btn" onClick={startNewChat}>
          <Plus size={18} /> New Chat
        </button>
        
        <div className="history-list">
          {fetchingHistory && <div className="empty-history">Loading history...</div>}
          {!fetchingHistory && Object.keys(chatHistory).length === 0 && (
            <div className="empty-history">No past chats yet.</div>
          )}
          {Object.keys(chatHistory).reverse().map((chatUrl) => (
            <div
              key={chatUrl}
              className={`history-item ${url === chatUrl ? 'active' : ''}`}
              onClick={() => loadChat(chatUrl)}
              title={chatHistory[chatUrl].title}
            >
              <Video size={16} className="history-icon" />
              <div className="history-url">{chatHistory[chatUrl].title}</div>
            </div>
          ))}
        </div>
      </div>

      <header className="app-header">
        <button className="icon-btn menu-btn" onClick={() => setSidebarOpen(true)}>
          <Menu size={24} />
        </button>
        <Video className="header-icon" size={24} />
        <h2>{url ? "Active Chat" : "New Chat"}</h2>
      </header>
      
      <div className="chat-container">
        <div className="chat-box">
          {messages.length === 0 && (
            <div className="empty-state">
              <Bot size={64} opacity={0.5} color="var(--accent-color)" />
              <h3>How can I help you today?</h3>
              <p>Enter a YouTube URL below and ask me to summarize, explain, or answer questions about it.</p>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === "user" ? <User size={18} /> : <Bot size={18} />}
              </div>
              <div className="message-content">
                {msg.role === "assistant" ? (
                  <ReactMarkdown components={markdownComponents}>{msg.content}</ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="message assistant">
              <div className="message-avatar">
                <Bot size={18} />
              </div>
              <div className="typing-indicator">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>
        
        <div className="input-area">
          <div className="input-group">
            <Video className="input-icon" size={18} />
            <input
              type="text"
              placeholder="Paste YouTube URL here..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="input url-input"
            />
          </div>
          
          <div style={{ display: 'flex' }}>
            <div className="input-group" style={{ flex: 1 }}>
              <MessageSquare className="input-icon" size={18} />
              <input
                type="text"
                placeholder="Ask a question..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="input question-input"
                onKeyDown={handleKey}
                disabled={loading}
              />
            </div>
            <button 
              onClick={handleSend} 
              className="send-btn" 
              disabled={loading || !question.trim() || !url.trim()}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Home;
