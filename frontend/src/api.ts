import type { EventsApiResponse } from './types'

const API_BASE = 'http://localhost:8000'

export async function fetchEvents(params: { category?: string | null; venue?: string | null; name?: string | null; page?: number; pageSize?: number }) {
  // Backend endpoint expects POST to /api/events/live with category, venue, today_only
  const res = await fetch(`${API_BASE}/api/events/live`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      category: params.category || null,
      venue: params.venue || params.name || null,
      today_only: true
    })
  })
  if (!res.ok) throw new Error(`Failed to fetch events: ${res.status}`)
  const data = (await res.json()) as EventsApiResponse
  return data
}

// Optional curated marquee recommendations. If the endpoint is missing, return [].
export async function fetchMarqueeRecommendations(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/api/recommendations/marquee`)
    if (!res.ok) return []
    const data = (await res.json()) as { items?: string[] } | string[]
    if (Array.isArray(data)) return data
    if (data && Array.isArray(data.items)) return data.items
    return []
  } catch {
    return []
  }
}

// Weather data types
export interface HourlyWeather {
  time: string
  temp: number
  icon: string
  condition: string
}

export interface WeatherData {
  temp: number
  condition: string
  description: string
  icon: string
  isRaining: boolean
  isOutdoorFriendly: boolean
  hourly: HourlyWeather[]
}

// Fetch current weather for Glasgow using wttr.in (free, no API key needed)
export async function fetchWeather(): Promise<WeatherData | null> {
  try {
    // Using wttr.in JSON API - free and no auth required
    const res = await fetch('https://wttr.in/Glasgow,UK?format=j1')
    if (!res.ok) return null
    
    const data = await res.json()
    const current = data.current_condition?.[0]
    if (!current) return null

    const weatherCode = parseInt(current.weatherCode || '0')
    const temp = parseInt(current.temp_C || '0')
    const description = current.weatherDesc?.[0]?.value || 'Unknown'
    const precipMM = parseFloat(current.precipMM || '0')
    
    // Check if it's nighttime
    const currentHour = new Date().getHours()
    const isNight = currentHour < 6 || currentHour >= 20
    
    // Determine if it's actually raining based on weather description keywords
    const rainKeywords = ['rain', 'drizzle', 'shower', 'sleet', 'snow', 'thunder']
    const isRaining = rainKeywords.some(keyword => description.toLowerCase().includes(keyword)) || precipMM > 0.1
    
    const isOutdoorFriendly = !isRaining && temp >= 10 && temp <= 25

    // Parse hourly forecast from today's weather
    const hourly: HourlyWeather[] = []
    const todayWeather = data.weather?.[0]
    if (todayWeather?.hourly) {
      for (const hour of todayWeather.hourly) {
        const hourTime = parseInt(hour.time || '0')
        const hourTemp = parseInt(hour.tempC || '0')
        const hourCode = parseInt(hour.weatherCode || '0')
        const hourDesc = hour.weatherDesc?.[0]?.value || ''
        const hourPrecip = parseFloat(hour.precipMM || '0')
        const hourIsRaining = rainKeywords.some(keyword => hourDesc.toLowerCase().includes(keyword)) || hourPrecip > 0.1
        const hourIsNight = hourTime < 600 || hourTime >= 2000
        
        // Format time (e.g., 0 -> 12 AM, 300 -> 3 AM, 1200 -> 12 PM, 1500 -> 3 PM)
        const hours = Math.floor(hourTime / 100)
        const displayHour = hours === 0 ? 12 : hours > 12 ? hours - 12 : hours
        const period = hours < 12 ? 'AM' : 'PM'
        const timeStr = `${displayHour} ${period}`
        
        hourly.push({
          time: timeStr,
          temp: hourTemp,
          icon: getWeatherEmoji(hourCode, hourIsRaining, hourIsNight),
          condition: hourDesc
        })
      }
    }

    return {
      temp,
      condition: description,
      description,
      icon: getWeatherEmoji(weatherCode, isRaining, isNight),
      isRaining,
      isOutdoorFriendly,
      hourly
    }
  } catch (error) {
    console.error('Failed to fetch weather:', error)
    return null
  }
}

function getWeatherEmoji(code: number, isRaining: boolean, isNight: boolean): string {
  if (isRaining) return '🌧️'
  if (code === 113) return isNight ? '🌙' : '☀️' // Clear - moon at night, sun during day
  if (code === 116) return isNight ? '☁️' : '⛅' // Partly cloudy
  if (code >= 119 && code <= 122) return '☁️' // Cloudy/Overcast
  if (code >= 143 && code <= 248) return '🌫️' // Fog/Mist
  if (code >= 338 && code <= 395) return '❄️' // Snow
  return isNight ? '🌙' : '🌤️' // Default
}
