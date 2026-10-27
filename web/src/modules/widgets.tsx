// Widget components: one per widget type in a module layout (registered in registry.ts).

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { getModuleTrend } from '../api/plant'
import type { Alert, PredictedProblem, TrendSeries, WidgetView } from '../api/types'
import { TileCard } from '../components/TileCard'
import { formatValue, limitsText, rangeLabel } from '../format'
import { LineChart } from './charts'
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
  return (
    <figure className="trend">
      <figcaption>
        {series.label} {series.unit && <span className="muted">({series.unit})</span>}
      </figcaption>
      <LineChart series={[series]} />
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
  else if (widget.combine || ranges.length > 0) body = <LineChart series={series} />
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
