import React, { useEffect, useMemo, useState } from 'react'
import { fetchEvents, fetchMarqueeRecommendations, fetchWeather, type WeatherData } from './api'
import type { EventItem } from './types'
import { ResultsPage } from './components/ResultsPage'
import { AIChatInterface } from './components/AIChatInterface'
import aiAvatar from '../image-removebg-preview (1).png'
import { calculateNightOutScore, getScoreBadge } from './nightOutScore'

const PAGE_SIZE = 12

export const App: React.FC = () => {
  const [events, setEvents] = useState<EventItem[]>([])
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // filters & pagination
  const [category, setCategory] = useState<string>('')
  const [query, setQuery] = useState<string>('')
  const [debouncedQuery, setDebouncedQuery] = useState<string>('')
  const [page, setPage] = useState<number>(1)

  // AI modal
  const [showAI, setShowAI] = useState(false)

  // Weather data
  const [weather, setWeather] = useState<WeatherData | null>(null)

  // Fetch weather on mount
  useEffect(() => {
    (async () => {
      const weatherData = await fetchWeather()
      setWeather(weatherData)
    })()
  }, [])

  // Debounce query changes
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 350)
    return () => clearTimeout(t)
  }, [query])

  // Load events on filters change (debounced query)
  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await fetchEvents({ category: category || null, name: debouncedQuery || null })
        
        // Calculate NightOut Score for each event
        const scoredEvents = res.events.map(event => {
          const scoreData = calculateNightOutScore(event, weather)
          const badge = getScoreBadge(scoreData.total)
          return {
            ...event,
            nightOutScore: scoreData.total,
            scoreBadge: badge
          }
        })
        
        // Sort by score (highest first)
        const sortedEvents = scoredEvents.sort((a, b) => (b.nightOutScore || 0) - (a.nightOutScore || 0))
        
        setEvents(sortedEvents)
        setCategories(res.categories)
      } catch (e: any) {
        setError(e?.message || 'Failed to load events')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [category, debouncedQuery, weather])

  const totalPages = Math.max(1, Math.ceil(events.length / PAGE_SIZE))
  useEffect(() => { setPage(1) }, [category, debouncedQuery])

  const paginated = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE
    return events.slice(start, start + PAGE_SIZE)
  }, [events, page])

  // Curated marquee support with graceful fallback
  const [curated, setCurated] = useState<string[]>([])
  useEffect(() => {
    (async () => {
      const items = await fetchMarqueeRecommendations()
      setCurated(items || [])
    })()
  }, [])

  const marqueeEvents = useMemo(() => {
    // Randomize selection for marquee; pick up to 15
    const copy = [...events]
    for (let i = copy.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1))
      const t = copy[i]
      copy[i] = copy[j]
      copy[j] = t
    }
    return copy.slice(0, 15)
  }, [events])

  return (
    <div>
      <ResultsPage
        events={paginated}
        totalCount={events.length}
        loading={loading}
        error={error}
        categories={categories}
        category={category}
        onCategoryChange={setCategory}
        query={query}
        onQueryChange={setQuery}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        onBack={() => {
          setCategory('')
          setQuery('')
        }}
        marqueeEvents={marqueeEvents}
        onOpenAI={() => setShowAI(true)}
        weather={weather}
      />

      {showAI && <AIChatInterface onClose={() => setShowAI(false)} />}

      {/* Floating fun chat FAB */}
      <button
        aria-label="Open Scott"
        className="chat-fab"
        style={{ background: 'transparent', borderRadius: 0, width: 64, height: 64, padding: 0 }}
        onClick={() => setShowAI(true)}
        title="Scott"
      >
        <img src={aiAvatar} alt="AI" style={{ width: '100%', height: '100%', borderRadius: 0, objectFit: 'cover', pointerEvents: 'none' }} />
      </button>
    </div>
  )
}
