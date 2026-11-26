import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

export type KpiTone = 'red' | 'green' | 'blue' | 'grey' | 'orange'

const TONE_BG: Record<KpiTone, string> = {
  red: 'bg-[#FF1744]',
  green: 'bg-[#00C853]',
  blue: 'bg-[#2979FF]',
  orange: 'bg-[#EF6C00]',
  grey: 'bg-[#616161]',
}

export function KpiCard({
  title,
  icon: Icon,
  iconTone,
  value,
  valueClassName = '',
  pill,
  children,
}: {
  title: string
  icon: LucideIcon
  iconTone: KpiTone
  value: ReactNode
  valueClassName?: string
  pill: { label: string; tone: KpiTone }
  children?: ReactNode
}) {
  return (
    <Card className={`svr-kpi h-full ${iconTone === 'red' && pill.tone === 'red' ? 'svr-kpi-urgent' : ''}`}>
      <CardContent className='flex h-full flex-col gap-3 p-5'>
        <div className='flex items-center justify-between gap-2'>
          <span className='truncate text-xs font-semibold uppercase tracking-wide text-muted-foreground'>
            {title}
          </span>
          <span className={`svr-kpi-icon flex size-8 shrink-0 items-center justify-center rounded-lg text-white shadow-sm ${TONE_BG[iconTone]}`}>
            <Icon className='size-4' />
          </span>
        </div>
        <div className={`text-3xl font-bold leading-none tabular-nums ${valueClassName}`}>{value}</div>
        <div className='mt-auto flex flex-col items-start gap-2'>
          <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold leading-4 text-white shadow-sm ${TONE_BG[pill.tone]}`}>
            {pill.label}
          </span>
          <div className='text-xs text-muted-foreground'>{children}</div>
        </div>
      </CardContent>
    </Card>
  )
}
