import { Link } from '@tanstack/react-router'
import { AlertTriangle, ArrowUpRight, Bell } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import type { Locale } from '@/lib/i18n'
import type { MonitoringAlert } from '@/lib/types'

interface MonitoringAlertsPopoverProps {
  alerts: MonitoringAlert[]
  locale: Locale
}

function formatAlertCopy(alert: MonitoringAlert, isAr: boolean): {
  title: string
  detail: string
  href: '/review-queue' | '/evaluation'
  action: string
} {
  if (alert.code === 'high_human_review_rate') {
    const pct = `${(alert.value * 100).toFixed(1)}%`
    const target = `${(alert.threshold * 100).toFixed(0)}%`
    return {
      title: isAr ? 'ارتفاع معدل المراجعة البشرية' : 'Elevated Human Review Rate',
      detail: isAr
        ? `معدل آخر 24 ساعة هو ${pct} (الحد المستهدف <= ${target}).`
        : `24h rate is ${pct} against the <= ${target} threshold.`,
      href: '/review-queue',
      action: isAr ? 'فتح قائمة المراجعة' : 'Open Review Queue',
    }
  }
  if (alert.code === 'high_p95_latency') {
    const sec = `${(alert.value / 1000).toFixed(1)}s`
    const targetSec = `${(alert.threshold / 1000).toFixed(0)}s`
    return {
      title: isAr ? 'تجاوز زمن المعالجة المستهدف' : 'Pipeline Latency Above Target',
      detail: isAr
        ? `زمن p95 خلال 24 ساعة هو ${sec} (الحد المستهدف <= ${targetSec}).`
        : `24h p95 end-to-end latency is ${sec} (target <= ${targetSec}).`,
      href: '/evaluation',
      action: isAr ? 'عرض مقاييس الأداء' : 'Inspect Latency',
    }
  }
  return {
    title: isAr ? 'تنبيه تشغيل' : 'Operational Notice',
    detail: alert.message,
    href: '/evaluation',
    action: isAr ? 'عرض التفاصيل' : 'View Details',
  }
}

export function MonitoringAlertsPopover({ alerts, locale }: MonitoringAlertsPopoverProps) {
  if (!alerts.length) return null

  const isAr = locale === 'ar'
  const hasCritical = alerts.some((a) => a.severity === 'critical')

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant='outline'
          className={
            hasCritical
              ? 'border-destructive/40 text-foreground hover:bg-destructive/10'
              : 'border-amber-500/40 text-foreground hover:bg-amber-500/10'
          }
          aria-label={isAr ? `تنبيهات النظام (${alerts.length})` : `System alerts (${alerts.length})`}
        >
          <Bell className={hasCritical ? 'size-4 text-destructive' : 'size-4 text-amber-500'} />
          <span className='hidden sm:inline'>{isAr ? 'التنبيهات' : 'Alerts'}</span>
          <Badge
            variant={hasCritical ? 'destructive' : 'secondary'}
            className='h-5 min-w-5 justify-center px-1.5 font-mono text-[11px] tabular-nums'
          >
            {alerts.length}
          </Badge>
        </Button>
      </PopoverTrigger>
      <PopoverContent align='end' className='w-96 max-w-[calc(100vw-2rem)] p-0'>
        <div className='flex items-center justify-between border-b px-4 py-3'>
          <span className='text-sm font-semibold'>
            {isAr ? 'تنبيهات التشغيل النشطة' : 'Active System Alerts'}
          </span>
          <span className='text-xs text-muted-foreground tabular-nums'>
            {isAr ? `${alerts.length} نشط` : `${alerts.length} active`}
          </span>
        </div>
        <div className='divide-y'>
          {alerts.map((alert) => {
            const copy = formatAlertCopy(alert, isAr)
            const isCrit = alert.severity === 'critical'
            return (
              <div key={alert.code} className='flex items-start gap-3 px-4 py-3'>
                <AlertTriangle
                  className={
                    isCrit
                      ? 'mt-0.5 size-4 shrink-0 text-destructive'
                      : 'mt-0.5 size-4 shrink-0 text-amber-500'
                  }
                />
                <div className='min-w-0 flex-1 space-y-1'>
                  <div className='flex items-center justify-between gap-2'>
                    <p className='text-xs font-semibold leading-none'>{copy.title}</p>
                    <Badge
                      variant={isCrit ? 'destructive' : 'secondary'}
                      className='px-1.5 py-0 text-[10px] uppercase'
                    >
                      {isCrit
                        ? isAr
                          ? 'عاجل'
                          : 'Critical'
                        : isAr
                          ? 'تحذير'
                          : 'Warning'}
                    </Badge>
                  </div>
                  <p className='text-xs leading-relaxed text-muted-foreground'>{copy.detail}</p>
                  <Link
                    to={copy.href}
                    className='inline-flex items-center gap-1 pt-0.5 text-xs font-medium text-blue-600 hover:underline dark:text-sky-400'
                  >
                    <span>{copy.action}</span>
                    <ArrowUpRight className='size-3' />
                  </Link>
                </div>
              </div>
            )
          })}
        </div>
      </PopoverContent>
    </Popover>
  )
}
