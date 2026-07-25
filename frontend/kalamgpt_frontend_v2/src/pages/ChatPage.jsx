import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../context/AuthContext'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api'

const suggestedPrompts = [
  'What dreams did you have as a child?',
  'How can youth contribute to nation building?',
  'What is your vision for India\'s future?',
  'What advice do you have for students?',
]

export default function ChatPage() {
  const { chatId } = useParams()
  const navigate = useNavigate()
  const { token } = useAuth()
  const [history, setHistory] = useState([])
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [playingId, setPlayingId] = useState(null)
  const [sessionId, setSessionId] = useState(() => {
    return chatId || `session-${Date.now()}`
  })
  const bottomRef = useRef(null)
  const recognitionRef = useRef(null)

  // Initialize Speech Recognition
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition()
      recognition.continuous = false
      recognition.interimResults = true
      recognition.lang = 'en-US'

      recognition.onstart = () => {
        setIsListening(true)
      }

      recognition.onresult = (event) => {
        let interimTranscript = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            setPrompt((prev) => prev + transcript + ' ')
          } else {
            interimTranscript += transcript
          }
        }
      }

      recognition.onend = () => {
        setIsListening(false)
      }

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
      }

      recognitionRef.current = recognition
    }
  }, [])

  // Scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  // Load historical chat
  useEffect(() => {
    if (chatId) {
      fetchHistoricalChat(chatId)
    }
  }, [chatId, token])

  const fetchHistoricalChat = async (id) => {
    try {
      const res = await fetch(`${API_URL}/chat/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const data = await res.json()
        setHistory(data.chat || [])
      }
    } catch (err) {
      console.error('Failed to fetch chat:', err)
    }
  }

  // Start listening to microphone
  const handleMicClick = () => {
    if (recognitionRef.current) {
      if (isListening) {
        recognitionRef.current.stop()
        setIsListening(false)
      } else {
        setPrompt('')
        recognitionRef.current.start()
      }
    }
  }

  // Send message
  const handleSendMessage = async (e) => {
    e.preventDefault()
    if (!prompt.trim() || loading) return

    const userMessage = prompt
    setPrompt('')
    setHistory([...history, { role: 'user', text: userMessage }])
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ 
          prompt: userMessage,
          session_id: sessionId 
        }),
      })

      const data = await res.json()
      if (res.ok) {
        setHistory((prev) => [
          ...prev,
          { role: 'kalam', text: data.response, id: data.chat_id },
        ])
        if (data.session_id) setSessionId(data.session_id)
      }
    } catch (err) {
      console.error('Failed to send message:', err)
    } finally {
      setLoading(false)
    }
  }

  // Play voice response
  const handlePlayVoice = async (messageText, messageId) => {
    if (playingId === messageId) {
      const audio = document.getElementById(`audio-${messageId}`)
      if (audio) audio.pause()
      setPlayingId(null)
      return
    }

    setPlayingId(messageId)

    try {
      const res = await fetch(`${API_URL}/text-to-speech`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ text: messageText }),
      })

      if (res.ok) {
        const blob = await res.blob()
        const audioUrl = URL.createObjectURL(blob)
        const audio = new Audio(audioUrl)
        
        audio.onended = () => setPlayingId(null)
        audio.play()
      } else {
        setPlayingId(null)
        alert('Voice not available')
      }
    } catch (err) {
      console.error('Failed to play voice:', err)
      setPlayingId(null)
    }
  }

  return (
    <div className="chat-shell">
      <div className="chat-header">
        <div className="chat-header-inner">
          <button
            onClick={() => navigate('/dashboard')}
            className="back-pill"
          >
            ← Dashboard
          </button>
          <div className="header-title">
            <span className="eyebrow">A voice-led conversation</span>
            <h1>Chat with Kalam</h1>
          </div>
          <div className="header-spacer" />
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-thread">
          <AnimatePresence>
            {history.length === 0 && !loading ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="empty-state"
              >
                <div className="empty-state-glow" />
                <p className="empty-kicker">Thoughtful, calm, and a little luminous</p>
                <h2>Ask with curiosity</h2>
                <p>
                  Explore ideas around science, leadership, dreams, and the future of India.
                  You can speak or type your question.
                </p>

                <div className="prompt-grid">
                  {suggestedPrompts.map((suggestion, i) => (
                    <motion.button
                      key={i}
                      onClick={() => setPrompt(suggestion)}
                      whileHover={{ scale: 1.03, y: -2 }}
                      className="prompt-chip"
                    >
                      {suggestion}
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            ) : (
              history.map((msg, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`message-row ${msg.role === 'user' ? 'message-row-user' : 'message-row-assistant'}`}
                >
                  <div
                    className={`message-bubble ${
                      msg.role === 'user' ? 'message-bubble-user' : 'message-bubble-assistant'
                    }`}
                  >
                    <p>{msg.text}</p>

                    {msg.role === 'kalam' && (
                      <div className="message-actions">
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          onClick={() => handlePlayVoice(msg.text, msg.id || i)}
                          className={`chip-pill ${playingId === (msg.id || i) ? 'chip-pill-active' : ''}`}
                        >
                          {playingId === (msg.id || i) ? '⏸️ Stop' : '🔊 Listen'}
                        </motion.button>
                        <div className="chip-pill chip-pill-muted">📄 Text</div>
                      </div>
                    )}
                  </div>
                </motion.div>
              ))
            )}
          </AnimatePresence>

          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="loader-card"
            >
              <div className="loader-dots">
                {[...Array(3)].map((_, i) => (
                  <motion.div
                    key={i}
                    animate={{ y: [0, -8, 0] }}
                    transition={{
                      duration: 0.6,
                      delay: i * 0.1,
                      repeat: Infinity,
                    }}
                    className="loader-dot"
                  />
                ))}
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSendMessage} className="composer">
          <motion.button
            type="button"
            onClick={handleMicClick}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.95 }}
            className={`mic-button ${isListening ? 'mic-button-listening' : ''}`}
            disabled={loading}
            title="Click to speak"
          >
            {isListening ? '🎙️' : '🎤'}
          </motion.button>

          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={isListening ? 'Listening...' : 'Ask Kalam...'}
            className="composer-input"
            disabled={loading || isListening}
          />

          <motion.button
            type="submit"
            disabled={loading || isListening}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.95 }}
            className="send-button"
          >
            Send
          </motion.button>
        </form>

        {isListening && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="listening-status"
          >
            🎙️ Listening... Click the mic again to stop.
          </motion.div>
        )}
      </div>
    </div>
  )
}