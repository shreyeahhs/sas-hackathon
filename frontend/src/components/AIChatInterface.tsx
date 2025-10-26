import React, { useEffect, useRef, useState } from 'react'
import aiAvatar from '../../image-removebg-preview (1).png'

type Message = {
  role: 'assistant' | 'user'
  content: string
  recommendations?: Array<any>  // Can be events or venues with different shapes
  suggestions?: string[]
}

type Props = {
  onClose: () => void
}

const CHATBOT_API = 'http://localhost:8000/chat'

export const AIChatInterface: React.FC<Props> = ({ onClose }) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => `session-${Date.now()}-${Math.random().toString(36).slice(2)}`)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [initialized, setInitialized] = useState(false)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Initialize the conversation with a greeting from the backend
  useEffect(() => {
    if (!initialized) {
      setInitialized(true)
      // Send initial greeting request without showing as user message
      const initChat = async () => {
        setLoading(true)
        try {
          const res = await fetch(CHATBOT_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              message: 'start',
              session_id: sessionId
            })
          })
          if (res.ok) {
            const data = await res.json()
            const assistantMsg: Message = {
              role: 'assistant',
              content: data.reply || "Hi! I'm Scott.",
              recommendations: data.recommendations || [],
              suggestions: data.suggestions || []
            }
            setMessages([assistantMsg])
          }
        } catch (err) {
          console.error('Init error:', err)
        } finally {
          setLoading(false)
        }
      }
      initChat()
    }
  }, [initialized, sessionId])

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return

    const userMsg: Message = { role: 'user', content: text.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    console.log(`[CHAT] Sending message: "${text}" with session_id: ${sessionId}`)

    try {
      const res = await fetch(CHATBOT_API, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text.trim(),
          session_id: sessionId
        })
      })

      if (!res.ok) throw new Error(`Chat API error: ${res.status}`)

      const data = await res.json()
      console.log(`[CHAT] Response:`, data)
      const assistantMsg: Message = {
        role: 'assistant',
        content: data.reply || "Scott here to help!",
        recommendations: data.recommendations || [],
        suggestions: data.suggestions || []
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch (err: any) {
      console.error('Chat error:', err)
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "Sorry, I'm having trouble connecting. Please try again."
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal chat-modal glassmorphism animate-scale-in shadow-bubble" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="chat-header gradient-secondary">
          <div className="chat-title">
            <img src={aiAvatar} alt="Scott" style={{ width: 28, height: 28, borderRadius: 8, objectFit: 'cover', border: '1px solid #2b3242' }} />
            <div>
              <div style={{ fontWeight: 800 }}>Scott</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--muted)' }}>
                <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: 999, background: '#22c55e' }} />
                <span>Glasgow NightOut AI</span>
              </div>
            </div>
          </div>
          <div className="chat-actions">
            <button className="button ghost" onClick={onClose} title="Close">×</button>
          </div>
        </div>

        {/* Messages */}
        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`chat-row ${msg.role === 'user' ? 'user' : 'assistant'}`}>
              <div className={`bubble ${msg.role === 'user' ? 'user' : 'assistant'}`}>
                <div style={{ lineHeight: 1.5 }}>{msg.content}</div>
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {msg.suggestions.map((sug, k) => (
                      <button key={k} className="badge outline" onClick={() => sendMessage(sug)} style={{ cursor: 'pointer' }}>
                        {sug}
                      </button>
                    ))}
                  </div>
                )}

                {msg.recommendations && msg.recommendations.length > 0 && (
                  <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
                    {msg.recommendations.map((rec, j) => {
                      const isEvent = 'title' in rec
                      const displayTitle = isEvent ? rec.title : rec.name
                      const displayImage = isEvent ? rec.image_url : rec.image
                      const displayDetails = isEvent 
                        ? `${rec.date} · ${rec.venue}${rec.categories?.length ? ' · ' + rec.categories.join(', ') : ''}`
                        : `${rec.rating ? '⭐ ' + rec.rating : ''} ${rec.price || ''} · ${rec.address || ''}`
                      const displayDesc = isEvent ? rec.description : (rec.categories || []).join(' · ')
                      const displayLink = isEvent ? rec.link : rec.url
                      const displayMapsUrl = isEvent ? rec.maps_url : null

                      return (
                        <div key={j} className="card" style={{ cursor: 'default' }}>
                          {displayImage && <img src={displayImage} alt={displayTitle} style={{ width: '100%', height: 140, objectFit: 'cover' }} />}
                          <div style={{ padding: 12 }}>
                            <div style={{ fontWeight: 700, marginBottom: 4 }}>{displayTitle}</div>
                            <div className="meta" style={{ marginBottom: 4 }}>{displayDetails}</div>
                            {displayDesc && <div className="desc" style={{ marginBottom: 8 }}>{displayDesc}</div>}
                            <div style={{ display: 'flex', gap: 8 }}>
                              {displayLink && (
                                <a href={displayLink} target="_blank" rel="noreferrer" className="button" style={{ fontSize: 12, padding: '6px 10px' }}>
                                  {isEvent ? 'Learn More' : 'View Details'}
                                </a>
                              )}
                              {displayMapsUrl && (
                                <a href={displayMapsUrl} target="_blank" rel="noreferrer" className="button secondary" style={{ fontSize: 12, padding: '6px 10px' }}>
                                  View Location
                                </a>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ color: 'var(--muted)', fontStyle: 'italic' }}>AI is thinking...</div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="chat-inputbar">
          <input
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything..."
            disabled={loading}
          />
          <button className="button icon gradient-primary" onClick={() => sendMessage(input)} disabled={loading || !input.trim()} title="Send">
            <span style={{ transform: 'translateX(1px)' }}>➤</span>
          </button>
        </div>
      </div>
    </div>
  )
}
