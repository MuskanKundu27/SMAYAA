import { useEffect, useRef, useState } from 'react'

import { formatTime } from '../format'
import { AlertDetails } from '../modules/widgets'
import { usePlantData } from '../plant/usePlantData'
import { hasUnseen, loadSeen, notificationIds, saveSeen } from './seen'

/** The bell in the top bar: plant alerts and predicted problems. It blinks while there is
 *  something the user has not opened yet; opening it shows the details. Keyed by user + plant
 *  in AppLayout, so switching plant starts fresh. */
export function NotificationBell({ userId, plantId }: { userId: string; plantId: string }) {
  const { alerts: data } = usePlantData()
  const [open, setOpen] = useState(false)
  const [seen, setSeen] = useState(() => loadSeen(userId, plantId))
  const box = useRef<HTMLDivElement>(null)

  const ids = notificationIds(data)
  const alerts = data?.alerts ?? []
  const problems = data?.problems ?? []
  const count = alerts.length + problems.length
  const high = alerts.some((a) => a.severity === 'high')
  const blinking = hasUnseen(ids, seen)
  const tone = high ? 'high' : count > 0 ? 'medium' : 'ok'

  // Close when clicking outside the panel or pressing Escape.
  useEffect(() => {
    if (!open) return
    const onClick = (event: MouseEvent) => {
      if (box.current && !box.current.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  function toggle() {
    if (!open) {
      // Opening counts as having seen everything currently listed.
      setSeen(new Set(ids))
      saveSeen(userId, plantId, ids)
    }
    setOpen((o) => !o)
  }

  if (!data) return null
  const updated = data.reading
    ? `Updated ${formatTime(data.reading.recorded_at)} by ${data.reading.created_by?.name ?? 'unknown'}`
    : 'No readings yet'

  return (
    <div className="notify" ref={box}>
      <button
        type="button"
        className={`notify__bell notify__bell--${tone} ${blinking ? 'notify__bell--blink' : ''}`}
        onClick={toggle}
        aria-expanded={open}
        aria-label={count ? `${count} notification${count > 1 ? 's' : ''}` : 'No notifications'}
        title={count ? `${alerts.length} alerts, ${problems.length} predicted problems` : 'All clear'}
      >
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path
            fill="currentColor"
            d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-2 2v1h18v-1Z"
          />
        </svg>
        {count > 0 && <span className="notify__badge">{count}</span>}
      </button>

      {open && (
        <div className="notify__panel" role="dialog" aria-label="Notifications">
          <div className="notify__head">
            <strong>Notifications</strong>
            <span className="muted">{updated}</span>
          </div>

          {count === 0 ? (
            <p className="ok-message notify__empty">✓ All parameters within range. No problems predicted.</p>
          ) : (
            <>
              {alerts.length > 0 && (
                <section className="notify__section">
                  <h3>
                    Alerts ({alerts.length}){high && <span className="severity severity--high">High</span>}
                  </h3>
                  <div className="alert-cards">
                    {alerts.map((a) => (
                      <AlertDetails key={a.parameter_key} alert={a} />
                    ))}
                  </div>
                </section>
              )}
              {problems.length > 0 && (
                <section className="notify__section">
                  <h3>Predicted problems ({problems.length})</h3>
                  <ul className="problem-list">
                    {problems.map((p) => (
                      <li key={p.code} className="problem">
                        <div className="problem__head">
                          <span className="problem__code">{p.code}</span>
                          <span className="problem__title">{p.title}</span>
                          {p.probability !== null && <span className="problem__prob">{p.probability}%</span>}
                        </div>
                        {p.probability !== null && (
                          <div className="prob-bar" aria-hidden="true">
                            <div className="prob-bar__fill" style={{ width: `${p.probability}%` }} />
                          </div>
                        )}
                        <p className="problem__action">
                          <strong>Recommended:</strong> {p.action}
                        </p>
                      </li>
                    ))}
                  </ul>
                  <p className="disclaimer">Probabilities are demo heuristics, not engineering guarantees.</p>
                </section>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
