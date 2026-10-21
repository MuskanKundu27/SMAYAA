import { describe, expect, it } from 'vitest'

import type { Tile } from '../api/types'
import { displayedTile } from './editing'
import { WIDGETS, widgetFor } from './registry'
import { UnknownWidget } from './widgets'

const tile = (overrides: Partial<Tile> = {}): Tile => ({
  key: 'hard',
  label: 'Hardness',
  unit: 'ppm',
  precision: 0,
  kind: 'input',
  value: 650,
  status: 'warn',
  direction: 'high',
  limits: { warn_min: 100, good_min: 200, good_max: 600, warn_max: 800 },
  editable: true,
  insufficient_data: false,
  ...overrides,
})

describe('widget registry', () => {
  it('has a component for every widget type the API can send', () => {
    const apiTypes = [
      'input_group',
      'value_tiles',
      'trend_chart',
      'predicted_problems',
      'alert_list',
      'inputs_summary',
      'text_note',
    ]
    expect(Object.keys(WIDGETS).sort()).toEqual(apiTypes.sort())
  })

  it('falls back to a placeholder for unknown types instead of breaking the page', () => {
    expect(widgetFor('something_new')).toBe(UnknownWidget)
  })
})

describe('displayedTile', () => {
  it('shows the saved tile when there is no live preview', () => {
    const saved = tile()
    expect(displayedTile(saved, {})).toBe(saved)
  })

  it('shows the live preview while typing, keeping whether it is editable', () => {
    const saved = tile({ editable: true })
    const live = tile({ value: 900, status: 'bad', editable: false })
    expect(displayedTile(saved, { hard: live })).toEqual({ ...live, editable: true })
  })
})
