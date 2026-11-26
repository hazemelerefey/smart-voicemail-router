import { useEffect, useState } from 'react'
import { Clock } from 'lucide-react'
import type { Locale } from '@/lib/i18n'

const SLA_MINUTES: Record<string, number> = {
  urgent: 15,
  high: 60,
  normal: 240,
  low: 1440,
}

const SLA_PILL_BASE =
  'inline-flex w-fit shrink-0 items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-semibold leading-4 tabular-nums shadow-xs'

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
      <span className={`${SLA_PILL_BASE} border border-border bg-muted/60 font-sans font-medium text-muted-foreground`}>
        <Clock className='size-3 shrink-0' />
        <span>{locale === 'ar' ? 'تم ضمن المهلة' : 'SLA Met'}</span>
      </span>
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
      <span className={`${SLA_PILL_BASE} bg-[#FF1744] text-white`}>
        <Clock className='size-3 shrink-0' />
        <span>
          {locale === 'ar'
            ? `تجاوز +${formatDurationMinutes(overdue, locale)}`
            : `Breached +${formatDurationMinutes(overdue, locale)}`}
        </span>
      </span>
    )
  }

  const nearBreach = diffMins <= Math.max(5, Math.round(targetMins * 0.25))
  if (nearBreach) {
    return (
      <span className={`${SLA_PILL_BASE} bg-[#EF6C00] text-white`}>
        <Clock className='size-3 shrink-0' />
        <span>
          {locale === 'ar'
            ? `متبقي ${formatDurationMinutes(diffMins, locale)}`
            : `${formatDurationMinutes(diffMins, locale)} left`}
        </span>
      </span>
    )
  }

  return (
    <span className={`${SLA_PILL_BASE} border border-border bg-muted/50 font-medium text-muted-foreground`}>
      <Clock className='size-3 shrink-0' />
      <span>
        {locale === 'ar'
          ? `متبقي ${formatDurationMinutes(diffMins, locale)}`
          : `${formatDurationMinutes(diffMins, locale)} left`}
      </span>
    </span>
  )
}
