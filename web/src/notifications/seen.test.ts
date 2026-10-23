import { describe, expect, it } from 'vitest'

import type { Alert, PlantAlerts, PredictedProblem } from '../api/types'
import { hasUnseen, notificationIds } from './seen'

const alert = (key: string, level: 'warn' | 'bad') => ({ parameter_key: key, level }) as Alert
const problem = (code: string) => ({ code }) as PredictedProblem
const data = (alerts: Alert[], problems: PredictedProblem[] = []): PlantAlerts => ({
  reading: null,
  alerts,
  problems,
})

describe('notificationIds', () => {
  it('lists alerts with their level and predicted problems', () => {
    expect(notificationIds(data([alert('hard', 'warn')], [problem('TH-P02')]))).toEqual([
      'alert:hard:warn',
      'problem:TH-P02',
    ])
    expect(notificationIds(null)).toEqual([])
  })
})

describe('hasUnseen', () => {
  it('is false once everything was seen, true for a new or worse alert', () => {
    const seen = new Set(notificationIds(data([alert('hard', 'warn')])))
    expect(hasUnseen(notificationIds(data([alert('hard', 'warn')])), seen)).toBe(false)
    expect(hasUnseen(notificationIds(data([alert('hard', 'bad')])), seen)).toBe(true)
    expect(hasUnseen(notificationIds(data([alert('hard', 'warn'), alert('ph', 'warn')])), seen)).toBe(true)
  })

  it('does not blink when there is nothing', () => {
    expect(hasUnseen([], new Set())).toBe(false)
  })
})
