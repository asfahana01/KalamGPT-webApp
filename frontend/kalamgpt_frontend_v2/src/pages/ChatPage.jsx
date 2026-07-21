import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useParams } from 'react-router-dom';

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:5000/api";

const QUOTES = [
  "Dream, dream, dream. Dreams transform into thoughts, and thoughts result in action.",
  "You have to dream before your dreams can come true.",
  "Excellence is a continuous process and not an accident.",
  "The best brains of the nation may be found on the last benches of the classroom.",
];

function QuoteBar() {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % QUOTES.length), 8000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="quote-bar">
      <span className="quote-mark">"</span>
      <span className="quote-text">{QUOTES[idx]}</span>
      <span className="quote-mark">"</span>
    </div>
  );
}

function Message({ role, text }) {
  const isKalam = role === "kalam";
  return (
    <div className={`message-row ${isKalam ? "kalam-row" : "user-row"}`}>
      {isKalam && <div className="avatar kalam-avatar">🚀</div>}
      <div className={`bubble ${isKalam ? "kalam-bubble" : "user-bubble"}`}>
        <p>{text}</p>
      </div>
      {!isKalam && <div className="avatar user-avatar">🎓</div>}
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="message-row kalam-row">
      <div className="avatar kalam-avatar">🚀</div>
      <div className="bubble kalam-bubble typing-bubble">
        <span className="dot" />
        <span className="dot" />
        <span className="dot" />
      </div>
    </div>
  );
}

function SuggestedPrompts({ onSelect }) {
  const prompts = [
    "What advice do you have for a student who has failed?",
    "How can India solve its education crisis?",
    "What is the connection between science and spirituality?",
    "Give me a bold idea to improve rural healthcare.",
  ];
  return (
    <div className="suggestions">
      <p className="suggestions-label">Ask Kalam about…</p>
      <div className="suggestions-grid">
        {prompts.map((p) => (
          <button key={p} className="suggestion-chip" onClick={() => onSelect(p)}>
            {p}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ChatPage() {
  const navigate = useNavigate();
  const { token } = useAuth();
  const [history, setHistory] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const { chatId } = useParams();

// Load historical chat if chatId is provided
useEffect(() => {
  if (chatId) {
    fetchHistoricalChat(chatId);
  }
}, [chatId, token]);

const fetchHistoricalChat = async (id) => {
  setLoading(true);
  try {
    const res = await fetch(`${API_URL}/chat/${id}`, {
      headers: { 'Authorization': `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setHistory(data.chat || []);
    }
  } catch (err) {
    console.error('Failed to fetch chat:', err);
  } finally {
    setLoading(false);
  }
};
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history, loading]);

  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  }, [prompt]);

  const ask = async (overridePrompt) => {
    const text = (overridePrompt || prompt).trim();
    if (!text || loading) return;

    setError(null);
    setHistory((h) => [...h, { role: "user", text }]);
    setPrompt("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ prompt: text }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Server error");
      }

      const data = await res.json();
      setHistory((h) => [...h, { role: "kalam", text: data.response }]);
    } catch (err) {
      setError(err.message || "Could not reach Kalam GPT. Is the backend running?");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  };

  const clearChat = () => {
    setHistory([]);
    setError(null);
  };

  const goToDashboard = () => {
    navigate('/dashboard');
  };

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-rocket">🚀</span>
            <div>
              <h1 className="logo-title">Kalam GPT</h1>
              <p className="logo-sub">Inspired by Dr. A.P.J. Abdul Kalam</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            {history.length > 0 && (
              <button className="clear-btn" onClick={clearChat}>
                New Chat
              </button>
            )}
            <button className="clear-btn" onClick={goToDashboard}>
              Dashboard
            </button>
          </div>
        </div>
        <QuoteBar />
      </header>

      <main className="chat-area">
        {history.length === 0 && !loading ? (
          <SuggestedPrompts onSelect={(p) => ask(p)} />
        ) : (
          <div className="messages">
            {history.map((m, i) => (
              <Message key={i} role={m.role} text={m.text} />
            ))}
            {loading && <TypingIndicator />}
            <div ref={bottomRef} />
          </div>
        )}
      </main>

      {error && (
        <div className="error-banner">
          ⚠️ {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <footer className="input-bar">
        <div className="input-inner">
          <textarea
            ref={textareaRef}
            className="input-textarea"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Kalam about science, youth, India, dreams…"
            rows={1}
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={() => ask()}
            disabled={loading || !prompt.trim()}
          >
            {loading ? (
              <span className="spinner" />
            ) : (
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <p className="input-hint">Enter to send · Shift+Enter for new line</p>
      </footer>
    </div>
  );
}
