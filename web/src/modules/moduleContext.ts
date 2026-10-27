import { createContext, useContext } from 'react'

/** Which plant and module a widget belongs to (for widgets that load more data themselves,
 *  e.g. a trend chart switching its time range). */
export interface ModuleLocation {
  plantId: string
  moduleKey: string
}

export const ModuleLocationContext = createContext<ModuleLocation>({ plantId: '', moduleKey: '' })

export function useModuleLocation(): ModuleLocation {
  return useContext(ModuleLocationContext)
}
