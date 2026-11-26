import { useEffect, useState } from 'react'
import { Clock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { Locale } from '@/lib/i18n'

const SLA_MINUTES: Record<string, number> = {
  urgent: 15,
  high: 60,
  normal: 240,
  low: 1440,
}

function formatDurationMinutes(absMins: number, locale: Locale): string {
  if (absMins < 60) {
    return locale === 'ar' ? `${absMins} د` : `${absMins}m`
  }
  const hours = Math.floor(absMins / 60)
  const mins = absMins % 60
  if (mins === 0) {
    return locale === 'ar' ? `${hours} س` : `${hours}h`
  }
  return locale === 'ar' ? `${hours} س ${mins} د` : `${hours}h ${mins}m`
}

export function SlaCountdownBadge({
  createdAt,
  priority,
  status,
  locale,
}: {
  createdAt: string
  priority: string | null | undefined
  status: string
  locale: Locale
}) {
  const [nowMs, setNowMs] = useState(() => Date.now())

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 30_000)
    return () => window.clearInterval(id)
  }, [])

  if (status === 'resolved' || status === 'closed') {
    return (
      <Badge variant='outline' className='gap-1 text-[11px] font-normal text-muted-foreground'>
        <Clock className='size-3' />
        <span>{locale === 'ar' ? 'تم ضمن المهلة' : 'SLA Met'}</span>
      </Badge>
    )
  }

  const targetMins = SLA_MINUTES[(priority ?? 'normal').toLowerCase()] ?? 240
  const createdMs = Date.parse(createdAt)
  if (!Number.isFinite(createdMs)) return null

  const deadlineMs = createdMs + targetMins * 60_000
  const diffMins = Math.round((deadlineMs - nowMs) / 60_000)

  if (diffMins <= 0) {
    const overdue = Math.abs(diffMins)
    return (
      <Badge variant='destructive' className='gap-1 font-mono text-[11px]'>
        <Clock className='size-3' />
        <span>
          {locale === 'ar'
            ? `تجاوز +${formatDurationMinutes(overdue, locale)}`
            : `Breached +${formatDurationMinutes(overdue, locale)}`}
        </span>
      </Badge>
    )
  }

  const nearBreach = diffMins <= Math.max(5, Math.round(targetMins * 0.25))
  if (nearBreach) {
    return (
      <Badge
        variant='outline'
        className='gap-1 border-amber-500/50 bg-amber-500/10 font-mono text-[11px] text-amber-700 dark:text-amber-400'
      >
        <Clock className='size-3' />
        <span>
          {locale === 'ar'
            ? `متبقي ${formatDurationMinutes(diffMins, locale)}`
            : `${formatDurationMinutes(diffMins, locale)} left`}
        </span>
      </Badge>
    )
  }

  return (
    <Badge variant='outline' className='gap-1 font-mono text-[11px] font-normal text-muted-foreground'>
      <Clock className='size-3' />
      <span>
        {locale === 'ar'
          ? `متبقي ${formatDurationMinutes(diffMins, locale)}`
          : `${formatDurationMinutes(diffMins, locale)} left`}
      </span>
    </Badge>
  )
}
