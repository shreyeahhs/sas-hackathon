import React, { useMemo, useState } from 'react'

type Props = { onClose: () => void }

type Prefs = {
  mood: string
  groupSize: number
  budget: 'low' | 'medium' | 'high'
}

const MOODS = [
  'Chill', 'High-energy', 'Romantic', 'Artsy', 'Foodie', 'Live music', 'Comedy', 'Outdoors', 'Hidden gems', 'Surprise me'
]

export const AIWizardModal: React.FC<Props> = ({ onClose }) => {
  const [mood, setMood] = useState('Chill')
  const [customMood, setCustomMood] = useState('')
  const [groupSize, setGroupSize] = useState(2)
  const [budget, setBudget] = useState<'low'|'medium'|'high'>('medium')

  const effectiveMood = useMemo(() => customMood.trim() || mood, [customMood, mood])

  const save = () => {
    const prefs: Prefs = { mood: effectiveMood, groupSize, budget }
    try {
      localStorage.setItem('nightout:ai_prefs', JSON.stringify(prefs))
    } catch {}
    // Also pass via query params for visibility
    const params = new URLSearchParams({
      mood: prefs.mood,
      groupSize: String(prefs.groupSize),
      budget: prefs.budget,
    })
    window.location.href = `/chat.html?${params.toString()}`
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>AI Mode</h3>
        <p style={{ color: '#9aa3b2' }}>Tell us a bit and we’ll craft tonight’s plan: events + venues + a smooth route.</p>

        <div style={{ display: 'grid', gap: 14 }}>
          <div>
            <div style={{ marginBottom: 8, color: '#c8d2e0' }}>Mood</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {MOODS.map(m => (
                <button key={m} className={`badge ${mood === m ? 'selected' : ''}`} onClick={() => setMood(m)}>{m}</button>
              ))}
            </div>
            <div style={{ marginTop: 10 }}>
              <input
                placeholder="Or type your vibe..."
                value={customMood}
                onChange={e => setCustomMood(e.target.value)}
                style={{ width: '100%' }}
              />
            </div>
          </div>

          <div>
            <div style={{ marginBottom: 8, color: '#c8d2e0' }}>Group size</div>
            <input type="number" min={1} max={50} value={groupSize} onChange={e => setGroupSize(Number(e.target.value))} />
          </div>

          <div>
            <div style={{ marginBottom: 8, color: '#c8d2e0' }}>Budget</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {(['low','medium','high'] as const).map(b => (
                <button key={b} className={`badge ${budget === b ? 'selected' : ''}`} onClick={() => setBudget(b)}>
                  {b === 'low' ? '£' : b === 'medium' ? '££' : '£££'}
                </button>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
            <button className="button secondary" onClick={onClose}>Cancel</button>
            <button className="button" onClick={save}>Start planning</button>
          </div>
        </div>
      </div>
    </div>
  )
}
