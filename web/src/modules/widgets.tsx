// Widget components: one per widget type in a module layout (registered in registry.ts).

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { getModuleTrend } from '../api/plant'
import type { Alert, PredictedProblem, TrendSeries, WidgetView } from '../api/types'
import { TileCard } from '../components/TileCard'
import { formatDateTime, formatEta, formatValue, limitsText, rangeLabel } from '../format'
import { useModuleLocation } from './moduleContext'

/** `index` is the widget's position in the module layout. */
export type WidgetProps = { widget: WidgetView; index: number }

export function Section({
  title,
  children,
  card = false,
  actions,
}: {
  title: string
  children: ReactNode
  /** Draw the whole widget as one card (panels such as tables and charts). */
  card?: boolean
  /** Controls shown at the right of the title (e.g. time-range buttons). */
  actions?: ReactNode
}) {
  return (
    <section className={card ? 'widget widget--card' : 'widget'}>
      {(title || actions) && (
        <div className="widget__head">
          {title && <h2 className="widget__title">{title}</h2>}
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}

export function PriorityBadge({ priority }: { priority: PredictedProblem['priority'] }) {
  const label = { high: 'High', medium: 'Medium', low: 'Low' }[priority]
  return <span className={`severity severity--${priority}`}>{label}</span>
}

export function TilesWidget({ widget }: WidgetProps) {
  const tiles = widget.tiles ?? []
  return (
    <Section title={widget.title}>
      {tiles.length === 0 ? (
        <p className="muted">No parameters configured.</p>
      ) : (
        <div className="tile-cards">
          {tiles.map((tile) => (
            <TileCard key={tile.key} tile={tile} asSwitch={widget.switches?.includes(tile.key) ?? false} />
          ))}
        </div>
      )}
    </Section>
  )
}

export function InputsSummaryWidget({ widget }: WidgetProps) {
  return (
    <Section title={widget.title || 'Inputs used'}>
      <table className="summary-table">
        <tbody>
          {(widget.tiles ?? []).map((t) => (
            <tr key={t.key}>
              <th scope="row">{t.label}</th>
              <td>
                {t.insufficient_data ? (
                  <span className="muted">Insufficient data</span>
                ) : (
                  <>
                    {formatValue(t.value, t.precision)} <span className="muted">{t.unit}</span>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  )
}

function ProblemsTable({ problems }: { problems: PredictedProblem[] }) {
  return (
    <table className="data-table compact-table">
      <thead>
        <tr>
          <th>Issue</th>
          <th>Severity</th>
          <th>Probability</th>
          <th>ETA</th>
        </tr>
      </thead>
      <tbody>
        {problems.map((p) => (
          <tr key={p.code}>
            <td>
              {p.title} <span className="muted problem__code-small">{p.code}</span>
            </td>
            <td>
              <PriorityBadge priority={p.priority} />
            </td>
            <td className="nowrap">
              {p.probability === null ? (
                '—'
              ) : (
                <span className="prob-inline">
                  <span className="prob-bar prob-bar--inline" aria-hidden="true">
                    <span className="prob-bar__fill" style={{ width: `${p.probability}%` }} />
                  </span>
                  {p.probability}%
                </span>
              )}
            </td>
            <td className="nowrap">{formatEta(p.eta_hours)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export function PredictedProblemsWidget({ widget }: WidgetProps) {
  const problems = widget.problems ?? []
  const insufficient = widget.insufficient_rules ?? []
  const asTable = widget.style === 'table'
  return (
    <Section title={widget.title || 'Predicted problems'} card={asTable}>
      {problems.length === 0 && insufficient.length === 0 && (
        <p className="ok-message">No problems predicted from the latest values.</p>
      )}
      {asTable && problems.length > 0 && <ProblemsTable problems={problems} />}
      <ul className="problem-list" style={asTable ? { display: 'none' } : undefined}>
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
      {insufficient.length > 0 && (
        <p className="muted">Insufficient data to evaluate: {insufficient.join(', ')}.</p>
      )}
    </Section>
  )
}

export function AlertDetails({ alert }: { alert: Alert }) {
  return (
    <div className={`alert-card alert-card--${alert.severity}`}>
      <div className="alert-card__head">
        <strong>{alert.label}</strong>
        <span>
          {formatValue(alert.value)} {alert.unit} · {alert.direction === 'high' ? 'above' : 'below'}{' '}
          range
        </span>
        <span className={`severity severity--${alert.severity}`}>
          {alert.severity === 'high' ? 'High' : 'Medium'}
        </span>
      </div>
      <div className="alert-card__limits">{limitsText(alert.limits, alert.unit)}</div>
      {alert.modules.length > 0 && (
        <div className="alert-card__modules">Affects: {alert.modules.join(', ')}</div>
      )}
      <dl className="alert-card__advice">
        <dt>Likely cause</dt>
        <dd>{alert.cause}</dd>
        <dt>Treatment</dt>
        <dd>{alert.treatment}</dd>
        <dt>Precautions</dt>
        <dd>{alert.precautions}</dd>
      </dl>
      {alert.needs_review && (
        <p className="disclaimer">Sample guidance – to be reviewed by a water-treatment engineer.</p>
      )}
    </div>
  )
}

export function AlertListWidget({ widget }: WidgetProps) {
  const alerts = widget.alerts ?? []
  return (
    <Section title={widget.title || 'Alerts'}>
      {alerts.length === 0 ? (
        <p className="ok-message">All parameters are within range.</p>
      ) : (
        <div className="alert-cards">
          {alerts.map((a) => (
            <AlertDetails key={a.parameter_key} alert={a} />
          ))}
        </div>
      )}
    </Section>
  )
}

function TrendChart({ series }: { series: TrendSeries }) {
  const width = 320
  const height = 90
  const points = series.points.filter((p) => p.v !== null) as { t: string; v: number }[]
  if (points.length < 2) {
    return <p className="muted">{series.label}: not enough history yet.</p>
  }
  const values = points.map((p) => p.v)
  const lo = Math.min(...values, series.limits?.warn_min ?? Infinity)
  const hi = Math.max(...values, series.limits?.warn_max ?? -Infinity)
  const y = (v: number) => (hi === lo ? height / 2 : height - ((v - lo) / (hi - lo)) * height)
  const x = (i: number) => (i / (points.length - 1)) * width
  const path = points.map((p, i) => `${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(' ')
  return (
    <figure className="trend">
      <figcaption>
        {series.label} <span className="muted">({series.unit})</span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${series.label} trend`}>
        {series.limits && (
          <rect
            className="trend__good"
            x={0}
            width={width}
            y={y(series.limits.good_max)}
            height={Math.max(y(series.limits.good_min) - y(series.limits.good_max), 1)}
          />
        )}
        <polyline className="trend__line" points={path} />
      </svg>
      <div className="trend__axis muted">
        <span>{formatDateTime(points[0].t)}</span>
        <span>{formatDateTime(points[points.length - 1].t)}</span>
      </div>
    </figure>
  )
}

const SERIES_COLOURS = ['var(--blue)', '#e8590c', '#2f9e44', '#7048e8']

/** One or more series in one chart: the first on the left axis (with its good range as a
 *  band), the others on the right axis. */
function CombinedChart({ series }: { series: TrendSeries[] }) {
  const width = 320
  const height = 110
  const lines = series.map((s) => ({
    series: s,
    points: s.points.filter((p) => p.v !== null).map((p) => ({ t: Date.parse(p.t), v: p.v as number })),
  }))
  const all = lines.flatMap((l) => l.points)
  if (all.length < 2) return <p className="muted">Not enough history yet.</p>

  const t0 = Math.min(...all.map((p) => p.t))
  const t1 = Math.max(...all.map((p) => p.t))
  const x = (t: number) => (t1 === t0 ? width / 2 : ((t - t0) / (t1 - t0)) * width)
  const axis = (values: number[]) => {
    const lo = Math.min(...values)
    const hi = Math.max(...values)
    return { lo, hi, y: (v: number) => (hi === lo ? height / 2 : height - 4 - ((v - lo) / (hi - lo)) * (height - 8)) }
  }
  const firstLimits = series[0].limits
  const left = axis(
    lines[0].points
      .map((p) => p.v)
      .concat(firstLimits ? [firstLimits.good_min, firstLimits.good_max] : [])
      .concat(lines[0].points.length ? [] : [0]),
  )
  const rightValues = lines.slice(1).flatMap((l) => l.points.map((p) => p.v))
  const right = rightValues.length ? axis(rightValues) : left

  return (
    <figure className="trend trend--plain">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={series.map((s) => s.label).join(' and ')}>
        {firstLimits && (
          <rect
            className="trend__good"
            x={0}
            width={width}
            y={left.y(firstLimits.good_max)}
            height={Math.max(left.y(firstLimits.good_min) - left.y(firstLimits.good_max), 1)}
          />
        )}
        {lines.map((line, i) => {
          const scale = i === 0 ? left : right
          const path = line.points.map((p) => `${x(p.t).toFixed(1)},${scale.y(p.v).toFixed(1)}`).join(' ')
          return <polyline key={line.series.key} className="trend__series" stroke={SERIES_COLOURS[i % 4]} points={path} />
        })}
      </svg>
      <div className="trend__axis muted">
        <span>{formatDateTime(new Date(t0).toISOString())}</span>
        <span>{formatDateTime(new Date(t1).toISOString())}</span>
      </div>
      <ul className="trend__legend">
        {lines.map((line, i) => {
          const latest = line.points[line.points.length - 1]
          return (
            <li key={line.series.key}>
              <span className="trend__swatch" style={{ background: SERIES_COLOURS[i % 4] }} />
              {line.series.label}
              {line.series.unit && <span className="muted"> ({line.series.unit})</span>}
              {latest && <strong> {formatValue(latest.v)}</strong>}
            </li>
          )
        })}
      </ul>
    </figure>
  )
}

export function TrendChartWidget({ widget, index }: WidgetProps) {
  const { plantId, moduleKey } = useModuleLocation()
  const initial = widget.hours ?? 24
  const [hours, setHours] = useState(initial)
  const [loaded, setLoaded] = useState<{ hours: number; series: TrendSeries[] } | null>(null)
  const [failed, setFailed] = useState(false)

  // Another time range: ask the server for it (again whenever the screen reloads).
  useEffect(() => {
    if (hours === initial || !plantId) return
    let cancelled = false
    getModuleTrend(plantId, moduleKey, index, hours)
      .then((series) => {
        if (!cancelled) {
          setLoaded({ hours, series })
          setFailed(false)
        }
      })
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [plantId, moduleKey, index, hours, initial, widget.series])

  const series = hours === initial ? (widget.series ?? []) : loaded?.hours === hours ? loaded.series : null
  const ranges = widget.ranges ?? []
  const buttons = ranges.length > 1 && (
    <div className="range-buttons" role="group" aria-label="Time range">
      {ranges.map((h) => (
        <button
          key={h}
          type="button"
          className={h === hours ? 'range-button range-button--active' : 'range-button'}
          aria-pressed={h === hours}
          onClick={() => setHours(h)}
        >
          {rangeLabel(h)}
        </button>
      ))}
    </div>
  )

  let body: ReactNode
  if (failed && hours !== initial) body = <p className="form-error">Could not load this time range.</p>
  else if (series === null) body = <p className="muted">Loading…</p>
  else if (widget.combine || ranges.length > 0) body = <CombinedChart series={series} />
  else
    body = (
      <div className="trends">
        {series.map((s) => (
          <TrendChart key={s.key} series={s} />
        ))}
      </div>
    )

  return (
    <Section title={widget.title || 'Trends'} card={ranges.length > 0 || Boolean(widget.combine)} actions={buttons}>
      {body}
    </Section>
  )
}

export function TextNoteWidget({ widget }: WidgetProps) {
  return (
    <Section title={widget.title}>
      <p className="text-note">{widget.text}</p>
    </Section>
  )
}

export function UnknownWidget({ widget }: WidgetProps) {
  return (
    <Section title={widget.title}>
      <p className="muted">This screen element ({widget.type}) is not available in this version.</p>
    </Section>
  )
}
