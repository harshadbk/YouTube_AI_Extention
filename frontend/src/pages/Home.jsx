import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Video, User, MessageSquare, Menu, X, Plus, Trash2, Share2 } from "lucide-react";
import { API_URL } from "../config";

function Home({ token }) {
  const [url, setUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState({});
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth > 768);
  const [loading, setLoading] = useState(false);
  const [fetchingHistory, setFetchingHistory] = useState(true);
  const [shareState, setShareState] = useState("Share");
  const [deleteConfirmUrl, setDeleteConfirmUrl] = useState(null);
  const [deleteConfirmTitle, setDeleteConfirmTitle] = useState("");
  const chatEndRef = useRef(null);

  const normalizeYouTubeUrl = (input) => {
    if (!input || typeof input !== "string") return "";

    const trimmed = input.trim();
    if (!trimmed) return "";

    const getVideoIdFromPath = (pathname) => {
      if (!pathname) return "";
      const cleanPath = pathname.replace(/^\/+|\/+$/g, "");
      if (!cleanPath) return "";

      const segments = cleanPath.split("/");
      const videoId = segments.find((segment, index) => {
        const previous = segments[index - 1];
        return (
          segment &&
          /^[A-Za-z0-9_-]{11}$/.test(segment) &&
          (previous === "shorts" || previous === "embed" || previous === "watch" || !previous)
        );
      });

      return videoId || "";
    };

    try {
      const withProtocol = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
      const parsed = new URL(withProtocol);
      const videoId =
        parsed.searchParams.get("v") ||
        getVideoIdFromPath(parsed.pathname) ||
        (parsed.hostname.includes("youtu.be") ? parsed.pathname.split("/").filter(Boolean)[0] : "");

      if (videoId && /^[A-Za-z0-9_-]{11}$/.test(videoId)) {
        return `https://www.youtube.com/watch?v=${videoId}`;
      }
    } catch {
      // ignore and fall through to raw pattern extraction
    }

    const patterns = [
      /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/))([A-Za-z0-9_-]{11})/i,
      /(?:https?:\/\/)?youtu\.be\/([A-Za-z0-9_-]{11})/i,
      /(?:^|[?&])(?:v|video|url|youtube)=https?:\/\/(?:www\.)?(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)?([A-Za-z0-9_-]{11})/i,
      /(?:^|[?&])(?:v|video|url|youtube)=([A-Za-z0-9_-]{11})/i,
    ];

    for (const pattern of patterns) {
      const match = trimmed.match(pattern);
      if (match && /^[A-Za-z0-9_-]{11}$/.test(match[1])) {
        return `https://www.youtube.com/watch?v=${match[1]}`;
      }
    }

    return trimmed;
  };

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

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const paramValue = params.get("url") || params.get("video") || params.get("youtube");
    if (paramValue) {
      const cleaned = normalizeYouTubeUrl(paramValue);
      if (cleaned) {
        setUrl(cleaned);
      }
    }
  }, []);

  useEffect(() => {
    const safeUrl = normalizeYouTubeUrl(url);
    const baseUrl = `${window.location.origin}${window.location.pathname}`;

    if (!safeUrl) {
      if (window.location.search) {
        window.history.replaceState({}, "", baseUrl);
      }
      return;
    }

    const nextUrl = `${baseUrl}?url=${encodeURIComponent(safeUrl)}`;
    if (window.location.href !== nextUrl) {
      window.history.replaceState({}, "", nextUrl);
    }
  }, [url]);

  const activeChat = chatHistory[normalizeYouTubeUrl(url)] || { title: "", messages: [] };
  const messages = activeChat.messages;

  const handleShare = async () => {
    const safeUrl = normalizeYouTubeUrl(url);
    if (!safeUrl) return;

    const shareUrl = `${window.location.origin}${window.location.pathname}?url=${encodeURIComponent(safeUrl)}`;
    const chatText = messages.length
      ? messages
          .map((msg) => `${msg.role === "user" ? "You" : "Assistant"}: ${msg.content}`)
          .join("\n\n")
      : "No messages yet.";
    const sharePayload = `${chatText}\n\nVideo: ${safeUrl}\nChat link: ${shareUrl}`;

    try {
      if (navigator.share) {
        await navigator.share({
          title: "YouTube AI Assistant chat",
          text: sharePayload,
          url: shareUrl,
        });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(sharePayload);
      }
      setShareState("Copied");
      window.setTimeout(() => setShareState("Share"), 1200);
    } catch (error) {
      if (navigator.clipboard) {
        try {
          await navigator.clipboard.writeText(sharePayload);
          setShareState("Copied");
          window.setTimeout(() => setShareState("Share"), 1200);
        } catch {
          setShareState("Share");
        }
      }
    }
  };

  const handleDeleteChatRequest = (chatUrl, title) => {
    setDeleteConfirmUrl(chatUrl);
    setDeleteConfirmTitle(title || chatUrl);
  };

  const confirmDeleteChat = async () => {
    const chatUrl = deleteConfirmUrl;
    if (!chatUrl) return;

    setDeleteConfirmUrl(null);
    setDeleteConfirmTitle("");

    const normalizedDeleteTarget = normalizeYouTubeUrl(chatUrl) || chatUrl;
    const nextHistory = { ...chatHistory };
    Object.keys(nextHistory).forEach((key) => {
      if (normalizeYouTubeUrl(key) === normalizedDeleteTarget || key === chatUrl) {
        delete nextHistory[key];
      }
    });

    setChatHistory(nextHistory);
    if (normalizeYouTubeUrl(url) === normalizedDeleteTarget || url === chatUrl) {
      setUrl("");
    }

    try {
      await axios.delete(`${API_URL}/history`, {
        params: { url: normalizedDeleteTarget },
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (error) {
      console.error("Failed to delete chat", error);
    }
  };

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSend = async () => {
    const cleanedUrl = normalizeYouTubeUrl(url);
    if (!cleanedUrl || !question || loading) return;

    const userMsg = { role: "user", content: question };
    const currentQuestion = question;

    setUrl(cleanedUrl);

    setChatHistory(prev => ({
      ...prev,
      [cleanedUrl]: { ...prev[cleanedUrl], messages: [...(prev[cleanedUrl]?.messages || []), userMsg] }
    }));

    setLoading(true);
    setQuestion("");

    try {
      const transcriptResponse = await axios.get(`${API_URL}/transcript`, {
        params: { url: cleanedUrl },
        headers: { Authorization: `Bearer ${token}` },
      });
      const resp = await axios.post(`${API_URL}/chat`, {
        url: cleanedUrl,
        video_title: transcriptResponse.data.title,
        question: currentQuestion,
        transcript_text: transcriptResponse.data.transcript_text,
      }, { headers: { Authorization: `Bearer ${token}` } });
      const aiMsg = { role: "assistant", content: resp.data.answer };

      setChatHistory(prev => ({
        ...prev,
        [cleanedUrl]: { title: resp.data.title || prev[cleanedUrl]?.title || cleanedUrl, messages: [...(prev[cleanedUrl]?.messages || []), aiMsg] }
      }));
    } catch (err) {
      const serverMessage = err?.response?.data?.detail;
      const errMsg = { role: "assistant", content: "Error: " + (serverMessage ?? err?.message ?? "unknown error") };
      setChatHistory(prev => ({
        ...prev,
        [cleanedUrl]: { ...prev[cleanedUrl], messages: [...(prev[cleanedUrl]?.messages || []), errMsg] }
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
    <div className={`app-wrapper ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
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
              title={chatHistory[chatUrl].title}
            >
              <div className="history-item-main" onClick={() => loadChat(chatUrl)} style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                <Video size={16} className="history-icon" />
                <div className="history-url">{chatHistory[chatUrl].title}</div>
              </div>
              <button
                className="delete-history-btn"
                onClick={(event) => {
                  event.stopPropagation();
                  handleDeleteChatRequest(chatUrl, chatHistory[chatUrl].title);
                }}
                aria-label={`Delete chat for ${chatHistory[chatUrl].title}`}
                title="Delete chat"
              >
                <Trash2 size={14} />
              </button>
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
        <button className="share-btn" onClick={handleShare} disabled={!normalizeYouTubeUrl(url)}>
          <Share2 size={15} />
          <span>{shareState}</span>
        </button>
      </header>
      
      {deleteConfirmUrl && (
        <div className="delete-confirm-overlay" onClick={() => setDeleteConfirmUrl(null)}>
          <div className="delete-confirm-modal" onClick={(event) => event.stopPropagation()}>
            <div className="delete-confirm-icon"><Trash2 size={22} /></div>
            <h3>Delete this chat?</h3>
            <p>{deleteConfirmTitle}</p>
            <div className="delete-confirm-actions">
              <button className="secondary-action-btn" onClick={() => setDeleteConfirmUrl(null)}>Cancel</button>
              <button className="danger-action-btn" onClick={confirmDeleteChat}>Delete</button>
            </div>
          </div>
        </div>
      )}

      <div className="chat-container">
        <div className="chat-box">
          {messages.length === 0 && (
            <div className="empty-state">
              <h3>How can I help you today?</h3>
              <p>Enter a YouTube URL below and ask me to summarize, explain, or answer questions about it.</p>
            </div>
          )}
          
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              {msg.role === "user" && <div className="message-avatar"><User size={18} /></div>}
              <div className="message-content">
                {msg.role === "assistant" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{msg.content}</ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          
          {loading && (
            <div className="message assistant">
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
