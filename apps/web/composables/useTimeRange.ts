import type { AlertTimeRange, TimeRangePill } from '~/types/dashboard'

// Maximum days back from "today" that the slider can reach when sliderVal = 0.
// Capped at 365 to match the longest pill so any pill stays valid at any slider position.
const MAX_SCRUB_DAYS = 365

const WINDOW_DAYS: Record<TimeRangePill, number> = {
  '7d':   7,
  '30d':  30,
  '90d':  90,
  '365d': 365,
}

export interface DateRange {
  from: string
  to:   string
}

// Returns inclusive YYYY-MM-DD bounds. Offset is rounded to whole days so the
// MVT source isn't re-tiled mid-drag. Ghana is UTC+0 year-round, so toISOString
// slicing gives the local calendar date without timezone gymnastics.
export function rangeToFromTo(range: AlertTimeRange, today: Date = new Date()): DateRange {
  const dayMs = 86_400_000
  const windowDays = WINDOW_DAYS[range.pill]
  const offsetDays = Math.max(
    0,
    Math.round((1 - range.sliderVal) * (MAX_SCRUB_DAYS - windowDays)),
  )
  const to = new Date(today.getTime() - offsetDays * dayMs)
  const from = new Date(to.getTime() - (windowDays - 1) * dayMs)
  return {
    from: from.toISOString().slice(0, 10),
    to:   to.toISOString().slice(0, 10),
  }
}
