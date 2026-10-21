import type { Limits } from '../api/types'
import { parseInput } from '../format'

export const LIMIT_FIELDS: { key: keyof Limits; label: string }[] = [
  { key: 'warn_min', label: 'Warning min' },
  { key: 'good_min', label: 'Good min' },
  { key: 'good_max', label: 'Good max' },
  { key: 'warn_max', label: 'Warning max' },
]

/** The four limit boxes as typed. */
export type LimitDraft = Record<keyof Limits, string>

export const toDraft = (limits: Limits | null): LimitDraft => ({
  warn_min: limits ? String(limits.warn_min) : '',
  good_min: limits ? String(limits.good_min) : '',
  good_max: limits ? String(limits.good_max) : '',
  warn_max: limits ? String(limits.warn_max) : '',
})

/** The four numbers of a draft, or an error text. All boxes empty = nothing to save (null). */
export function parseDraft(draft: LimitDraft): { limits: Limits } | { error: string } | null {
  if (LIMIT_FIELDS.every((f) => draft[f.key].trim() === '')) return null
  const values: Partial<Limits> = {}
  for (const f of LIMIT_FIELDS) {
    const parsed = parseInput(draft[f.key])
    if (!parsed.ok || parsed.value === null) return { error: `${f.label} must be a number.` }
    values[f.key] = parsed.value
  }
  const l = values as Limits
  if (!(l.warn_min <= l.good_min && l.good_min <= l.good_max && l.good_max <= l.warn_max)) {
    return { error: 'Order must be: warning min ≤ good min ≤ good max ≤ warning max.' }
  }
  return { limits: l }
}
