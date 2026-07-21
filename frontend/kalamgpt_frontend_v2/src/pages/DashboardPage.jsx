import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

export function DashboardPage() {
  const navigate = useNavigate();
  const { token, user, logout } = useAuth();
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchChatHistory();
  }, [token]);

  const fetchChatHistory = async () => {
    try {
      const res = await fetch(`${API_URL}/history`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setChatHistory(data.history || []);
      }
    } catch (err) {
      console.error('Failed to fetch history:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const startNewChat = () => {
    navigate('/chat');
  };

  return (
    <div className="dashboard">
      {/* Navbar */}
      <div className="navbar">
        <div className="navbar-brand">🚀 Kalam GPT</div>
        <div className="navbar-user">
          <span className="user-email">{user?.email || 'User'}</span>
          <button className="btn btn-logout" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="chat-area">
        <div style={{ maxWidth: '600px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '20px', textAlign: 'center' }}>
            Welcome, {user?.name || 'Friend'}!
          </h2>

          <button className="btn btn-primary" onClick={startNewChat} style={{ width: '100%', marginBottom: '40px' }}>
            💬 Start New Chat
          </button>

          <h3 style={{ fontSize: '1.1rem', marginBottom: '15px', color: 'var(--saffron)' }}>
            Chat History
          </h3>

          {loading ? (
            <p style={{ textAlign: 'center', color: 'var(--muted)' }}>Loading...</p>
          ) : chatHistory.length === 0 ? (
            <p style={{ textAlign: 'center', color: 'var(--muted)' }}>No chat history yet. Start a new conversation!</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
              {chatHistory.map((chat) => (
                <div
                  key={chat.id}
                  style={{
                    background: 'var(--navy-soft)',
                    border: '1px solid rgba(244,161,46,0.15)',
                    borderRadius: '8px',
                    padding: '12px 15px',
                    cursor: 'pointer',
                  }}
                  onClick={() => navigate(`/chat/${chat.id}`)}
                >
                  <p style={{ fontSize: '0.9rem', marginBottom: '5px', color: 'var(--ivory)' }}>
                    {chat.prompt.substring(0, 60)}...
                  </p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                    {new Date(chat.created_at).toLocaleDateString()}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
