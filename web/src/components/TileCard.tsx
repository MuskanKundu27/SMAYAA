import type { KeyboardEvent } from 'react'

import type { Tile } from '../api/types'
import { formatValue, limitsText } from '../format'
import { displayedTile, useModuleEditing } from '../modules/editing'
import { RangeBar } from './RangeBar'
import { StatusPill } from './StatusPill'

/** One parameter: value (editable for inputs when allowed), unit, status, range bar, limits.
 *  `asSwitch` draws an on/off input (1 = on, 0 = off) as a switch instead of a number box. */
export function TileCard({ tile: savedTile, asSwitch = false }: { tile: Tile; asSwitch?: boolean }) {
  const { canEdit, drafts, setDraft, commit, cancel, setValue, saveStates, preview } = useModuleEditing()

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

  const saveBadge = saveState && (
    <div className={`tile-card__save tile-card__save--${saveState.kind}`} role="status">
      {saveState.kind === 'saving' && 'Saving…'}
      {saveState.kind === 'saved' && 'Saved ✓'}
      {saveState.kind === 'error' && saveState.message}
    </div>
  )

  if (asSwitch) {
    const on = savedTile.value !== null && savedTile.value >= 0.5
    const unknown = savedTile.value === null
    return (
      <div className={`tile-card tile-card--${tile.status}`}>
        <div className="tile-card__head">
          <span className="tile-card__label">{tile.label}</span>
          <StatusPill status={tile.status} />
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label={tile.label}
          className={`switch ${on ? 'switch--on' : ''} ${unknown ? 'switch--unknown' : ''}`}
          disabled={!editable || saveState?.kind === 'saving'}
          onClick={() => setValue(tile.key, on ? 0 : 1)}
        >
          <span className="switch__track">
            <span className="switch__knob" />
          </span>
          <span className="switch__text">{unknown ? 'Not set' : on ? 'ON' : 'OFF'}</span>
        </button>
        {saveBadge}
      </div>
    )
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

      {saveBadge}
    </div>
  )
}
