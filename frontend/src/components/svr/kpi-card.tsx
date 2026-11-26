import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

export type KpiTone = 'red' | 'green' | 'blue' | 'grey' | 'orange'

const PILL_BG: Record<KpiTone, string> = {
  red: 'bg-[#FF1744]',
  green: 'bg-[#00C853]',
  blue: 'bg-[#2979FF]',
  orange: 'bg-[#EF6C00]',
  grey: 'bg-[#616161]',
}

const ICON_CHIP: Record<KpiTone, string> = {
  red: 'border-[#FF1744]/25 bg-[#FF1744]/10 text-[#FF1744] dark:border-[#FF1744]/35 dark:bg-[#FF1744]/15 dark:text-[#FF5252]',
  green: 'border-[#00C853]/25 bg-[#00C853]/10 text-[#00A844] dark:border-[#00C853]/35 dark:bg-[#00C853]/15 dark:text-[#00E676]',
  blue: 'border-[#2979FF]/25 bg-[#2979FF]/10 text-[#2979FF] dark:border-[#2979FF]/35 dark:bg-[#2979FF]/15 dark:text-[#448AFF]',
  orange: 'border-[#EF6C00]/25 bg-[#EF6C00]/10 text-[#EF6C00] dark:border-[#EF6C00]/35 dark:bg-[#EF6C00]/15 dark:text-[#FF9100]',
  grey: 'border-border bg-muted text-muted-foreground',
}

export function KpiCard({
  title,
  icon: Icon,
  iconTone,
  value,
  valueClassName = '',
  pill,
  pillMeta,
  children,
}: {
  title: string
  icon: LucideIcon
  iconTone: KpiTone
  value: ReactNode
  valueClassName?: string
  pill: { label: string; tone: KpiTone }
  pillMeta?: ReactNode
  children?: ReactNode
}) {
  return (
    <Card className='svr-kpi h-full'>
      <CardContent className='flex h-full flex-col gap-2.5 p-5'>
        <div className='flex items-center justify-between gap-2'>
          <span className='truncate text-xs font-semibold uppercase tracking-wide text-muted-foreground'>
            {title}
          </span>
          <span
            className={`flex size-8 shrink-0 items-center justify-center rounded-lg border ${ICON_CHIP[iconTone]}`}
          >
            <Icon className='size-4' />
          </span>
        </div>
        <div className={`text-3xl font-bold leading-none tabular-nums ${valueClassName}`}>{value}</div>
        <div className='flex flex-wrap items-center gap-2 pt-0.5'>
          <span
            className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold leading-4 text-white shadow-xs ${PILL_BG[pill.tone]}`}
          >
            {pill.label}
          </span>
          {pillMeta && <span className='text-xs text-muted-foreground'>{pillMeta}</span>}
        </div>
        <div className='mt-auto pt-1 text-xs text-muted-foreground'>{children}</div>
      </CardContent>
    </Card>
  )
}
