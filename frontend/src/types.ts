export type EventItem = {
  title: string
  date: string
  venue: string
  description: string
  category: string
  categories: string[]
  url: string
  image_url?: string
  nightOutScore?: number
  scoreBadge?: { emoji: string; label: string; color: string }
}

export type EventsApiResponse = {
  events: EventItem[]
  total_count: number
  categories: string[]
}
