import type { StatusLevel } from '../api/types'
import { STATUS_LABELS } from '../format'

export function StatusPill({ status }: { status: StatusLevel }) {
  return <span className={`pill pill--${status}`}>{STATUS_LABELS[status]}</span>
}
