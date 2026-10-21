// Management endpoints: users, plants, companies, limits, operator profiles, configuration,
// audit log. Every call is checked again by the API (permissions + scope); the screens only
// decide what to show.

import { apiFetch } from './client'
import type {
  AuditEntry,
  Company,
  CompanyCreated,
  FormulaTestResult,
  Module,
  OperatorProfile,
  Page,
  Parameter,
  Plant,
  PlantLimits,
  PlantSettings,
  Rule,
  RuleTestResult,
  Treatment,
  User,
} from './types'

type Json = Record<string, unknown>

const send = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
})
const query = (params: Record<string, string | number | undefined>) => {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}
const id = encodeURIComponent

// --- Users and plants ---

export const listUsers = () => apiFetch<Page<User>>('/users?limit=200')
export const createUser = (body: Json) => apiFetch<User>('/users', send('POST', body))
export const deactivateUser = (userId: string) =>
  apiFetch<{ user: User; warnings: string[] }>(`/users/${id(userId)}`, send('DELETE'))

export const listPlants = () => apiFetch<Page<Plant>>('/plants?limit=200')
export const createPlant = (body: Json) => apiFetch<Plant>('/plants', send('POST', body))
export const updatePlant = (plantId: string, body: Json) =>
  apiFetch<Plant>(`/plants/${id(plantId)}`, send('PATCH', body))

// --- Limits, plant settings, operator profiles (per plant) ---

const plant = (plantId: string) => `/plants/${id(plantId)}`

export const getLimits = (plantId: string) => apiFetch<PlantLimits>(`${plant(plantId)}/limits`)
export const saveLimits = (plantId: string, items: Json[]) =>
  apiFetch<PlantLimits>(`${plant(plantId)}/limits`, send('PUT', { items }))
export const resetLimit = (plantId: string, key: string) =>
  apiFetch<PlantLimits>(`${plant(plantId)}/limits/${id(key)}`, send('DELETE'))

export const getPlantSettings = (plantId: string) =>
  apiFetch<PlantSettings>(`${plant(plantId)}/settings`)
export const savePlantSettings = (plantId: string, values: Json) =>
  apiFetch<PlantSettings>(`${plant(plantId)}/settings`, send('PUT', { values }))

export const listOperatorProfiles = (plantId: string) =>
  apiFetch<OperatorProfile[]>(`${plant(plantId)}/operator-profiles`)
export const saveOperatorProfile = (plantId: string, userId: string, body: Json) =>
  apiFetch<OperatorProfile>(`${plant(plantId)}/operator-profiles/${id(userId)}`, send('PUT', body))
export const resetOperatorProfile = (plantId: string, userId: string) =>
  apiFetch<OperatorProfile>(`${plant(plantId)}/operator-profiles/${id(userId)}`, send('DELETE'))

// --- Companies and their configuration (platform admin) ---

export const listCompanies = () => apiFetch<Page<Company>>('/companies?limit=200')
export const createCompany = (body: Json) =>
  apiFetch<CompanyCreated>('/companies', send('POST', body))
export const updateCompany = (companyId: string, body: Json) =>
  apiFetch<Company>(`/companies/${id(companyId)}`, send('PATCH', body))

const company = (companyId: string) => `/companies/${id(companyId)}`

export const listParameters = (companyId: string) =>
  apiFetch<Parameter[]>(`${company(companyId)}/parameters`)
export const createParameter = (companyId: string, body: Json) =>
  apiFetch<Parameter>(`${company(companyId)}/parameters`, send('POST', body))
export const updateParameter = (companyId: string, key: string, body: Json) =>
  apiFetch<Parameter>(`${company(companyId)}/parameters/${id(key)}`, send('PATCH', body))
export const testFormula = (companyId: string, formula: string) =>
  apiFetch<FormulaTestResult>(`${company(companyId)}/formulas/test`, send('POST', { formula }))

export const listTreatments = (companyId: string) =>
  apiFetch<Treatment[]>(`${company(companyId)}/treatments`)
export const saveTreatments = (companyId: string, items: Json[]) =>
  apiFetch<Treatment[]>(`${company(companyId)}/treatments`, send('PUT', items))

export const listRules = (companyId: string) => apiFetch<Rule[]>(`${company(companyId)}/rules`)
export const createRule = (companyId: string, body: Json) =>
  apiFetch<Rule>(`${company(companyId)}/rules`, send('POST', body))
export const updateRule = (companyId: string, code: string, body: Json) =>
  apiFetch<Rule>(`${company(companyId)}/rules/${id(code)}`, send('PATCH', body))
export const testRule = (companyId: string, body: Json) =>
  apiFetch<RuleTestResult>(`${company(companyId)}/rules/test`, send('POST', body))

export const listConfigModules = (companyId: string) =>
  apiFetch<Module[]>(`${company(companyId)}/modules`)
export const createModule = (companyId: string, body: Json) =>
  apiFetch<Module>(`${company(companyId)}/modules`, send('POST', body))
export const updateModule = (companyId: string, key: string, body: Json) =>
  apiFetch<Module>(`${company(companyId)}/modules/${id(key)}`, send('PATCH', body))

export const applyTemplate = (companyId: string) =>
  apiFetch<{ template: string; added: Record<string, number> }>(
    `${company(companyId)}/apply-template`,
    send('POST'),
  )

// --- Audit log ---

export const listAuditLog = (params: { companyId?: string; entity?: string; offset?: number }) =>
  apiFetch<Page<AuditEntry>>(
    `/audit-log${query({ company_id: params.companyId, entity: params.entity, offset: params.offset, limit: 50 })}`,
  )
