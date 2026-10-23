import { useMemo, useState } from 'react'
import type { PointerEvent } from 'react'
import type { Series } from '../api/types'
import { useElementWidth } from '../hooks/useElementWidth'
import { describeSeries, layoutSeries, slotAtX, slotStartIso } from '../lib/chart'
import { formatDateTime, formatDecimal, formatInteger, formatPercent } from '../lib/format'

const DEFAULT_WIDTH = 720

export function PresenceChart({ series }: { series: Series }) {
  const [containerRef, measuredWidth] = useElementWidth<HTMLDivElement>()
  const [hovered, setHovered] = useState<number | null>(null)

  const width = measuredWidth > 0 ? measuredWidth : DEFAULT_WIDTH
  const height = width < 520 ? 240 : 300
  const layout = useMemo(() => layoutSeries(series, { width, height }), [series, width, height])
  const { plot } = layout

  const handleMove = (event: PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect()
    setHovered(slotAtX(layout, event.clientX - rect.left))
  }

  const hoveredBar =
    hovered === null ? undefined : layout.bars.find((bar) => bar.index === hovered)
  const cursorX =
    hovered === null
      ? null
      : Math.min(
          plot.left + (((hovered + 0.5) * layout.bucketMs) / layout.spanMs) * plot.width,
          plot.left + plot.width,
        )

  return (
    <div ref={containerRef} className="chart">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-labelledby="chart-title chart-desc"
        onPointerMove={handleMove}
        onPointerLeave={() => setHovered(null)}
      >
        <title id="chart-title">Presença de pombos ao longo do tempo</title>
        <desc id="chart-desc">{describeSeries(series, layout)}</desc>
        <defs>
          <pattern
            id="chart-gap-hatch"
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <line className="chart__hatch-line" x1="0" y1="0" x2="0" y2="6" />
          </pattern>
        </defs>

        {layout.yTicks.map((tick) => (
          <g key={tick.value}>
            <line
              className="chart__grid"
              x1={plot.left}
              x2={plot.left + plot.width}
              y1={tick.y}
              y2={tick.y}
            />
            <text
              className="chart__axis-label"
              x={plot.left - 8}
              y={tick.y}
              textAnchor="end"
              dominantBaseline="middle"
            >
              {tick.label}
            </text>
          </g>
        ))}

        {layout.gaps.map((gap) => (
          <rect
            key={`gap-${gap.startIndex}`}
            className="chart__gap"
            x={gap.x}
            y={plot.top}
            width={gap.width}
            height={plot.height}
          />
        ))}

        {layout.bars.map((bar) => (
          <g key={bar.index}>
            <rect
              className={bar.index === hovered ? 'chart__bar chart__bar--active' : 'chart__bar'}
              x={bar.x}
              y={bar.yMean}
              width={bar.width}
              height={Math.max(0, plot.top + plot.height - bar.yMean)}
              rx={Math.min(3, bar.width / 2)}
            />
            <line
              className="chart__whisker"
              x1={bar.x + bar.width / 2}
              x2={bar.x + bar.width / 2}
              y1={bar.yMean}
              y2={bar.yPeak}
            />
            <line
              className="chart__peak"
              x1={bar.x}
              x2={bar.x + bar.width}
              y1={bar.yPeak}
              y2={bar.yPeak}
            />
          </g>
        ))}

        {cursorX !== null ? (
          <line
            className="chart__cursor"
            x1={cursorX}
            x2={cursorX}
            y1={plot.top}
            y2={plot.top + plot.height}
          />
        ) : null}

        {layout.xTicks.map((tick) => (
          <text
            key={tick.x}
            className="chart__axis-label"
            x={tick.x}
            y={plot.top + plot.height + 20}
            textAnchor={tick.anchor}
          >
            {tick.label}
          </text>
        ))}
      </svg>

      {hovered !== null && cursorX !== null ? (
        <div
          className="chart__tooltip"
          aria-hidden="true"
          style={{ left: Math.min(Math.max(cursorX, 90), width - 90), top: plot.top }}
        >
          <strong>{formatDateTime(slotStartIso(layout, hovered))}</strong>
          {hoveredBar ? (
            <dl>
              <dt>Média</dt>
              <dd>{formatDecimal(hoveredBar.point.mean_pigeons)}</dd>
              <dt>Pico</dt>
              <dd>{formatInteger(hoveredBar.point.max_pigeons)}</dd>
              <dt>Presença</dt>
              <dd>{formatPercent(hoveredBar.point.presence_rate)}</dd>
              <dt>Leituras</dt>
              <dd>{formatInteger(hoveredBar.point.readings)}</dd>
            </dl>
          ) : (
            <span>Sem medição neste intervalo</span>
          )}
        </div>
      ) : null}
    </div>
  )
}
