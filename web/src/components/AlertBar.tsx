import { useState } from 'react'

import { formatTime, formatValue } from '../format'
import { AlertDetails } from '../modules/widgets'
import { usePlantData } from '../plant/usePlantData'

/** Shown at the top of every page for plant users: the plant's current alerts. */
export function AlertBar() {
  const { alerts } = usePlantData()
  const [open, setOpen] = useState(false)
  if (!alerts) return null

  const list = alerts.alerts
  const high = list.filter((a) => a.severity === 'high').length
  const updated = alerts.reading
    ? `Updated ${formatTime(alerts.reading.recorded_at)} by ${alerts.reading.created_by?.name ?? 'unknown'}`
    : 'No readings yet'

  if (list.length === 0) {
    return (
      <div className="alert-bar alert-bar--ok" role="status">
        <span>✓ All parameters within range</span>
        <span className="alert-bar__meta">{updated}</span>
      </div>
    )
  }

  return (
    <div className={`alert-bar ${high ? 'alert-bar--high' : 'alert-bar--medium'}`} role="alert">
      <button className="alert-bar__summary" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <strong>
          {list.length} alert{list.length > 1 ? 's' : ''}
          {high > 0 && ` (${high} high)`}
        </strong>
        <span className="alert-bar__items">
          {list
            .slice(0, 4)
            .map((a) => `${a.label} ${formatValue(a.value)} ${a.unit} ${a.direction === 'high' ? '↑' : '↓'}`)
            .join(' · ')}
          {list.length > 4 && ' …'}
        </span>
        <span className="alert-bar__meta">{updated}</span>
        <span className="alert-bar__toggle">{open ? 'Hide' : 'Details'}</span>
      </button>
      {open && (
        <div className="alert-bar__details">
          {list.map((a) => (
            <AlertDetails key={a.parameter_key} alert={a} />
          ))}
        </div>
      )}
    </div>
  )
}
