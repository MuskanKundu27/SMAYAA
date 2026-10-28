// The line chart used by trend widgets: smooth lines, a soft fill under the first series, grid
// lines with values, time labels, the good range as a band, and a hover tooltip.

import { useId, useMemo, useRef, useState } from 'react'
import type { PointerEvent } from 'react'

import type { TrendSeries } from '../api/types'
import { formatValue } from '../format'

const SERIES_COLOURS = ['#1f6feb', '#f08c00', '#2f9e44', '#7048e8']

const W = 360
const H = 100 // compact: four charts sit side by side
const TOP = 10
const BOTTOM = 24
const MAX_POINTS = 120 // more points are averaged into buckets so lines stay smooth

type Point = { t: number; v: number }

function downsample(points: Point[]): Point[] {
  if (points.length <= MAX_POINTS) return points
  const size = points.length / MAX_POINTS
  const out: Point[] = []
  for (let i = 0; i < MAX_POINTS; i++) {
    const chunk = points.slice(Math.floor(i * size), Math.floor((i + 1) * size))
    if (chunk.length === 0) continue
    out.push({
      t: chunk.reduce((s, p) => s + p.t, 0) / chunk.length,
      v: chunk.reduce((s, p) => s + p.v, 0) / chunk.length,
    })
  }
  return out
}

/** A smooth path through the points (quadratic curves through midpoints: no overshoot). */
function smoothPath(xy: [number, number][]): string {
  const f = (n: number) => n.toFixed(1)
  if (xy.length < 3) return xy.map(([x, y], i) => `${i ? 'L' : 'M'}${f(x)},${f(y)}`).join(' ')
  let d = `M${f(xy[0][0])},${f(xy[0][1])}`
  for (let i = 1; i < xy.length - 1; i++) {
    const [x, y] = xy[i]
    const [nx, ny] = xy[i + 1]
    d += ` Q${f(x)},${f(y)} ${f((x + nx) / 2)},${f((y + ny) / 2)}`
  }
  const [lx, ly] = xy[xy.length - 1]
  return `${d} L${f(lx)},${f(ly)}`
}

interface Scale {
  y: (v: number) => number
  ticks: number[]
}

function scaleFor(values: number[]): Scale {
  let lo = Math.min(...values)
  let hi = Math.max(...values)
  if (hi === lo) {
    lo -= 1
    hi += 1
  }
  const pad = (hi - lo) * 0.08
  lo -= pad
  hi += pad
  const ticks = [0, 1, 2].map((i) => lo + ((hi - lo) * i) / 2)
  return { y: (v) => TOP + (1 - (v - lo) / (hi - lo)) * (H - TOP - BOTTOM), ticks }
}

function tickText(v: number): string {
  const a = Math.abs(v)
  return formatValue(v, a >= 100 ? 0 : a >= 10 ? 1 : 2)
}

function timeText(t: number, spanHours: number): string {
  const d = new Date(t)
  return spanHours <= 36
    ? d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

function nearest(points: Point[], t: number): Point | null {
  let best: Point | null = null
  for (const p of points) if (!best || Math.abs(p.t - t) < Math.abs(best.t - t)) best = p
  return best
}

/** One or more series: the first on the left axis (with its good range as a band), the
 *  others on the right axis. */
export function LineChart({ series }: { series: TrendSeries[] }) {
  const gradientId = `fill-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const svgRef = useRef<SVGSVGElement>(null)
  const [hoverX, setHoverX] = useState<number | null>(null)
  const lines = useMemo(
    () =>
      series.map((s) => ({
        series: s,
        points: downsample(
          s.points.filter((p) => p.v !== null).map((p) => ({ t: Date.parse(p.t), v: p.v as number })),
        ),
      })),
    [series],
  )

  const all = lines.flatMap((l) => l.points)
  if (all.length < 2) return <p className="muted chart-empty">Not enough history yet.</p>

  const twoAxes = lines.length > 1 && lines.slice(1).some((l) => l.points.length > 0)
  const left = 42
  const right = twoAxes ? 42 : 12
  const plotW = W - left - right
  const t0 = Math.min(...all.map((p) => p.t))
  const t1 = Math.max(...all.map((p) => p.t))
  const spanHours = (t1 - t0) / 3_600_000
  const x = (t: number) => left + (t1 === t0 ? plotW / 2 : ((t - t0) / (t1 - t0)) * plotW)

  const band = series[0].limits
  const leftScale = scaleFor(
    lines[0].points.map((p) => p.v).concat(band ? [band.good_min, band.good_max] : []).concat(
      lines[0].points.length ? [] : [0],
    ),
  )
  const rightScale = twoAxes ? scaleFor(lines.slice(1).flatMap((l) => l.points.map((p) => p.v))) : leftScale
  const scaleOf = (i: number) => (i === 0 ? leftScale : rightScale)
  const bottom = H - BOTTOM

  const hoverT = hoverX === null ? null : t0 + ((hoverX - left) / plotW) * (t1 - t0)
  const hovered = hoverT === null ? [] : lines.map((l) => nearest(l.points, hoverT))

  function onMove(event: PointerEvent<SVGSVGElement>) {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect || rect.width === 0) return
    const sx = ((event.clientX - rect.left) / rect.width) * W
    setHoverX(Math.min(Math.max(sx, left), W - right))
  }

  return (
    <div className="chart">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={series.map((s) => s.label).join(' and ')}
        onPointerMove={onMove}
        onPointerLeave={() => setHoverX(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={SERIES_COLOURS[0]} stopOpacity="0.28" />
            <stop offset="100%" stopColor={SERIES_COLOURS[0]} stopOpacity="0" />
          </linearGradient>
        </defs>

        {leftScale.ticks.map((v) => (
          <g key={`l${v}`}>
            <line className="chart__grid" x1={left} x2={W - right} y1={leftScale.y(v)} y2={leftScale.y(v)} />
            <text className="chart__tick" x={left - 6} y={leftScale.y(v) + 3} textAnchor="end">
              {tickText(v)}
            </text>
          </g>
        ))}
        {twoAxes &&
          rightScale.ticks.map((v) => (
            <text
              key={`r${v}`}
              className="chart__tick"
              x={W - right + 6}
              y={rightScale.y(v) + 3}
              fill={SERIES_COLOURS[1]}
            >
              {tickText(v)}
            </text>
          ))}

        {band && (
          <g>
            <rect
              className="chart__band"
              x={left}
              width={plotW}
              y={leftScale.y(band.good_max)}
              height={Math.max(leftScale.y(band.good_min) - leftScale.y(band.good_max), 1)}
            />
            <line className="chart__band-edge" x1={left} x2={W - right} y1={leftScale.y(band.good_max)} y2={leftScale.y(band.good_max)} />
            <line className="chart__band-edge" x1={left} x2={W - right} y1={leftScale.y(band.good_min)} y2={leftScale.y(band.good_min)} />
          </g>
        )}

        {lines.map((line, i) => {
          if (line.points.length === 0) return null
          const xy = line.points.map((p) => [x(p.t), scaleOf(i).y(p.v)] as [number, number])
          const path = smoothPath(xy)
          const last = xy[xy.length - 1]
          const colour = SERIES_COLOURS[i % SERIES_COLOURS.length]
          return (
            <g key={line.series.key}>
              {i === 0 && (
                <path d={`${path} L${last[0].toFixed(1)},${bottom} L${xy[0][0].toFixed(1)},${bottom} Z`} fill={`url(#${gradientId})`} />
              )}
              <path className="chart__line" d={path} stroke={colour} />
              <circle className="chart__dot" cx={last[0]} cy={last[1]} r={3.2} fill={colour} />
            </g>
          )
        })}

        {[t0, (t0 + t1) / 2, t1].map((t, i) => (
          <text
            key={i}
            className="chart__tick"
            x={x(t)}
            y={H - 6}
            textAnchor={i === 0 ? 'start' : i === 1 ? 'middle' : 'end'}
          >
            {timeText(t, spanHours)}
          </text>
        ))}

        {hoverX !== null && (
          <g>
            <line className="chart__cursor" x1={hoverX} x2={hoverX} y1={TOP} y2={bottom} />
            {hovered.map((p, i) =>
              p ? (
                <circle
                  key={i}
                  className="chart__dot"
                  cx={x(p.t)}
                  cy={scaleOf(i).y(p.v)}
                  r={3.6}
                  fill={SERIES_COLOURS[i % SERIES_COLOURS.length]}
                />
              ) : null,
            )}
          </g>
        )}
      </svg>

      {hoverX !== null && hovered.some(Boolean) && (
        <div className={`chart__tip ${hoverX > W / 2 ? 'chart__tip--left' : ''}`} style={{ left: `${(hoverX / W) * 100}%` }}>
          <div className="chart__tip-time">{new Date(hovered.find(Boolean)!.t).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</div>
          {hovered.map((p, i) =>
            p ? (
              <div key={lines[i].series.key} className="chart__tip-row">
                <span className="chart__swatch" style={{ background: SERIES_COLOURS[i % SERIES_COLOURS.length] }} />
                {lines[i].series.label}: <strong>{formatValue(p.v)}</strong> {lines[i].series.unit}
              </div>
            ) : null,
          )}
        </div>
      )}

      <ul className="chart__legend">
        {lines.map((line, i) => {
          // The newest stored value, not a smoothed bucket.
          const raw = line.series.points.filter((p) => p.v !== null)
          const latest = raw.length ? { v: raw[raw.length - 1].v as number } : null
          return (
            <li key={line.series.key}>
              <span className="chart__swatch" style={{ background: SERIES_COLOURS[i % SERIES_COLOURS.length] }} />
              {line.series.label}
              {latest && (
                <strong>
                  {' '}
                  {formatValue(latest.v)}
                  {line.series.unit && <span className="muted"> {line.series.unit}</span>}
                </strong>
              )}
            </li>
          )
        })}
        {band && (
          <li className="muted">
            <span className="chart__swatch chart__swatch--band" />
            Good range
          </li>
        )}
      </ul>
    </div>
  )
}
