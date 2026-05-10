export type LayerKey = 'gfw' | 'sar' | 'turbidity' | 'reserves'
export type HotspotId = 'wassa' | 'atewa' | 'birim' | 'tano' | 'pra'
export type ThemeResolved = 'light' | 'dark'

export interface Hotspot {
  id: HotspotId
  name: string
  region: string
  coords: [number, number]
  alerts: number
}

export interface HeroStat {
  num: string
  cap: string
}

export interface HotspotDetail {
  title: string
  alerts: number
  excavators: number
  rivers: number
  description: string
  incidents: Incident[]
}

export interface Incident {
  id: string
  desc: string
  date: string
}

export interface AlertProperties {
  id: string
  kind: 'alert' | 'citizen'
  hotspot: HotspotId
}

export interface RiverProperties {
  severity: number
}

export interface ReserveProperties {
  name: string
}

export type TimeRangePill = '7d' | '30d' | '90d' | '365d'

export interface AlertTimeRange {
  pill: TimeRangePill
  sliderVal: number
}

export type MinConfidence = 'low' | 'high' | 'highest'

export interface RegionSparklineDay {
  date: string
  count: number
}

export interface RegionSparkline {
  region_id: number
  region_name: string
  dates: RegionSparklineDay[]
}
