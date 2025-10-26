import React from 'react'
import type { EventItem } from '../types'
import type { WeatherData } from '../api'
import { FiltersBar } from './FiltersBar'
import { EventCard } from './EventCard'
import { Pagination } from './Pagination'
import { Marquee } from './Marquee'
import { HeroHeader } from './HeroHeader'
import { WeatherBanner } from './WeatherBanner'

interface ResultsPageProps {
  events: EventItem[]
  totalCount: number
  loading: boolean
  error: string | null
  categories: string[]
  category: string
  onCategoryChange: (c: string) => void
  query: string
  onQueryChange: (q: string) => void
  page: number
  totalPages: number
  onPageChange: (p: number) => void
  onBack?: () => void
  marqueeEvents?: EventItem[]
  onOpenAI?: () => void
  showHero?: boolean
  weather?: WeatherData | null
}

export const ResultsPage: React.FC<ResultsPageProps> = ({
  events,
  totalCount,
  loading,
  error,
  categories,
  category,
  onCategoryChange,
  query,
  onQueryChange,
  page,
  totalPages,
  onPageChange,
  onBack,
  marqueeEvents,
  onOpenAI,
  showHero = true,
  weather,
}) => {
  const handleBack = () => {
    // Legacy: previously used for a "New Search" button. Kept for API compatibility.
    if (onBack) onBack()
  }

  return (
    <div>
      {/* Professional Top Header */}
      <div className="top-header">
        <div className="container">
          <div className="top-header-inner">
            <div className="brand-section">
              <div className="brand-name">
                <span className="gradient-text">Glas</span>
                <span className="brand-lets">Let's</span>
                <span className="gradient-text">gow</span>
              </div>
              <div className="brand-tagline">Where plans and pints meet.</div>
            </div>
            {/* removed top AI button */}
          </div>
        </div>
      </div>

      {/* Weather Banner */}
      <WeatherBanner weather={weather || null} />

      {/* Hero Header - shown by default, can be hidden with showHero={false} */}
      {showHero && <HeroHeader onOpenAI={onOpenAI} />}

      {/* Content */}
      <div className="container page fab-safe-bottom">
        {/* Summary */}
        <div className="section">
          <h1 className="section-title" style={{ fontSize: 28 }}>
            {category ? (
              <>Showing <strong>{totalCount}</strong> <em>{category}</em> events</>
            ) : (
              <>Top picks for tonight</>
            )}
          </h1>
          <div className="section-subtitle">
            {query ? (
              <>Search: “{query}” · </>
            ) : null}
            Total results: <strong>{totalCount}</strong>
          </div>
        </div>

        {/* Marquee shifted down below header and summary */}
        {marqueeEvents && marqueeEvents.length > 0 ? (
          <div className="section">
            <Marquee events={marqueeEvents} />
          </div>
        ) : null}

        {/* Filter Bar */}
        <div className="section">
          <FiltersBar
            categories={categories}
            category={category}
            onCategoryChange={onCategoryChange}
            query={query}
            onQueryChange={onQueryChange}
          />
        </div>

        {/* Results */}
        {loading ? (
          <div>Loading events…</div>
        ) : error ? (
          <div style={{ color: '#ff6b6b' }}>Error: {error}</div>
        ) : (
          <>
            <div className="grid">
              {events.map((ev) => (
                <EventCard key={`${ev.title}-${ev.date}-${ev.venue}`} event={ev} />
              ))}
            </div>
            <Pagination page={page} totalPages={totalPages} onPageChange={onPageChange} />
          </>
        )}
      </div>
    </div>
  )
}
