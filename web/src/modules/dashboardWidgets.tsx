// Dashboard widgets: KPI / benefit cards, recommended actions, quick links and the system
// diagram (registered in registry.ts). They only draw what the API sends.

import { useNavigate } from 'react-router'

import type { KpiCard, QuickLink, Tile } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { RangeBar } from '../components/RangeBar'
import { StatusPill } from '../components/StatusPill'
import { formatDelta, formatValue, limitsText } from '../format'
import { usePlantData } from '../plant/usePlantData'
import { PriorityBadge, Section } from './widgets'
import type { WidgetProps } from './widgets'

function value(tile: Tile): string {
  return formatValue(tile.value, tile.precision)
}

function targetText(card: KpiCard): string | null {
  const unit = card.tile.unit ? ` ${card.tile.unit}` : ''
  const fmt = (v: number) => formatValue(v, card.tile.precision)
  if (card.target_min !== null && card.target_max !== null) {
    return `Target: ${fmt(card.target_min)} – ${fmt(card.target_max)}${unit}`
  }
  if (card.target_max !== null) return `Target: ≤ ${fmt(card.target_max)}${unit}`
  return null
}

function DeltaText({ card }: { card: KpiCard }) {
  if (card.delta === null) return null
  const good = card.delta_good === 'up' ? card.delta > 0 : card.delta < 0
  return <span className={good ? 'delta delta--good' : 'delta delta--bad'}>{formatDelta(card.delta)}</span>
}

function KpiCardView({ card, benefit }: { card: KpiCard; benefit: boolean }) {
  const { tile } = card
  if (tile.insufficient_data) {
    return (
      <div className="kpi-card kpi-card--na">
        <div className="kpi-card__label">{tile.label}</div>
        <div className="kpi-card__value muted">Insufficient data</div>
      </div>
    )
  }
  const rangeCaption =
    card.in_range !== null
      ? card.in_range
        ? 'Within target range'
        : 'Outside target range'
      : tile.value === null
        ? 'No data'
        : 'No target set'

  if (benefit) {
    return (
      <div className={`kpi-card kpi-card--${card.status} kpi-card--benefit`}>
        <div className="kpi-card__label">{tile.label}</div>
        <div className="kpi-card__value">
          {value(tile)}
          {tile.unit && <span className="kpi-card__unit">{tile.unit}</span>}
        </div>
        <div className="kpi-card__foot">
          <span>{card.caption || rangeCaption}</span>
          <DeltaText card={card} />
        </div>
      </div>
    )
  }

  // KPI style: like the parameter tiles — status, range bar and the good / warning ranges.
  const fromLimits = tile.limits !== null && card.target_min !== null
  const target = fromLimits ? null : targetText(card)
  return (
    <div className={`kpi-card kpi-card--${card.status}`}>
      <div className="kpi-card__head">
        <span className="kpi-card__label">{tile.label}</span>
        {card.status !== 'na' && <StatusPill status={card.status} />}
      </div>
      <div className="kpi-card__value">
        {value(tile)}
        {tile.unit && <span className="kpi-card__unit">{tile.unit}</span>}
      </div>
      {fromLimits && tile.limits && <RangeBar value={tile.value} limits={tile.limits} status={card.status} />}
      <div className="kpi-card__foot">
        {fromLimits && <span>{limitsText(tile.limits, tile.unit)}</span>}
        {target && <span>{target}</span>}
        {!fromLimits && !target && card.caption && card.delta === null && <span>{card.caption}</span>}
      </div>
      {card.delta !== null && (
        <div className="kpi-card__foot">
          {card.caption && <span>{card.caption}</span>}
          <DeltaText card={card} />
        </div>
      )}
    </div>
  )
}

export function KpiCardsWidget({ widget }: WidgetProps) {
  const benefit = widget.style === 'benefit'
  return (
    <Section title={widget.title} card={benefit}>
      <div className={benefit ? 'kpi-cards kpi-cards--benefit' : 'kpi-cards'}>
        {(widget.cards ?? []).map((card, i) => (
          <KpiCardView key={`${card.tile.key}-${i}`} card={card} benefit={benefit} />
        ))}
      </div>
    </Section>
  )
}

export function RecommendedActionsWidget({ widget }: WidgetProps) {
  const actions = widget.problems ?? []
  return (
    <Section title={widget.title || 'Recommended actions'} card>
      {actions.length === 0 ? (
        <p className="ok-message">No actions needed right now.</p>
      ) : (
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>Action</th>
              <th>Priority</th>
              <th>Expected benefit</th>
            </tr>
          </thead>
          <tbody>
            {actions.map((a) => (
              <tr key={a.code}>
                <td>{a.action}</td>
                <td>
                  <PriorityBadge priority={a.priority} />
                </td>
                <td className="benefit-text">{a.benefit || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Section>
  )
}

/** The app path for a quick link, or null if this user cannot open it. */
function linkPath(link: QuickLink, can: (p: string) => boolean, moduleKeys: Set<string>): string | null {
  if (link.target === 'limits') return can('limits.read') ? '/limits' : null
  if (link.target === 'operator-profiles') return can('operator_profiles.manage') ? '/operator-profiles' : null
  const key = link.target.startsWith('module:') ? link.target.slice('module:'.length) : null
  return key && moduleKeys.has(key) ? `/m/${key}` : null
}

export function QuickLinksWidget({ widget }: WidgetProps) {
  const navigate = useNavigate()
  const { can } = useAuth()
  const { modules } = usePlantData()
  const moduleKeys = new Set(modules.map((m) => m.key))
  const links = (widget.links ?? [])
    .map((link) => ({ link, path: linkPath(link, can, moduleKeys) }))
    .filter((l): l is { link: QuickLink; path: string } => l.path !== null)
  return (
    <Section title={widget.title || 'Quick actions'} card>
      {links.length === 0 ? (
        <p className="muted">No quick actions available for your role.</p>
      ) : (
        <div className="quick-links">
          {links.map(({ link, path }) => (
            <button key={link.label} type="button" className="quick-link" onClick={() => void navigate(path)}>
              {link.label}
              <span aria-hidden="true">›</span>
            </button>
          ))}
        </div>
      )}
    </Section>
  )
}

function FlowBadge({
  tile,
  x,
  y,
  tone,
}: {
  tile: Tile | undefined
  x: number
  y: number
  tone: 'makeup' | 'recycled' | 'evaporation' | 'blowdown' | 'side'
}) {
  if (!tile) return null
  const text = tile.insufficient_data ? 'n/a' : `${value(tile)} ${tile.unit}`
  return (
    <g className={`badge badge--${tone}`}>
      <rect className="badge__box" x={x} y={y} width={136} height={52} rx={10} />
      <rect className="badge__bar" x={x} y={y} width={6} height={52} rx={3} />
      <text className="badge__title" x={x + 16} y={y + 20}>
        {tile.label}
      </text>
      <text className="badge__value" x={x + 16} y={y + 41}>
        {text}
      </text>
    </g>
  )
}

/** A cooling tower with make-up in, blowdown out and the side-stream filter loop, plus a list
 *  of measurement points. Values come from the widget's parameters; recycled water and
 *  evaporation are drawn only when the widget names them. */
export function SystemDiagramWidget({ widget }: WidgetProps) {
  const named = widget.named ?? {}
  const points = widget.tiles ?? []
  return (
    <Section title={widget.title} card>
      <div className="diagram">
        <svg viewBox="0 0 540 330" role="img" aria-label="Cooling tower with make-up water, blowdown and side-stream filter">
          <defs>
            <linearGradient id="dg-body" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#c9d8ee" />
              <stop offset="50%" stopColor="#eef3fb" />
              <stop offset="100%" stopColor="#b9cbe6" />
            </linearGradient>
            <linearGradient id="dg-water" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#5aa2ff" />
              <stop offset="100%" stopColor="#1f6feb" />
            </linearGradient>
            <linearGradient id="dg-filter" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#ffd8a8" />
              <stop offset="50%" stopColor="#fff4e6" />
              <stop offset="100%" stopColor="#ffc078" />
            </linearGradient>
            <marker id="dg-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M0 0 L10 5 L0 10 Z" fill="context-stroke" />
            </marker>
          </defs>

          {/* vapour rising from the fans */}
          <g className="diagram__vapour">
            <circle cx={232} cy={36} r={12} />
            <circle cx={246} cy={22} r={9} />
            <circle cx={302} cy={34} r={12} />
            <circle cx={316} cy={20} r={9} />
          </g>

          {/* tower: fan stacks, body, louvres, spray */}
          <rect className="diagram__stack" x={212} y={52} width={56} height={22} rx={4} />
          <rect className="diagram__stack" x={282} y={52} width={56} height={22} rx={4} />
          <ellipse className="diagram__fan" cx={240} cy={52} rx={24} ry={5} />
          <ellipse className="diagram__fan" cx={310} cy={52} rx={24} ry={5} />
          <path className="diagram__body" d="M190 74 L360 74 L378 214 L172 214 Z" />
          <rect className="diagram__eliminator" x={194} y={84} width={162} height={10} rx={2} />
          <g className="diagram__spray">
            {[214, 240, 266, 292, 318, 344].map((sx) => (
              <path key={sx} d={`M${sx} 104 l-4 12 M${sx} 104 l0 14 M${sx} 104 l4 12`} />
            ))}
          </g>
          <g className="diagram__louvres">
            {[150, 164, 178, 192].map((ly) => (
              <path key={ly} d={`M${183 - (ly - 150) * 0.12} ${ly} L367 ${ly} `} />
            ))}
          </g>

          {/* basin with water */}
          <rect className="diagram__basin" x={160} y={212} width={230} height={40} rx={8} />
          <path className="diagram__water" d="M166 226 q14 -6 28 0 t28 0 t28 0 t28 0 t28 0 t28 0 t28 0 t22 0 V246 H166 Z" />

          {/* pipes: make-up in (left), blowdown out (right), side-stream loop (below) */}
          <path className="diagram__pipe diagram__pipe--makeup" d="M28 196 H120 Q140 196 140 216 V230 H160" markerEnd="url(#dg-arrow)" />
          <path className="diagram__pipe diagram__pipe--blowdown" d="M390 236 H430 Q450 236 450 256 V296 H512" markerEnd="url(#dg-arrow)" />
          <path className="diagram__pipe diagram__pipe--side" d="M300 252 V292 H262" markerEnd="url(#dg-arrow)" />
          <path className="diagram__pipe diagram__pipe--side" d="M190 292 H214" />
          <path className="diagram__pipe diagram__pipe--side" d="M190 292 Q174 292 174 276 V256" markerEnd="url(#dg-arrow)" />
          {named.recycled && (
            <path className="diagram__pipe diagram__pipe--recycled" d="M28 244 H160" markerEnd="url(#dg-arrow)" />
          )}
          {named.evaporation && (
            <path className="diagram__pipe diagram__pipe--evaporation" d="M338 40 Q352 28 362 30" markerEnd="url(#dg-arrow)" />
          )}

          {/* side-stream filter vessel */}
          <rect className="diagram__filter" x={214} y={274} width={48} height={40} rx={12} />
          <path className="diagram__filter-media" d="M220 290 H256 M220 298 H256" />

          <FlowBadge tile={named.makeup} x={8} y={128} tone="makeup" />
          <FlowBadge tile={named.recycled} x={8} y={254} tone="recycled" />
          <FlowBadge tile={named.evaporation} x={368} y={6} tone="evaporation" />
          <FlowBadge tile={named.blowdown} x={396} y={160} tone="blowdown" />
          <FlowBadge tile={named.sidestream} x={20} y={268} tone="side" />
        </svg>

        {points.length > 0 && (
          <div className="diagram__points">
            <h3 className="diagram__points-title">{widget.text || 'Chemistry measurement points'}</h3>
            <ul>
              {points.map((t) => (
                <li key={t.key}>
                  <span className={`status-dot status-dot--${t.status}`} aria-hidden="true" />
                  <span className="diagram__point-label">{t.label}</span>
                  <span className={`diagram__point-value status-text--${t.status}`}>
                    {t.insufficient_data ? 'n/a' : value(t)} <span className="muted">{t.unit}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Section>
  )
}
