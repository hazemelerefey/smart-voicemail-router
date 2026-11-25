import { useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface SvrCrosshairChartProps {
  xLabels: string[]
  yDomain: [number, number]
  formatY?: (val: number) => string
  className?: string
  children: React.ReactNode
}

interface CursorState {
  x: number
  y: number
  plotLeft: number
  plotTop: number
  plotWidth: number
  plotHeight: number
  xLabel: string
  yLabel: string
}

/**
 * Wraps a Recharts BarChart with an architectural X/Y dashed crosshair and live
 * axis coordinate pills without triggering Recharts state re-renders.
 */
export function SvrCrosshairChart({
  xLabels,
  yDomain,
  formatY,
  className,
  children,
}: SvrCrosshairChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [cursor, setCursor] = useState<CursorState | null>(null)

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const container = containerRef.current
    if (!container) return
    const gridEl = container.querySelector('.recharts-cartesian-grid')
    if (!gridEl) {
      setCursor(null)
      return
    }
    const containerRect = container.getBoundingClientRect()
    const gridRect = gridEl.getBoundingClientRect()
    if (
      gridRect.width <= 0 ||
      gridRect.height <= 0 ||
      e.clientX < gridRect.left ||
      e.clientX > gridRect.right ||
      e.clientY < gridRect.top ||
      e.clientY > gridRect.bottom
    ) {
      setCursor(null)
      return
    }

    const plotLeft = gridRect.left - containerRect.left
    const plotTop = gridRect.top - containerRect.top
    const plotWidth = gridRect.width
    const plotHeight = gridRect.height
    const x = e.clientX - containerRect.left
    const y = e.clientY - containerRect.top

    const yRatio = Math.min(1, Math.max(0, (y - plotTop) / plotHeight))
    const yVal = yDomain[1] - yRatio * (yDomain[1] - yDomain[0])
    const yLabel = formatY ? formatY(yVal) : yVal.toFixed(1)

    const xRatio = Math.min(0.999999, Math.max(0, (x - plotLeft) / plotWidth))
    const xLabel = xLabels.length > 0 ? xLabels[Math.floor(xRatio * xLabels.length)] : ''

    setCursor({ x, y, plotLeft, plotTop, plotWidth, plotHeight, xLabel, yLabel })
  }

  return (
    <div
      ref={containerRef}
      className={cn('svr-chart relative select-none', className)}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => setCursor(null)}
    >
      {children}
      {cursor && (
        <div className='pointer-events-none absolute inset-0 z-20'>
          <svg className='h-full w-full overflow-visible'>
            <line
              x1={cursor.x}
              y1={cursor.plotTop}
              x2={cursor.x}
              y2={cursor.plotTop + cursor.plotHeight}
              stroke='var(--chart-crosshair)'
              strokeWidth={1}
              strokeDasharray='2 3'
            />
            <line
              x1={cursor.plotLeft}
              y1={cursor.y}
              x2={cursor.plotLeft + cursor.plotWidth}
              y2={cursor.y}
              stroke='var(--chart-crosshair)'
              strokeWidth={1}
              strokeDasharray='2 3'
            />
          </svg>
          {cursor.xLabel && (
            <div
              className='pointer-events-none absolute z-30 -translate-x-1/2 whitespace-nowrap rounded-[2px] bg-[var(--chart-pill-bg)] px-2 py-0.5 text-[11px] font-semibold leading-tight tracking-tight text-[var(--chart-pill-fg)] shadow-sm'
              style={{ left: cursor.x, top: cursor.plotTop + cursor.plotHeight + 4 }}
            >
              <span
                className='absolute -top-1 left-1/2 -translate-x-1/2 border-x-4 border-b-4 border-x-transparent'
                style={{ borderBottomColor: 'var(--chart-pill-bg)' }}
              />
              {cursor.xLabel}
            </div>
          )}
          <div
            className='pointer-events-none absolute z-30 -translate-x-full -translate-y-1/2 whitespace-nowrap rounded-[2px] bg-[var(--chart-pill-bg)] px-1.5 py-0.5 font-mono text-[11px] font-semibold leading-tight tabular-nums text-[var(--chart-pill-fg)] shadow-sm'
            style={{ left: Math.max(36, cursor.plotLeft - 4), top: cursor.y }}
          >
            {cursor.yLabel}
          </div>
        </div>
      )}
    </div>
  )
}
