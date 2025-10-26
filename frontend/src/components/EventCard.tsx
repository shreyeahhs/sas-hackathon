import React from 'react'
import type { EventItem } from '../types'

export const EventCard: React.FC<{ event: EventItem }> = ({ event }) => {
  return (
    <div className="card" onClick={() => window.open(event.url, '_blank')}>
      {event.image_url ? <img src={event.image_url} alt={event.title} /> : null}
      <div className="content">
        {/* NightOut Score Badge */}
        {event.nightOutScore !== undefined && event.scoreBadge && (
          <div className="score-badge" style={{ borderColor: event.scoreBadge.color }}>
            <span className="score-emoji">{event.scoreBadge.emoji}</span>
            <span className="score-label">{event.scoreBadge.label}</span>
            <span className="score-value">{event.nightOutScore}</span>
          </div>
        )}
        
        {/* Category chips for fun visual */}
        <div className="chips">
          {(event.categories?.length ? event.categories : [event.category]).slice(0,3).map((c) => (
            <span key={c} className="chip">{c}</span>
          ))}
        </div>
        <div className="title">{event.title}</div>
        <div className="meta">📅 {event.date}</div>
        <div className="meta">📍 {event.venue}</div>
        <div className="desc">{event.description}</div>
      </div>
    </div>
  )
}
