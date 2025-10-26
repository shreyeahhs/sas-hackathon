import type { EventItem } from './types'
import type { WeatherData } from './api'

/**
 * Team14 Activity Metric: NightOut Score
 * 
 * A custom scoring algorithm that evaluates events based on:
 * - Weather Compatibility (40%): Indoor events during rain, outdoor in good weather
 * - Time Relevance (30%): Events happening soon are prioritized
 * - Category Appeal (20%): Popular categories get higher scores
 * - Venue Popularity (10%): Well-known venues score higher
 */

interface ScoreBreakdown {
  total: number
  weather: number
  time: number
  category: number
  venue: number
}

export function calculateNightOutScore(
  event: EventItem,
  weather: WeatherData | null,
  currentTime: Date = new Date()
): ScoreBreakdown {
  let weatherScore = 50 // Default neutral score
  let timeScore = 50
  let categoryScore = 50
  let venueScore = 50

  // === WEATHER COMPATIBILITY (40%) ===
  if (weather) {
    const isIndoorCategory = isIndoorEvent(event.categories)
    
    if (weather.isRaining) {
      // Boost indoor events when raining
      weatherScore = isIndoorCategory ? 95 : 30
    } else if (weather.isOutdoorFriendly) {
      // Boost outdoor events in good weather
      weatherScore = isIndoorCategory ? 60 : 95
    } else {
      // Neutral weather - slight preference for indoor
      weatherScore = isIndoorCategory ? 70 : 55
    }
  }

  // === TIME RELEVANCE (30%) ===
  // Events happening tonight or soon get higher scores
  const eventDate = event.date ? new Date(event.date) : null
  if (eventDate) {
    const hoursUntilEvent = (eventDate.getTime() - currentTime.getTime()) / (1000 * 60 * 60)
    
    if (hoursUntilEvent < 0) {
      // Event already started or passed
      timeScore = 20
    } else if (hoursUntilEvent <= 3) {
      // Happening very soon (next 3 hours)
      timeScore = 100
    } else if (hoursUntilEvent <= 6) {
      // Happening tonight (next 6 hours)
      timeScore = 85
    } else if (hoursUntilEvent <= 12) {
      // Later tonight
      timeScore = 65
    } else if (hoursUntilEvent <= 24) {
      // Tomorrow
      timeScore = 40
    } else {
      // Future events
      timeScore = 25
    }
  }

  // === CATEGORY APPEAL (20%) ===
  // Popular nightlife categories get higher scores
  const categories = event.categories || []
  const popularCategories = [
    'Music', 'Nightlife', 'Live Music', 'Club', 'Bar', 'Concert',
    'Comedy', 'Theatre', 'Food & Drink', 'Party', 'DJ'
  ]
  
  const hasPopularCategory = categories.some(cat => 
    popularCategories.some(pop => cat.toLowerCase().includes(pop.toLowerCase()))
  )
  
  if (hasPopularCategory) {
    categoryScore = 85
  } else if (categories.length > 0) {
    categoryScore = 60
  } else {
    categoryScore = 40
  }

  // === VENUE POPULARITY (10%) ===
  // Well-known venues or descriptive event names score higher
  const venueName = event.venue?.toLowerCase() || ''
  const eventTitle = event.title?.toLowerCase() || ''
  
  const popularVenueKeywords = [
    'club', 'arena', 'theatre', 'hall', 'bar', 'pub', 'live', 'festival'
  ]
  
  const hasPopularVenue = popularVenueKeywords.some(keyword => 
    venueName.includes(keyword) || eventTitle.includes(keyword)
  )
  
  venueScore = hasPopularVenue ? 80 : 50

  // Calculate weighted total score
  const totalScore = Math.round(
    (weatherScore * 0.40) +
    (timeScore * 0.30) +
    (categoryScore * 0.20) +
    (venueScore * 0.10)
  )

  return {
    total: Math.min(100, Math.max(0, totalScore)),
    weather: weatherScore,
    time: timeScore,
    category: categoryScore,
    venue: venueScore
  }
}

function isIndoorEvent(categories: string[]): boolean {
  const indoorKeywords = [
    'theatre', 'museum', 'gallery', 'cinema', 'comedy', 'club',
    'bar', 'pub', 'restaurant', 'shopping', 'arcade', 'bowling',
    'indoor', 'exhibition', 'art'
  ]
  
  return categories.some(cat => 
    indoorKeywords.some(keyword => cat.toLowerCase().includes(keyword))
  )
}

export function getScoreBadge(score: number): { emoji: string; label: string; color: string } {
  if (score >= 85) {
    return { emoji: '🔥', label: 'Hot Pick', color: '#ef4444' }
  } else if (score >= 70) {
    return { emoji: '⭐', label: 'Top Rated', color: '#f59e0b' }
  } else if (score >= 55) {
    return { emoji: '👍', label: 'Good Choice', color: '#10b981' }
  } else {
    return { emoji: '📍', label: 'Available', color: '#6b7280' }
  }
}

export function sortByNightOutScore(events: EventItem[], descending = true): EventItem[] {
  return [...events].sort((a, b) => {
    const scoreA = a.nightOutScore || 0
    const scoreB = b.nightOutScore || 0
    return descending ? scoreB - scoreA : scoreA - scoreB
  })
}
