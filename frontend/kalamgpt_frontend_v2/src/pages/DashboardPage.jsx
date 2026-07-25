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
    <div className="min-h-screen bg-bg pt-20">
      {/* Header */}
      <div className="max-w-6xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-12"
        >
          <h1 className="text-4xl font-display italic text-text-primary mb-4">
            Welcome back, {user?.name || 'User'}
          </h1>
          <p className="text-muted">{user?.email}</p>
        </motion.div>

        {/* CTA Buttons */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="flex gap-4 mb-12"
        >
          <button
            onClick={() => navigate('/chat')}
            className="px-8 py-3 bg-accent-gradient text-bg rounded-lg font-medium hover:opacity-90 transition-opacity"
          >
            Start New Chat
          </button>
          <button
            onClick={() => {
              logout()
              navigate('/login')
            }}
            className="px-8 py-3 border border-stroke rounded-lg text-text-primary hover:bg-stroke/20 transition-colors"
          >
            Logout
          </button>
        </motion.div>

        {/* Chat History */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <h2 className="text-2xl font-display italic text-text-primary mb-6">
            Recent Conversations
          </h2>
          
          {loading ? (
            <p className="text-muted">Loading...</p>
          ) : history.length === 0 ? (
            <p className="text-muted">No conversations yet. Start a new chat!</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {history.map((chat) => (
                <motion.button
                  key={chat.id}
                  onClick={() => navigate(`/chat/${chat.id}`)}
                  whileHover={{ scale: 1.05 }}
                  className="p-6 bg-surface border border-stroke rounded-2xl text-left hover:border-accent transition-all group"
                >
                  <p className="text-sm text-muted group-hover:text-accent transition-colors mb-2">
                    {new Date(chat.created_at).toLocaleDateString()}
                  </p>
                  <p className="text-text-primary font-medium truncate mb-2">
                    {chat.preview || 'Chat'}
                  </p>
                  <p className="text-xs text-muted">
                    {chat.message_count} messages
                  </p>
                </motion.button>
              ))}
            </div>
          )}
        </motion.div>
      </div>
    </div>
  )
}