import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router'

import { ApiError } from '../api/client'
import { getModule, previewReading, saveReading } from '../api/plant'
import type { ModuleView, Tile } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { formatTime, parseInput } from '../format'
import { usePlantData } from '../plant/usePlantData'
import { ModuleEditingContext } from './editing'
import type { ModuleEditing, SaveState } from './editing'
import { ModuleLocationContext } from './moduleContext'
import { widgetFor } from './registry'

const PREVIEW_DELAY_MS = 400
const SAVED_BADGE_MS = 2500

function tilesByKey(view: ModuleView | null): Record<string, Tile> {
  const map: Record<string, Tile> = {}
  for (const widget of view?.widgets ?? []) for (const tile of widget.tiles ?? []) map[tile.key] = tile
  return map
}

/** Keyed by plant + module, so switching either starts with a clean screen (no stale typing). */
export function ModulePage() {
  const { moduleKey = '' } = useParams()
  const { plant } = useAuth()
  if (!plant) return <p className="muted">Select a plant to see this module.</p>
  return <ModuleScreen key={`${plant.id}:${moduleKey}`} plantId={plant.id} moduleKey={moduleKey} />
}

function ModuleScreen({ plantId, moduleKey }: { plantId: string; moduleKey: string }) {
  const { version, refresh } = usePlantData()

  const [view, setView] = useState<ModuleView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({})
  const [preview, setPreview] = useState<Record<string, Tile>>({})
  const previewTimer = useRef<number | undefined>(undefined)
  // Saved keys whose typed text is kept until the refreshed screen arrives (avoids a flicker
  // back to the old value between saving and reloading).
  const awaitingReload = useRef<Set<string>>(new Set())

  // Load (and reload whenever anyone saves a reading: `version` changes).
  useEffect(() => {
    let cancelled = false
    getModule(plantId, moduleKey)
      .then((v) => {
        if (!cancelled) {
          setView(v)
          setError(null)
          if (awaitingReload.current.size > 0) {
            const done = awaitingReload.current
            awaitingReload.current = new Set()
            setDrafts((current) =>
              Object.fromEntries(Object.entries(current).filter(([key]) => !done.has(key))),
            )
          }
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Could not load this module.')
      })
    return () => {
      cancelled = true
    }
  }, [plantId, moduleKey, version])

  const saved = useMemo(() => tilesByKey(view), [view])
  const location = useMemo(() => ({ plantId, moduleKey }), [plantId, moduleKey])

  // Live preview while typing: after a short pause, ask the server what the screen would show.
  useEffect(() => {
    window.clearTimeout(previewTimer.current)
    const values: Record<string, number | null> = {}
    for (const [key, text] of Object.entries(drafts)) {
      const parsed = parseInput(text)
      if (parsed.ok) values[key] = parsed.value
    }
    if (Object.keys(values).length === 0) return
    let cancelled = false
    previewTimer.current = window.setTimeout(() => {
      previewReading(plantId, values)
        .then((p) => !cancelled && setPreview(Object.fromEntries(p.tiles.map((t) => [t.key, t]))))
        .catch(() => !cancelled && setPreview({}))
    }, PREVIEW_DELAY_MS)
    return () => {
      cancelled = true
      window.clearTimeout(previewTimer.current)
    }
  }, [drafts, plantId])

  const setDraft = useCallback((key: string, text: string) => {
    setDrafts((current) => ({ ...current, [key]: text }))
  }, [])

  const dropDraft = useCallback((key: string) => {
    setDrafts((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
  }, [])

  const showState = useCallback((key: string, state: SaveState | null) => {
    setSaveStates((current) => {
      const next = { ...current }
      if (state) next[key] = state
      else delete next[key]
      return next
    })
  }, [])

  const save = useCallback(
    (key: string, value: number | null) => {
      if (value === (saved[key]?.value ?? null)) {
        dropDraft(key) // nothing changed: nothing to save
        return
      }
      showState(key, { kind: 'saving' })
      saveReading(plantId, { [key]: value })
        .then(() => {
          showState(key, { kind: 'saved' })
          window.setTimeout(() => showState(key, null), SAVED_BADGE_MS)
          awaitingReload.current.add(key)
          refresh() // reload this screen and the alert bar now
        })
        .catch((err: unknown) => {
          const message = err instanceof ApiError ? err.message : 'Not saved. Check your connection.'
          showState(key, { kind: 'error', message })
          dropDraft(key)
        })
    },
    [plantId, saved, showState, dropDraft, refresh],
  )

  const commit = useCallback(
    (key: string) => {
      const text = drafts[key]
      if (text === undefined) return
      const parsed = parseInput(text)
      if (!parsed.ok) {
        showState(key, { kind: 'error', message: parsed.error })
        dropDraft(key)
        return
      }
      save(key, parsed.value)
    },
    [drafts, showState, dropDraft, save],
  )

  const editing: ModuleEditing = useMemo(
    () => ({
      canEdit: view?.can_edit_readings ?? false,
      drafts,
      setDraft,
      commit,
      cancel: dropDraft,
      setValue: save,
      saveStates,
      // A preview only makes sense while something is being typed.
      preview: Object.keys(drafts).length > 0 ? preview : {},
    }),
    [view, drafts, setDraft, commit, dropDraft, save, saveStates, preview],
  )

  if (error) return <div className="card form-error">{error}</div>
  if (!view) return <p className="muted">Loading…</p>

  return (
    <ModuleLocationContext.Provider value={location}>
      <ModuleEditingContext.Provider value={editing}>
        <div className="module-head">
          <h1>{view.title}</h1>
          <p className="muted module-head__meta">
            {view.reading
              ? `Last updated by ${view.reading.created_by?.name ?? 'unknown'} at ${formatTime(view.reading.recorded_at)}`
              : 'No readings yet.'}
          </p>
        </div>
        <div className="module-grid">
          {view.widgets.map((widget, index) => {
            const Widget = widgetFor(widget.type)
            return (
              <div key={`${widget.type}-${index}`} className={`module-grid__item module-grid__item--${widget.width ?? 'full'}`}>
                <Widget widget={widget} index={index} />
              </div>
            )
          })}
        </div>
      </ModuleEditingContext.Provider>
    </ModuleLocationContext.Provider>
  )
}
