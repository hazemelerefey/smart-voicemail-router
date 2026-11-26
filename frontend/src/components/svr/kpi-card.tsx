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

export function KpiCard({
  title,
  icon: Icon,
  value,
  pill,
  children,
}: {
  title: string
  icon: LucideIcon
  value: ReactNode
  pill: { label: string; tone: KpiTone }
  children?: ReactNode
}) {
  return (
    <Card className='svr-kpi h-full'>
      <CardContent className='flex h-full flex-col gap-2.5 p-5'>
        <div className='flex items-center justify-between gap-2'>
          <span className='truncate text-xs font-semibold uppercase tracking-wide text-muted-foreground'>
            {title}
          </span>
          <Icon className='size-4 shrink-0 text-muted-foreground' />
        </div>
        <div className='text-3xl font-bold leading-none tabular-nums'>{value}</div>
        <div className='pt-0.5'>
          <span
            className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold leading-4 text-white shadow-xs ${PILL_BG[pill.tone]}`}
          >
            {pill.label}
          </span>
        </div>
        <div className='mt-auto pt-1 text-xs text-muted-foreground'>{children}</div>
      </CardContent>
    </Card>
  )
}
