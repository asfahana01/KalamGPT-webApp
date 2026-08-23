import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

export default function DashboardPage() {
  const navigate = useNavigate()
  const { user, token, logout } = useAuth()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHistory()
  }, [token])

  const fetchHistory = async () => {
    try {
      const res = await fetch(`${API_URL}/history`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setHistory(data.history || [])
      }
    } catch (err) {
      console.error('Failed to fetch history:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="dashboard-shell">
      <div className="dashboard-content">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="hero-card"
        >
          <div className="hero-copy">
            <p className="hero-kicker">Curated conversations</p>
            <h1>Welcome back, {user?.name || 'User'}</h1>
            <p className="hero-subtitle">{user?.email}</p>
          </div>

          <div className="hero-actions">
            <button
              onClick={() => navigate('/chat')}
              className="primary-action"
            >
              Start New Chat
            </button>
            <button
              onClick={() => {
                logout()
                navigate('/login')
              }}
              className="secondary-action"
            >
              Logout
            </button>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="history-section"
        >
          <div className="section-heading">
            <h2>Recent Conversations</h2>
            <span>Resume where you left off</span>
          </div>

          {loading ? (
            <div className="history-empty">Loading your conversations…</div>
          ) : history.length === 0 ? (
            <div className="history-empty">No conversations yet. Start a new chat to begin.</div>
          ) : (
            <div className="history-grid">
              {history.map((chat, index) => (
                <motion.button
                  key={chat.id}
                  onClick={() => navigate(`/chat/${chat.id}`)}
                  whileHover={{ scale: 1.03, y: -2 }}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.05 * index }}
                  className="history-card"
                >
                  <p className="history-date">
                    {new Date(chat.created_at).toLocaleDateString()}
                  </p>
                  <p className="history-preview">{chat.preview || 'Chat'}</p>
                  <p className="history-meta">{chat.message_count} messages</p>
                </motion.button>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}