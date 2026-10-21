import type { Limits, StatusLevel } from '../api/types'
import { rangeBarPositions } from '../format'

/** Warning band as a bar, the good range highlighted, and a marker at the current value. */
export function RangeBar({
  value,
  limits,
  status,
}: {
  value: number | null
  limits: Limits
  status: StatusLevel
}) {
  const { goodStart, goodEnd, marker } = rangeBarPositions(value, limits)
  return (
    <div className="range-bar" aria-hidden="true">
      <div
        className="range-bar__good"
        style={{ left: `${goodStart}%`, width: `${Math.max(goodEnd - goodStart, 1)}%` }}
      />
      {marker !== null && (
        <div className={`range-bar__marker range-bar__marker--${status}`} style={{ left: `${marker}%` }} />
      )}
    </div>
  )
}
