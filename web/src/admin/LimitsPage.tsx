import { useState } from 'react'

import { getLimits, getPlantSettings, resetLimit, saveLimits, savePlantSettings } from '../api/admin'
import type { Limits, PlantLimitItem, PlantLimits, PlantSettings } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { parseInput } from '../format'
import { LIMIT_FIELDS as FIELDS, parseDraft, toDraft } from './limits'
import type { LimitDraft as Draft } from './limits'
import { ErrorText, Loading, Notice } from './ui'
import { errorMessage, useLoad } from './useLoad'

// Labels for plant settings shipped with the default template. Settings added by a company
// without a label here are shown by their key.
const SETTING_LABELS: Record<string, string> = {
  clean_baseline_approach: 'Clean baseline approach (°C) – expected approach when the tower is clean',
  design_heat_load: 'Design heat load (kW)',
  design_flow: 'Design circulating flow (m³/h)',
  design_wbt: 'Design wet-bulb temperature (°C)',
  high_approach_threshold: 'High-approach threshold (°C)',
  low_flow_threshold: 'Low-flow threshold (m³/h)',
  clean_dp_baseline: 'Expected post-clean filter ΔP (bar)',
  min_water_per_clean: 'Minimum water per cleaning (m³)',
  outlet_turbidity_limit: 'Outlet turbidity quality limit (NTU)',
  target_coc: 'Target cycles of concentration (conductivity setpoint = make-up conductivity × target)',
  drift_loss: 'Drift loss (m³/h, design estimate)',
  baseline_blowdown: 'Baseline blowdown before optimisation (m³/h)',
  baseline_makeup: 'Baseline make-up water before optimisation (m³/h)',
  water_cost: 'Make-up water cost (₹ per m³)',
  chem_target: 'Chemical dosing target (L/h)',
  design_blowdown: 'Design blowdown (m³/h) – used for expected make-up',
  design_other_loss: 'Design backwash / other loss (m³/h)',
  design_storage_change: 'Design storage change (m³/h)',
  chemical_cost: 'Chemical cost (₹ per m³ of make-up)',
}

export function LimitsPage() {
  const { plant } = useAuth()
  if (!plant) return <p className="muted">Select a plant to see its limits.</p>
  return <PlantLimitsScreen key={plant.id} plantId={plant.id} plantName={plant.name} />
}

function PlantLimitsScreen({ plantId, plantName }: { plantId: string; plantName: string }) {
  const limits = useLoad(() => getLimits(plantId), [plantId])
  const settings = useLoad(() => getPlantSettings(plantId), [plantId])

  return (
    <>
      <h1>Limits · {plantName}</h1>
      <p className="muted">
        Limits belong to the plant. A value inside good min–max is Good, inside warning min–max is
        Warning, outside is Alert.
      </p>
      <ErrorText message={limits.error ?? settings.error} />
      {!limits.data ? <Loading /> : <LimitsTable data={limits.data} plantId={plantId} onSaved={limits.reload} />}
      {settings.data && <SettingsCard data={settings.data} plantId={plantId} onSaved={settings.reload} />}
    </>
  )
}

function LimitsTable({ data, plantId, onSaved }: { data: PlantLimits; plantId: string; onSaved: () => void }) {
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const draftFor = (item: PlantLimitItem) => drafts[item.parameter_key] ?? toDraft(item.limits)
  const changedKeys = Object.keys(drafts)

  function edit(item: PlantLimitItem, field: keyof Limits, text: string) {
    setDrafts((current) => ({ ...current, [item.parameter_key]: { ...draftFor(item), [field]: text } }))
  }

  async function handleSave() {
    const items = []
    for (const key of changedKeys) {
      const parsed = parseDraft(drafts[key])
      const label = data.items.find((i) => i.parameter_key === key)?.label ?? key
      if (parsed === null) continue
      if ('error' in parsed) {
        setError(`${label}: ${parsed.error}`)
        return
      }
      items.push({ parameter_key: key, ...parsed.limits })
    }
    if (items.length === 0) {
      setDrafts({})
      return
    }
    setBusy(true)
    setError(null)
    try {
      await saveLimits(plantId, items)
      setDrafts({})
      setMessage(`Saved ${items.length} limit${items.length === 1 ? '' : 's'}. Alerts update straight away.`)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function handleReset(item: PlantLimitItem) {
    if (!window.confirm(`Use the company default limits for ${item.label}?`)) return
    setError(null)
    try {
      await resetLimit(plantId, item.parameter_key)
      setMessage(`${item.label} now uses the company default.`)
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  const groups = [...new Set(data.items.map((i) => i.group_key))]

  return (
    <>
      {!data.has_manager && (
        <Notice tone="warn">
          This plant has no active manager. The company admin can edit its limits until a manager is
          assigned.
        </Notice>
      )}
      {!data.can_edit && <Notice>View only: you cannot change these limits.</Notice>}
      {message && <Notice>{message}</Notice>}
      <div className="card table-card">
        <table className="data-table limits-table">
          <thead>
            <tr>
              <th>Parameter</th>
              {FIELDS.map((f) => (
                <th key={f.key}>{f.label}</th>
              ))}
              <th>Source</th>
              <th />
            </tr>
          </thead>
          {groups.map((group) => (
            <tbody key={group}>
              <tr className="group-row">
                <td colSpan={FIELDS.length + 3}>{group}</td>
              </tr>
              {data.items
                .filter((i) => i.group_key === group)
                .map((item) => {
                  const draft = draftFor(item)
                  return (
                    <tr key={item.parameter_key} className={drafts[item.parameter_key] ? 'row--changed' : undefined}>
                      <td>
                        {item.label}
                        {item.unit && <span className="muted"> ({item.unit})</span>}
                      </td>
                      {FIELDS.map((f) => (
                        <td key={f.key}>
                          {data.can_edit ? (
                            <input
                              className="cell-input cell-input--number"
                              inputMode="decimal"
                              value={draft[f.key]}
                              onChange={(e) => edit(item, f.key, e.target.value)}
                              aria-label={`${item.label} ${f.label}`}
                            />
                          ) : (
                            draft[f.key] || '–'
                          )}
                        </td>
                      ))}
                      <td>
                        {item.source === 'plant' ? (
                          <span className="pill pill--good">This plant</span>
                        ) : item.source === 'default' ? (
                          <span className="pill pill--na">Company default</span>
                        ) : (
                          <span className="muted">No limits</span>
                        )}
                      </td>
                      <td className="cell-actions">
                        {data.can_edit && item.source === 'plant' && (
                          <button className="button button--ghost button--small" onClick={() => void handleReset(item)}>
                            Use default
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          ))}
        </table>
      </div>
      {data.can_edit && (
        <div className="sticky-actions">
          <ErrorText message={error} />
          {changedKeys.length > 0 && (
            <button className="button button--ghost" onClick={() => setDrafts({})} disabled={busy}>
              Discard changes
            </button>
          )}
          <button className="button button--primary" onClick={() => void handleSave()} disabled={busy || changedKeys.length === 0}>
            {busy ? 'Saving…' : 'Save limits'}
          </button>
        </div>
      )}
    </>
  )
}

function SettingsCard({ data, plantId, onSaved }: { data: PlantSettings; plantId: string; onSaved: () => void }) {
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const keys = Object.keys(data.settings)
  if (keys.length === 0) return null

  async function handleSave() {
    const values: Record<string, number> = {}
    for (const [key, text] of Object.entries(drafts)) {
      const parsed = parseInput(text)
      if (!parsed.ok || parsed.value === null) {
        setError(`${key}: please enter a number.`)
        return
      }
      values[key] = parsed.value
    }
    if (Object.keys(values).length === 0) return
    setError(null)
    try {
      await savePlantSettings(plantId, values)
      setDrafts({})
      setMessage('Plant settings saved.')
      onSaved()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <>
      <h2>Plant settings</h2>
      {message && <Notice>{message}</Notice>}
      <div className="card form-grid">
        {keys.map((key) => {
          const setting = data.settings[key]
          const value = drafts[key] ?? (setting.value === null || setting.value === undefined ? '' : String(setting.value))
          return (
            <label key={key} className="field">
              <span>{SETTING_LABELS[key] ?? key}</span>
              <input
                inputMode="decimal"
                value={value}
                disabled={!data.can_edit}
                onChange={(e) => setDrafts((d) => ({ ...d, [key]: e.target.value }))}
              />
              <small className="muted">
                {setting.source === 'plant' ? 'Set for this plant' : 'Company default'}
              </small>
            </label>
          )
        })}
        {data.can_edit && (
          <div className="form-grid__actions">
            <ErrorText message={error} />
            <button
              className="button button--primary"
              onClick={() => void handleSave()}
              disabled={Object.keys(drafts).length === 0}
            >
              Save settings
            </button>
          </div>
        )}
      </div>
    </>
  )
}
