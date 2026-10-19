import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import * as api from '../api/client'
import type { Me } from '../api/types'
import { AuthContext } from './useAuth'
import type { AuthState, AuthStatus } from './useAuth'

const PLANT_KEY = 'smayaa.selectedPlant'

// Remembering the last plant is a convenience only; storage may be unavailable.
function readSavedPlant(): string | null {
  try {
    return localStorage.getItem(PLANT_KEY)
  } catch {
    return null
  }
}

function savePlant(plantId: string): void {
  try {
    localStorage.setItem(PLANT_KEY, plantId)
  } catch {
    // ignore
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [me, setMe] = useState<Me | null>(null)
  const [plantId, setPlantId] = useState<string | null>(readSavedPlant)

  const endSession = useCallback(() => {
    setMe(null)
    setStatus('anonymous')
  }, [])

  const loadMe = useCallback(async () => {
    const profile = await api.apiFetch<Me>('/me')
    setMe(profile)
    setStatus('authenticated')
  }, [])

  // On page load: if the refresh cookie is still valid, the user stays logged in.
  useEffect(() => {
    api.setSessionEndedHandler(endSession)
    void (async () => {
      if (await api.refreshAccessToken()) {
        try {
          await loadMe()
          return
        } catch {
          // fall through to the login page
        }
      }
      setStatus('anonymous')
    })()
  }, [endSession, loadMe])

  const login = useCallback(
    async (username: string, password: string) => {
      await api.login(username, password)
      await loadMe()
    },
    [loadMe],
  )

  const logout = useCallback(async () => {
    await api.logout()
    endSession()
  }, [endSession])

  const selectPlant = useCallback((id: string) => {
    setPlantId(id)
    savePlant(id)
  }, [])

  const value = useMemo<AuthState>(() => {
    const plants = me?.plants ?? []
    const plant = plants.find((p) => p.id === plantId) ?? plants[0] ?? null
    const permissions = new Set(me?.permissions ?? [])
    return {
      status,
      me,
      plant,
      selectPlant,
      login,
      logout,
      can: (permission) => permissions.has(permission),
    }
  }, [status, me, plantId, selectPlant, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
