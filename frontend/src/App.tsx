import React, { useEffect, useMemo, useRef, useState } from 'react'
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

  // FAB drag state
  const [fabPosition, setFabPosition] = useState({ x: 0, y: 0 })
  const [fabDragging, setFabDragging] = useState(false)
  const [fabDragOffset, setFabDragOffset] = useState({ x: 0, y: 0 })
  const [fabMoved, setFabMoved] = useState(false)
  const fabStartRef = useRef<{ x: number; y: number } | null>(null)

  // Fetch weather on mount
  useEffect(() => {
    (async () => {
      const weatherData = await fetchWeather()
      setWeather(weatherData)
    })()
  }, [])

  // FAB drag handlers
  const handleFabMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setFabDragging(true)
    const target = e.currentTarget as HTMLElement
    const rect = target.getBoundingClientRect()
    setFabDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    })
    setFabMoved(false)
    fabStartRef.current = { x: e.clientX, y: e.clientY }
  }

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!fabDragging) return
      setFabPosition({
        x: e.clientX - fabDragOffset.x,
        y: e.clientY - fabDragOffset.y
      })
      if (!fabMoved && fabStartRef.current) {
        const dx = e.clientX - fabStartRef.current.x
        const dy = e.clientY - fabStartRef.current.y
        if (Math.sqrt(dx * dx + dy * dy) > 5) {
          setFabMoved(true)
        }
      }
    }

    const handleMouseUp = () => {
      setFabDragging(false)
    }

    if (fabDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [fabDragging, fabDragOffset])

  const handleFabClick = (e: React.MouseEvent) => {
    // If the user dragged (moved beyond threshold), suppress this click
    if (fabMoved) {
      e.preventDefault()
      e.stopPropagation()
      // Reset moved shortly after so future clicks work
      setTimeout(() => setFabMoved(false), 50)
      return
    }
    setShowAI(true)
  }

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
        style={{ 
          background: 'transparent', 
          borderRadius: 0, 
          width: 64, 
          height: 64, 
          padding: 0,
          position: 'fixed',
          left: (fabPosition.x !== 0 || fabPosition.y !== 0) ? fabPosition.x : undefined,
          top: (fabPosition.x !== 0 || fabPosition.y !== 0) ? fabPosition.y : undefined,
          bottom: (fabPosition.x !== 0 || fabPosition.y !== 0) ? undefined : 24,
          right: (fabPosition.x !== 0 || fabPosition.y !== 0) ? undefined : 24,
          cursor: fabDragging ? 'grabbing' : 'grab'
        }}
        onMouseDown={handleFabMouseDown}
        onClick={handleFabClick}
        title="Scott"
      >
        <img src={aiAvatar} alt="AI" style={{ width: '100%', height: '100%', borderRadius: 0, objectFit: 'cover', pointerEvents: 'none' }} />
      </button>
    </div>
  )
}
