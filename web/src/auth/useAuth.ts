import { createContext, useContext } from 'react'

import type { Me, MePlant } from '../api/types'

export type AuthStatus = 'loading' | 'anonymous' | 'authenticated'

export interface AuthState {
  status: AuthStatus
  me: Me | null
  /** Plant the user is currently looking at (users with several plants can switch). */
  plant: MePlant | null
  selectPlant: (plantId: string) => void
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  /** Fetch GET /me again, e.g. after creating a plant so it appears in the plant list. */
  reloadMe: () => Promise<void>
  can: (permission: string) => boolean
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>')
  return context
}
