import { cn } from '@/lib/utils'

export interface ChartTooltipRow {
  title: string
  value: string
  caption: string
  tone?: 'default' | 'positive' | 'negative'
}

interface SvrChartTooltipProps {
  active?: boolean
  payload?: ReadonlyArray<{ payload?: unknown }>
  format: (row: unknown) => ChartTooltipRow
}

/**
 * Thin, sharp, high-contrast chart tooltip: hairline border, 2px corners,
 * crisp two-line layout with strong semantic contrast.
 */
export function SvrChartTooltip({ active, payload, format }: SvrChartTooltipProps) {
  if (!active || !payload?.length) return null
  const raw = payload[0]?.payload
  if (!raw) return null
  const row = format(raw)
  return (
    <div className='rounded-[2px] border border-foreground/20 bg-popover px-3 py-1.5 text-xs leading-snug whitespace-nowrap text-popover-foreground antialiased'>
      <p className='font-semibold tracking-tight text-foreground'>{row.title}</p>
      <p className='mt-0.5 flex items-center gap-1.5 tabular-nums'>
        <strong className='font-mono font-bold text-foreground'>{row.value}</strong>
        <span className='text-foreground/35'>|</span>
        <span
          className={cn(
            'font-semibold',
            row.tone === 'positive' && 'text-[color:var(--success)]',
            row.tone === 'negative' && 'text-destructive',
            (!row.tone || row.tone === 'default') && 'text-foreground/85'
          )}
        >
          {row.caption}
        </span>
      </p>
    </div>
  )
}
