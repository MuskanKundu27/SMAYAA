import { describe, expect, it } from 'vitest'

import { parseDraft, toDraft } from './limits'

describe('parseDraft', () => {
  it('reads four numbers in the right order', () => {
    expect(parseDraft({ warn_min: '6.8', good_min: '7.2', good_max: '8.2', warn_max: '8.8' })).toEqual({
      limits: { warn_min: 6.8, good_min: 7.2, good_max: 8.2, warn_max: 8.8 },
    })
  })

  it('treats an untouched empty row as nothing to save', () => {
    expect(parseDraft(toDraft(null))).toBeNull()
  })

  it('rejects missing numbers and wrong order', () => {
    expect(parseDraft({ warn_min: '1', good_min: '', good_max: '3', warn_max: '4' })).toEqual({
      error: 'Good min must be a number.',
    })
    expect(parseDraft({ warn_min: '5', good_min: '2', good_max: '3', warn_max: '4' })).toHaveProperty('error')
  })
})
