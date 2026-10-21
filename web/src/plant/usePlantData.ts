import { createContext, useContext } from 'react'

import type { ModuleSummary, PlantAlerts } from '../api/types'

export interface PlantData {
  /** Modules this user may open at the selected plant (empty for users without a plant). */
  modules: ModuleSummary[]
  alerts: PlantAlerts | null
  /**
   * Increases whenever a new reading is saved (by anyone). Screens re-fetch when it changes.
   * This is how the manager sees the operator's change within a few seconds.
   */
  version: number
  /** Call after saving: refreshes immediately instead of waiting for the next poll. */
  refresh: () => void
}

export const PlantDataContext = createContext<PlantData>({
  modules: [],
  alerts: null,
  version: 0,
  refresh: () => {},
})

export function usePlantData(): PlantData {
  return useContext(PlantDataContext)
}
