import type { KeyboardEvent } from 'react'

import type { Tile } from '../api/types'
import { formatValue, limitsText } from '../format'
import { displayedTile, useModuleEditing } from '../modules/editing'
import { RangeBar } from './RangeBar'
import { StatusPill } from './StatusPill'

/** One parameter: value (editable for inputs when allowed), unit, status, range bar, limits. */
export function TileCard({ tile: savedTile }: { tile: Tile }) {
  const { canEdit, drafts, setDraft, commit, cancel, saveStates, preview } = useModuleEditing()

  if (savedTile.insufficient_data) {
    return (
      <div className="tile-card tile-card--na">
        <div className="tile-card__label">{savedTile.label}</div>
        <div className="tile-card__value muted">Insufficient data</div>
        <div className="tile-card__limits">Not configured for this company</div>
      </div>
    )
  }

  const tile = displayedTile(savedTile, preview)
  const editable = canEdit && savedTile.editable
  const draft = drafts[tile.key]
  const saveState = saveStates[tile.key]

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') event.currentTarget.blur() // blur triggers the save
    if (event.key === 'Escape') {
      cancel(tile.key)
      event.currentTarget.blur()
    }
  }

  return (
    <div className={`tile-card tile-card--${tile.status}`}>
      <div className="tile-card__head">
        <span className="tile-card__label">{tile.label}</span>
        <StatusPill status={tile.status} />
      </div>

      {editable ? (
        <label className="tile-card__input">
          <input
            inputMode="decimal"
            aria-label={tile.label}
            value={draft ?? (savedTile.value === null ? '' : String(savedTile.value))}
            placeholder="—"
            onChange={(e) => setDraft(tile.key, e.target.value)}
            onBlur={() => commit(tile.key)}
            onKeyDown={onKeyDown}
          />
          <span className="tile-card__unit">{tile.unit}</span>
        </label>
      ) : (
        <div className="tile-card__value">
          {formatValue(tile.value, tile.precision)}
          <span className="tile-card__unit">{tile.unit}</span>
        </div>
      )}

      {tile.limits && <RangeBar value={tile.value} limits={tile.limits} status={tile.status} />}
      <div className="tile-card__limits">{limitsText(tile.limits, tile.unit)}</div>

      {saveState && (
        <div className={`tile-card__save tile-card__save--${saveState.kind}`} role="status">
          {saveState.kind === 'saving' && 'Saving…'}
          {saveState.kind === 'saved' && 'Saved ✓'}
          {saveState.kind === 'error' && saveState.message}
        </div>
      )}
    </div>
  )
}
