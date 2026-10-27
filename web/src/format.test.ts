import { describe, expect, it } from 'vitest'

import { formatDelta, formatValue, limitsText, parseInput, rangeBarPositions, rangeLabel } from './format'

const HARD = { warn_min: 100, good_min: 200, good_max: 600, warn_max: 800 }

describe('formatValue', () => {
  it('uses the parameter precision', () => {
    expect(formatValue(7.9, 2)).toBe('7.90')
    expect(formatValue(650, 0)).toBe('650')
  })

  it('shows a dash for missing values', () => {
    expect(formatValue(null)).toBe('—')
    expect(formatValue(undefined)).toBe('—')
  })
})

describe('parseInput', () => {
  it('accepts numbers, including thousands separators', () => {
    expect(parseInput(' 650 ')).toEqual({ ok: true, value: 650 })
    expect(parseInput('2,400')).toEqual({ ok: true, value: 2400 })
    expect(parseInput('-0.5')).toEqual({ ok: true, value: -0.5 })
  })

  it('treats an empty box as clearing the value', () => {
    expect(parseInput('')).toEqual({ ok: true, value: null })
  })

  it('rejects text', () => {
    expect(parseInput('lots')).toEqual({ ok: false, error: 'Enter a number' })
  })
})

describe('rangeBarPositions', () => {
  it('places the good range and the value inside the warning band', () => {
    const { goodStart, goodEnd, marker } = rangeBarPositions(650, HARD)
    expect(goodStart).toBeCloseTo(14.29, 2) // (200 - 100) / 700
    expect(goodEnd).toBeCloseTo(71.43, 2) // (600 - 100) / 700
    expect(marker).toBeCloseTo(78.57, 2) // (650 - 100) / 700
  })

  it('keeps the marker on the bar for values outside the warning band', () => {
    expect(rangeBarPositions(5000, HARD).marker).toBe(100)
    expect(rangeBarPositions(-5, HARD).marker).toBe(0)
  })

  it('has no marker without a value', () => {
    expect(rangeBarPositions(null, HARD).marker).toBeNull()
  })
})

describe('limitsText', () => {
  it('describes limits with units', () => {
    expect(limitsText(HARD, 'ppm')).toBe('Good 200–600 ppm · Warning 100–800 ppm')
    expect(limitsText(null)).toBe('No limits')
  })
})

describe('dashboard labels', () => {
  it('shows % changes with arrows', () => {
    expect(formatDelta(27.7)).toBe('↑ 28%')
    expect(formatDelta(-9.6)).toBe('↓ 10%')
  })

  it('names time ranges', () => {
    expect([6, 24, 168, 720].map(rangeLabel)).toEqual(['6H', '24H', '7D', '30D'])
  })
})
