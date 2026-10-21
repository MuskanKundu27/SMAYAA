// Widget components: one per widget type in a module layout (registered in registry.ts).

import type { ReactNode } from 'react'

import type { Alert, TrendSeries, WidgetView } from '../api/types'
import { TileCard } from '../components/TileCard'
import { formatDateTime, formatValue, limitsText } from '../format'

export type WidgetProps = { widget: WidgetView }

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="widget">
      {title && <h2 className="widget__title">{title}</h2>}
      {children}
    </section>
  )
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
            <TileCard key={tile.key} tile={tile} />
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

export function PredictedProblemsWidget({ widget }: WidgetProps) {
  const problems = widget.problems ?? []
  const insufficient = widget.insufficient_rules ?? []
  return (
    <Section title={widget.title || 'Predicted problems'}>
      {problems.length === 0 && insufficient.length === 0 && (
        <p className="ok-message">No problems predicted from the latest values.</p>
      )}
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
      {insufficient.length > 0 && (
        <p className="muted">Insufficient data to evaluate: {insufficient.join(', ')}.</p>
      )}
      <p className="disclaimer">
        Probabilities are demo heuristics, not engineering guarantees.
      </p>
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

export function TrendChartWidget({ widget }: WidgetProps) {
  return (
    <Section title={widget.title || 'Trends'}>
      <div className="trends">
        {(widget.series ?? []).map((s) => (
          <TrendChart key={s.key} series={s} />
        ))}
      </div>
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
