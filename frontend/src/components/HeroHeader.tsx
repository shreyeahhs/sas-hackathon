import React from 'react'

interface HeroHeaderProps {
  onOpenAI?: () => void
}

export const HeroHeader: React.FC<HeroHeaderProps> = ({ onOpenAI }) => {
  return (
    <div className="hero-header">
      <div className="hero-content">
        <h1 className="hero-title">Your Perfect Night Out</h1>
        <p className="hero-subtitle">
          Discover the best events, venues, and experiences in Glasgow.<br />
          From live music to dining, we've got your evening covered.
        </p>
        <button
          className="button hero-cta gradient-primary"
          onClick={() => onOpenAI && onOpenAI()}
        >
          Plan Your Night Out with Scott
        </button>
      </div>
    </div>
  )
}
