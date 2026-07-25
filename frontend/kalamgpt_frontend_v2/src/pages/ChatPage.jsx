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
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Header */}
      <div className="fixed top-0 left-0 right-0 z-40 bg-bg/80 backdrop-blur-md border-b border-stroke/30">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/dashboard')}
            className="text-sm text-muted hover:text-text-primary transition-colors"
          >
            ← Back to Dashboard
          </button>
          <h1 className="font-display italic text-text-primary">Chat with Kalam</h1>
          <div className="w-12" />
        </div>
      </div>

      {/* Chat Container */}
      <div className="flex-1 max-w-4xl mx-auto w-full flex flex-col pt-24 pb-6 px-6">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto mb-6 space-y-6">
          <AnimatePresence>
            {history.length === 0 && !loading ? (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center h-full text-center"
              >
                <h2 className="text-2xl font-display italic text-text-primary mb-4">
                  Chat with Kalam
                </h2>
                <p className="text-muted mb-8 max-w-md">
                  Ask me anything about science, dreams, vision, leadership, or India's future. 
                  You can speak or type your questions!
                </p>

                {/* Suggested Prompts */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {suggestedPrompts.map((suggestion, i) => (
                    <motion.button
                      key={i}
                      onClick={() => setPrompt(suggestion)}
                      whileHover={{ scale: 1.05 }}
                      className="p-4 bg-surface border border-stroke rounded-lg text-left hover:border-accent transition-all text-sm text-text-primary hover:bg-surface/80"
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
                  className={`flex ${
                    msg.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-xs md:max-w-2xl px-6 py-4 rounded-2xl ${
                      msg.role === 'user'
                        ? 'bg-accent-gradient text-bg'
                        : 'bg-surface border border-stroke text-text-primary'
                    }`}
                  >
                    <p className="text-sm leading-relaxed mb-2">{msg.text}</p>
                    
                    {/* Voice/Text Options for Kalam responses */}
                    {msg.role === 'kalam' && (
                      <div className="flex gap-2 mt-3">
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          onClick={() => handlePlayVoice(msg.text, msg.id || i)}
                          className={`text-xs px-3 py-1 rounded-full transition-all ${
                            playingId === (msg.id || i)
                              ? 'bg-accent-gradient text-bg'
                              : 'bg-black/20 hover:bg-black/30 text-text-primary'
                          }`}
                        >
                          {playingId === (msg.id || i) ? '⏸️ Stop' : '🔊 Listen'}
                        </motion.button>
                        <div className="text-xs px-3 py-1 rounded-full bg-black/20 text-text-primary">
                          📄 Text
                        </div>
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
              className="flex justify-start"
            >
              <div className="bg-surface border border-stroke px-6 py-4 rounded-2xl">
                <div className="flex gap-2">
                  {[...Array(3)].map((_, i) => (
                    <motion.div
                      key={i}
                      animate={{ y: [0, -8, 0] }}
                      transition={{
                        duration: 0.6,
                        delay: i * 0.1,
                        repeat: Infinity,
                      }}
                      className="w-2 h-2 bg-muted rounded-full"
                    />
                  ))}
                </div>
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input Section */}
        <form
          onSubmit={handleSendMessage}
          className="flex gap-2 bg-surface border border-stroke rounded-full p-2"
        >
          {/* Microphone Button - LEFT SIDE */}
          <motion.button
            type="button"
            onClick={handleMicClick}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            className={`px-4 py-3 rounded-full transition-all ${
              isListening
                ? 'bg-red-500 text-white animate-pulse'
                : 'bg-surface hover:bg-stroke/50 text-text-primary'
            }`}
            disabled={loading}
            title="Click to speak"
          >
            {isListening ? '🎙️' : '🎤'}
          </motion.button>

          {/* Text Input */}
          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={isListening ? 'Listening...' : 'Ask Kalam...'}
            className="flex-1 bg-transparent px-6 py-3 text-text-primary placeholder-muted focus:outline-none"
            disabled={loading || isListening}
          />

          {/* Send Button - RIGHT SIDE */}
          <motion.button
            type="submit"
            disabled={loading || isListening}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="px-6 py-3 bg-accent-gradient text-bg rounded-full font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            Send
          </motion.button>
        </form>

        {/* Microphone Status */}
        {isListening && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center text-sm text-accent mt-2"
          >
            🎙️ Listening... Click mic again to stop
          </motion.div>
        )}
      </div>
    </div>
  )
}