// Small display helpers. Pure functions, so they are easy to test.

import type { Limits, StatusLevel } from './api/types'

export function formatValue(value: number | null | undefined, precision = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return value.toLocaleString('en-IN', {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  })
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** A % change with an arrow, e.g. "↑ 28%" or "↓ 12%". */
export function formatDelta(delta: number): string {
  const arrow = delta > 0 ? '↑' : delta < 0 ? '↓' : '→'
  return `${arrow} ${Math.abs(Math.round(delta))}%`
}

/** Label of a time-range button: 6 → "6H", 24 → "24H", 168 → "7D", 720 → "30D". */
export function rangeLabel(hours: number): string {
  return hours > 24 && hours % 24 === 0 ? `${hours / 24}D` : `${hours}H`
}

export const STATUS_LABELS: Record<StatusLevel, string> = {
  good: 'Good',
  warn: 'Warning',
  bad: 'Alert',
  na: 'No data',
}

export function limitsText(limits: Limits | null, unit = ''): string {
  if (!limits) return 'No limits'
  const u = unit ? ` ${unit}` : ''
  return `Good ${limits.good_min}–${limits.good_max}${u} · Warning ${limits.warn_min}–${limits.warn_max}${u}`
}

/** Where things sit on a range bar, as percentages (0–100) of the warning band. */
export function rangeBarPositions(
  value: number | null,
  limits: Limits,
): { goodStart: number; goodEnd: number; marker: number | null } {
  const span = limits.warn_max - limits.warn_min
  const pct = (x: number) =>
    span > 0 ? Math.min(100, Math.max(0, ((x - limits.warn_min) / span) * 100)) : 50
  return {
    goodStart: pct(limits.good_min),
    goodEnd: pct(limits.good_max),
    marker: value === null ? null : pct(value),
  }
}

export type ParsedInput = { ok: true; value: number | null } | { ok: false; error: string }

/** What the user typed in a tile. Empty means "clear the value". */
export function parseInput(text: string): ParsedInput {
  const trimmed = text.trim().replace(/,/g, '')
  if (trimmed === '') return { ok: true, value: null }
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return { ok: false, error: 'Enter a number' }
  return { ok: true, value }
}
