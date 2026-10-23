// Which notifications the user has already looked at, so the bell only blinks for new ones.
// Remembered per user and plant in this browser (a convenience; storage may be unavailable).

import type { PlantAlerts } from '../api/types'

/** One id per thing worth noticing: an alert at a given severity, or a predicted problem.
 *  An alert that gets worse (warning → alert) counts as new. */
export function notificationIds(data: PlantAlerts | null): string[] {
  if (!data) return []
  return [
    ...data.alerts.map((a) => `alert:${a.parameter_key}:${a.level}`),
    ...data.problems.map((p) => `problem:${p.code}`),
  ]
}

export function hasUnseen(ids: readonly string[], seen: ReadonlySet<string>): boolean {
  return ids.some((id) => !seen.has(id))
}

const storageKey = (userId: string, plantId: string) => `smayaa.seen.${userId}.${plantId}`

export function loadSeen(userId: string, plantId: string): Set<string> {
  try {
    const raw = localStorage.getItem(storageKey(userId, plantId))
    return new Set(raw ? (JSON.parse(raw) as string[]) : [])
  } catch {
    return new Set()
  }
}

export function saveSeen(userId: string, plantId: string, ids: readonly string[]): void {
  try {
    localStorage.setItem(storageKey(userId, plantId), JSON.stringify(ids))
  } catch {
    // ignore: the bell just blinks again next time
  }
}
