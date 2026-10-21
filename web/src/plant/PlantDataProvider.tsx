import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { getAlerts, getLatestReading, listModules } from '../api/plant'
import type { ModuleSummary, PlantAlerts } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { PlantDataContext } from './usePlantData'

// How often screens check for someone else's changes. WebSockets can replace polling later.
export const POLL_INTERVAL_MS = 5000

/** Data tagged with the plant it belongs to, so switching plant never shows the old plant's data. */
interface ForPlant<T> {
  plantId: string
  data: T
}

export function PlantDataProvider({ children }: { children: ReactNode }) {
  const { plant, can } = useAuth()
  const plantId = plant?.id ?? null
  const canViewModules = can('modules.view')
  const canViewAlerts = can('alerts.view')
  const canReadReadings = can('readings.read')

  const [modules, setModules] = useState<ForPlant<ModuleSummary[]> | null>(null)
  const [alerts, setAlerts] = useState<ForPlant<PlantAlerts> | null>(null)
  const [version, setVersion] = useState(0)
  const lastReadingId = useRef<string | null | undefined>(undefined)

  // Module list for the menu: reload when the plant changes.
  useEffect(() => {
    if (!plantId || !canViewModules) return
    let cancelled = false
    listModules(plantId)
      .then((data) => !cancelled && setModules({ plantId, data }))
      .catch(() => !cancelled && setModules({ plantId, data: [] }))
    return () => {
      cancelled = true
    }
  }, [plantId, canViewModules])

  const loadAlerts = useCallback(async () => {
    if (!plantId || !canViewAlerts) return
    try {
      setAlerts({ plantId, data: await getAlerts(plantId) })
    } catch {
      // keep the last known alerts; the next poll tries again
    }
  }, [plantId, canViewAlerts])

  const refresh = useCallback(() => {
    setVersion((v) => v + 1)
    void loadAlerts()
  }, [loadAlerts])

  // Poll the latest reading id; when it changes, everything on screen refreshes.
  useEffect(() => {
    if (!plantId || !canReadReadings) return
    lastReadingId.current = undefined
    let cancelled = false

    const check = async () => {
      try {
        const latest = await getLatestReading(plantId)
        const id = latest?.id ?? null
        if (!cancelled && id !== lastReadingId.current) {
          lastReadingId.current = id
          refresh()
        }
      } catch {
        // network hiccup: try again next time
      }
    }
    void check()
    const timer = window.setInterval(() => void check(), POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [plantId, canReadReadings, refresh])

  const value = useMemo(
    () => ({
      modules: modules && modules.plantId === plantId && canViewModules ? modules.data : [],
      alerts: alerts && alerts.plantId === plantId && canViewAlerts ? alerts.data : null,
      version,
      refresh,
    }),
    [modules, alerts, plantId, canViewModules, canViewAlerts, version, refresh],
  )
  return <PlantDataContext.Provider value={value}>{children}</PlantDataContext.Provider>
}
