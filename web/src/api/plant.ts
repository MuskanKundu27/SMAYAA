// Plant endpoints: module screens, alerts and readings.

import { apiFetch } from './client'
import type { ModuleSummary, ModuleView, PlantAlerts, Preview, Reading, SaveResult } from './types'

type Values = Record<string, number | null>

const plantPath = (plantId: string) => `/plants/${encodeURIComponent(plantId)}`

export const listModules = (plantId: string) =>
  apiFetch<ModuleSummary[]>(`${plantPath(plantId)}/modules`)

export const getModule = (plantId: string, key: string) =>
  apiFetch<ModuleView>(`${plantPath(plantId)}/modules/${encodeURIComponent(key)}`)

export const getAlerts = (plantId: string) => apiFetch<PlantAlerts>(`${plantPath(plantId)}/alerts`)

export const getLatestReading = (plantId: string) =>
  apiFetch<Reading | null>(`${plantPath(plantId)}/readings/latest`)

export const saveReading = (plantId: string, values: Values) =>
  apiFetch<SaveResult>(`${plantPath(plantId)}/readings`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })

export const previewReading = (plantId: string, values: Values) =>
  apiFetch<Preview>(`${plantPath(plantId)}/readings/preview`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
