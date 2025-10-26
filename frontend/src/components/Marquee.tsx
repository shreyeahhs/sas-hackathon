import React from 'react'
import type { EventItem } from '../types'

type Props = { events: EventItem[] }

export const Marquee: React.FC<Props> = ({ events }) => {
  // Return nothing if no events
  if (!events || events.length === 0) {
    console.log('[Marquee] No events provided')
    return null
  }
  
  console.log('[Marquee] Rendering with', events.length, 'events')
  
  // Double the events for seamless loop
  const doubled = [...events, ...events]
  
  return (
    <div className="marquee-container section" style={{ overflow: 'hidden' }}>
      {/* Label */}
      <div className="marquee-header">
        <span className="badge selected" style={{ fontSize: 12, padding: '6px 10px' }}>Recommendations ✨</span>
      </div>
      <div className="marquee-track-cards">
        {doubled.map((event, i) => (
          <div 
            key={i} 
            className="marquee-card"
            onClick={() => event.url && window.open(event.url, '_blank')}
            style={{ cursor: event.url ? 'pointer' : 'default' }}
          >
            {event.image_url && !event.image_url.includes('logo-wog') && !event.image_url.includes('placeholder') ? (
              <img 
                src={event.image_url} 
                alt={event.title} 
                style={{ width: '100%', height: 120, objectFit: 'cover', borderRadius: '8px 8px 0 0' }}
                onError={(e) => {
                  // Replace with placeholder on error
                  const target = e.target as HTMLImageElement
                  target.style.display = 'none'
                  target.parentElement?.querySelector('.img-placeholder')?.removeAttribute('style')
                }}
              />
            ) : null}
            <div 
              className="img-placeholder"
              style={{ 
                width: '100%', 
                height: 120, 
                background: 'linear-gradient(135deg, #1a1f2b 0%, #2b3242 100%)', 
                borderRadius: '8px 8px 0 0', 
                display: event.image_url ? 'none' : 'flex', 
                alignItems: 'center', 
                justifyContent: 'center' 
              }}
            >
              <span style={{ fontSize: 32, opacity: 0.3 }}>🎭</span>
            </div>
            <div style={{ padding: '8px 10px' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#e7ecf3', lineHeight: 1.3 }}>{event.title}</div>
              <div style={{ fontSize: 11, color: '#9aa3b2', marginTop: 4 }}>{event.venue}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
