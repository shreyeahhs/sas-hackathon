import React from 'react'
import type { WeatherData } from '../api'

interface WeatherBannerProps {
  weather: WeatherData | null
}

export const WeatherBanner: React.FC<WeatherBannerProps> = ({ weather }) => {
  if (!weather) return null

  const getRecommendation = () => {
    if (weather.isRaining) {
      return {
        text: "It's raining! We recommend checking out indoor events today.",
        emoji: '☂️',
        style: 'rain'
      }
    }
    if (weather.isOutdoorFriendly) {
      return {
        text: "Perfect weather for outdoor events!",
        emoji: '🌟',
        style: 'outdoor'
      }
    }
    return {
      text: "Check the weather before heading out to outdoor events.",
      emoji: '🌡️',
      style: 'neutral'
    }
  }

  const recommendation = getRecommendation()

  // Format current date
  const today = new Date()
  const dateString = today.toLocaleDateString('en-GB', { 
    weekday: 'long', 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric' 
  })

  return (
    <div className={`weather-banner weather-${recommendation.style}`}>
      <div className="container">
        <div className="weather-header">
          <h3 className="weather-date">{dateString}</h3>
        </div>
        <div className="weather-content">
          <div className="weather-left">
            <span className="weather-icon">{weather.icon}</span>
            <div className="weather-info">
              <span className="weather-temp">{weather.temp}°C</span>
              <span className="weather-condition">{weather.condition}</span>
            </div>
          </div>
          <div className="weather-recommendation">
            <span className="recommendation-emoji">{recommendation.emoji}</span>
            <span className="recommendation-text">{recommendation.text}</span>
          </div>
        </div>
        
        {/* Hourly forecast timeline */}
        {weather.hourly && weather.hourly.length > 0 && (
          <div className="hourly-forecast">
            <div className="hourly-scroll">
              {weather.hourly.map((hour, idx) => (
                <div key={idx} className="hourly-item">
                  <div className="hourly-time">{hour.time}</div>
                  <div className="hourly-icon">{hour.icon}</div>
                  <div className="hourly-temp">{hour.temp}°</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
