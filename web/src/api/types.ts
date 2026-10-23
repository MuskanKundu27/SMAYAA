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
  /** Tile keys drawn as on/off switches (input_group). */
  switches?: string[] | null
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
  /** Predicted problems for the notification bell (empty when the profile hides alerts). */
  problems: PredictedProblem[]
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

// --- Management ---

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface User {
  id: string
  username: string
  full_name: string
  is_active: boolean
  company_id: string | null
  roles: string[]
  plant_ids: string[]
  created_at: string
  deactivated_at: string | null
}

export interface Plant {
  id: string
  company_id: string
  name: string
  location: string
  is_active: boolean
  created_at: string
}

export interface Company {
  id: string
  name: string
  is_active: boolean
  created_at: string
}

export interface CompanyCreated {
  company: Company
  admin: User
}

export interface PlantLimitItem {
  parameter_key: string
  label: string
  unit: string
  group_key: string
  limits: Limits | null
  source: 'plant' | 'default' | null
}

export interface PlantLimits {
  plant_id: string
  has_manager: boolean
  can_edit: boolean
  items: PlantLimitItem[]
}

export interface PlantSettings {
  plant_id: string
  can_edit: boolean
  settings: Record<string, { value: unknown; source: 'plant' | 'company_default' | null }>
}

export interface OperatorProfile {
  user_id: string
  username: string
  full_name: string
  roles: string[]
  is_default: boolean
  visible_modules: string[] | null
  can_edit_readings: boolean
  show_alerts: boolean
}

export interface Parameter {
  id: string
  key: string
  label: string
  unit: string
  group_key: string
  kind: 'input' | 'calculated'
  formula: string | null
  formula_version: number
  precision: number
  sort_order: number
  is_active: boolean
  sample_value: number | null
  default_limits: Limits | null
  updated_at: string | null
}

export interface FormulaTestResult {
  ok: boolean
  result: number | boolean | null
  references: string[]
  error: string | null
}

export interface Treatment {
  id: string
  parameter_key: string
  direction: Direction
  cause: string
  treatment: string
  precautions: string
  needs_review: boolean
}

export interface Rule {
  id: string
  code: string
  title: string
  kind: string
  condition_expr: string
  probability_expr: string
  action_text: string
  affects_modules: string[]
  is_active: boolean
  version: number
  sort_order: number
}

export interface RuleTestResult {
  ok: boolean
  matched: boolean | null
  probability: number | null
  references: string[]
  error: string | null
}

export interface Module {
  id: string
  key: string
  title: string
  sort_order: number
  is_active: boolean
  layout: { widgets?: unknown[] }
  warnings: string[]
}

export interface AuditEntry {
  id: string
  created_at: string
  company_id: string | null
  company_name: string | null
  actor_id: string | null
  actor_name: string | null
  action: string
  entity: string
  entity_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
}
