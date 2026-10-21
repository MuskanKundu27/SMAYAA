// Shapes returned by the API (see the API's /api/v1/docs for the full schema).

export interface MePlant {
  id: string
  name: string
  location: string
}

export interface Me {
  id: string
  username: string
  full_name: string
  roles: string[]
  permissions: string[]
  company: { id: string; name: string } | null
  plants: MePlant[]
}

// --- Plant screens ---

export type StatusLevel = 'good' | 'warn' | 'bad' | 'na'
export type Direction = 'high' | 'low'

export interface Limits {
  warn_min: number
  good_min: number
  good_max: number
  warn_max: number
}

export interface Tile {
  key: string
  label: string
  unit: string
  precision: number
  kind: 'input' | 'calculated' | null
  value: number | null
  status: StatusLevel
  direction: Direction | null
  limits: Limits | null
  editable: boolean
  insufficient_data: boolean
}

export interface Alert {
  parameter_key: string
  label: string
  unit: string
  value: number
  level: 'warn' | 'bad'
  severity: 'medium' | 'high'
  direction: Direction
  limits: Limits
  modules: string[]
  cause: string
  treatment: string
  precautions: string
  needs_review: boolean
}

export interface PredictedProblem {
  code: string
  title: string
  probability: number | null
  action: string
  modules: string[]
}

export interface TrendSeries {
  key: string
  label: string
  unit: string
  limits: Limits | null
  points: { t: string; v: number | null }[]
}

export interface WidgetView {
  type: string
  title: string
  tiles: Tile[] | null
  problems: PredictedProblem[] | null
  insufficient_rules: string[] | null
  alerts: Alert[] | null
  series: TrendSeries[] | null
  text: string | null
}

export interface Person {
  id: string
  name: string
}

export interface ReadingSummary {
  id: string
  recorded_at: string
  created_by: Person | null
  changed_keys: string[]
}

export interface ModuleSummary {
  key: string
  title: string
  sort_order: number
}

export interface ModuleView {
  key: string
  title: string
  reading: ReadingSummary | null
  can_edit_readings: boolean
  widgets: WidgetView[]
}

export interface PlantAlerts {
  reading: ReadingSummary | null
  alerts: Alert[]
}

export interface Reading extends ReadingSummary {
  input_values: Record<string, number | null>
  calculated_values: Record<string, number | null>
}

export interface SaveResult {
  reading: Reading
  created: boolean
}

export interface Preview {
  values: Record<string, number | null>
  tiles: Tile[]
  alerts: Alert[]
  problems: PredictedProblem[]
}
