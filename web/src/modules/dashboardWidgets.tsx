// Dashboard widgets: KPI / benefit cards, recommended actions, quick links and the system
// diagram (registered in registry.ts). They only draw what the API sends.

import { useNavigate } from 'react-router'

import type { KpiCard, QuickLink, Tile } from '../api/types'
import { useAuth } from '../auth/useAuth'
import { formatDelta, formatValue, STATUS_LABELS } from '../format'
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
  const target = targetText(card)
  const rangeCaption =
    card.in_range === null ? 'No data' : card.in_range ? 'Within target range' : 'Outside target range'
  return (
    <div className={`kpi-card kpi-card--${card.status}${benefit ? ' kpi-card--benefit' : ''}`}>
      <div className="kpi-card__label">{tile.label}</div>
      <div className="kpi-card__value">
        {value(tile)}
        {tile.unit && <span className="kpi-card__unit">{tile.unit}</span>}
      </div>
      <div className="kpi-card__foot">
        {target && <span>{target}</span>}
        {!target && card.caption && <span>{card.caption}</span>}
        {!target && !card.caption && card.in_range !== null && <span>{rangeCaption}</span>}
        <DeltaText card={card} />
        {!benefit && card.status !== 'na' && (
          <span className={`kpi-card__status kpi-card__status--${card.status}`} title={STATUS_LABELS[card.status]}>
            {card.status === 'good' ? '✓' : '!'}
          </span>
        )}
      </div>
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

function FlowLabel({ tile, x, y }: { tile: Tile | undefined; x: number; y: number }) {
  if (!tile) return null
  return (
    <g>
      <rect className="diagram__label" x={x} y={y} width={124} height={46} rx={6} />
      <text className="diagram__label-title" x={x + 8} y={y + 17}>
        {tile.label}
      </text>
      <text className="diagram__label-value" x={x + 8} y={y + 37}>
        {tile.insufficient_data ? 'n/a' : `${value(tile)} ${tile.unit}`}
      </text>
    </g>
  )
}

/** A schematic cooling tower: make-up in, blowdown out, side-stream filter loop, plus the
 *  chemistry measurement points as a list. */
export function SystemDiagramWidget({ widget }: WidgetProps) {
  const named = widget.named ?? {}
  return (
    <Section title={widget.title} card>
      <div className="diagram">
        <svg viewBox="0 0 440 230" role="img" aria-label="Cooling tower with make-up, blowdown and side-stream filter">
          {/* tower */}
          <path className="diagram__tower" d="M150 40 L290 40 L300 150 L140 150 Z" />
          <rect className="diagram__fan" x={165} y={26} width={45} height={14} rx={3} />
          <rect className="diagram__fan" x={230} y={26} width={45} height={14} rx={3} />
          <rect className="diagram__basin" x={130} y={150} width={180} height={28} rx={4} />
          <rect className="diagram__water" x={134} y={160} width={172} height={14} rx={2} />
          {/* make-up in (left), blowdown out (right), side-stream loop (below) */}
          <path className="diagram__pipe diagram__pipe--makeup" d="M20 120 L130 160" markerEnd="url(#arrow)" />
          <path className="diagram__pipe diagram__pipe--blowdown" d="M310 165 L420 120" markerEnd="url(#arrow)" />
          <path className="diagram__pipe diagram__pipe--side" d="M220 178 L220 205 L110 205 L110 175 L130 172" markerEnd="url(#arrow)" />
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0 0 L10 5 L0 10 Z" fill="currentColor" />
            </marker>
          </defs>
          <FlowLabel tile={named.makeup} x={2} y={62} />
          <FlowLabel tile={named.blowdown} x={314} y={62} />
          <FlowLabel tile={named.sidestream} x={2} y={180} />
        </svg>
        {(widget.tiles ?? []).length > 0 && (
          <table className="summary-table diagram__points">
            <caption>Chemistry measurement points</caption>
            <tbody>
              {(widget.tiles ?? []).map((t) => (
                <tr key={t.key}>
                  <th scope="row">{t.label}</th>
                  <td className={`status-text status-text--${t.status}`}>
                    {t.insufficient_data ? 'n/a' : value(t)} <span className="muted">{t.unit}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Section>
  )
}
