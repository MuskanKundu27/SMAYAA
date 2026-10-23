import { createContext, useContext } from 'react'

import type { Tile } from '../api/types'

export type SaveState = { kind: 'saving' } | { kind: 'saved' } | { kind: 'error'; message: string }

/** Shared by all widgets on a module screen while the user types (see ModulePage). */
export interface ModuleEditing {
  canEdit: boolean
  /** What the user has typed but not saved yet, per parameter key. */
  drafts: Record<string, string>
  setDraft: (key: string, text: string) => void
  /** Save the draft for this key (on blur or Enter). */
  commit: (key: string) => void
  /** Cancel the draft (Escape). */
  cancel: (key: string) => void
  /** Save a value right away without typing (on/off switches). */
  setValue: (key: string, value: number | null) => void
  saveStates: Record<string, SaveState>
  /** Live preview tiles while typing (only this user sees them); key → tile. */
  preview: Record<string, Tile>
}

export const ModuleEditingContext = createContext<ModuleEditing>({
  canEdit: false,
  drafts: {},
  setDraft: () => {},
  commit: () => {},
  cancel: () => {},
  setValue: () => {},
  saveStates: {},
  preview: {},
})

export function useModuleEditing(): ModuleEditing {
  return useContext(ModuleEditingContext)
}

/** The tile to show: the live preview version while the user is typing, else the saved one. */
export function displayedTile(tile: Tile, preview: Record<string, Tile>): Tile {
  const live = preview[tile.key]
  return live ? { ...live, editable: tile.editable } : tile
}
