import { RefreshCw } from 'lucide-react'
import { useSvr, type WsStatus } from '@/context/svr-provider'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { cn } from '@/lib/utils'

function formatClock(iso: string | null, locale: 'en' | 'ar'): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleTimeString(locale === 'ar' ? 'ar-EG' : 'en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function SignalBars({ status }: { status: WsStatus }) {
  const activeCount = status === 'connected' ? 3 : status === 'connecting' || status === 'reconnecting' ? 2 : 1
  const activeColor =
    status === 'connected'
      ? 'fill-blue-600 dark:fill-sky-400'
      : status === 'connecting' || status === 'reconnecting'
        ? 'fill-amber-600 dark:fill-amber-400'
        : 'fill-muted-foreground'

  return (
    <svg viewBox='0 0 14 12' className='size-3.5 shrink-0' aria-hidden='true'>
      <rect x='1' y='7' width='2.5' height='4' rx='0.5' className={activeCount >= 1 ? activeColor : 'fill-foreground/15'} />
      <rect x='5.5' y='4' width='2.5' height='7' rx='0.5' className={activeCount >= 2 ? activeColor : 'fill-foreground/15'} />
      <rect x='10' y='1' width='2.5' height='10' rx='0.5' className={activeCount >= 3 ? activeColor : 'fill-foreground/15'} />
    </svg>
  )
}

/**
 * Interactive WebSocket stream status button + diagnostics popover in the header.
 * Backed by live /ws/queue connection timestamps, event count, and manual reconnect.
 */
export function QueueStreamStatus() {
  const { locale, wsStatus, wsVersion, lastWsEvent, wsConnectedAt, lastWsEventAt, reconnectWs } = useSvr()
  const isAr = locale === 'ar'

  const statusText =
    wsStatus === 'connected'
      ? isAr
        ? 'متصل'
        : 'Synced'
      : wsStatus === 'reconnecting' || wsStatus === 'connecting'
        ? isAr
          ? 'جاري الاتصال'
          : 'Syncing'
        : isAr
          ? 'غير متصل'
          : 'Offline'

  const pillText =
    wsStatus === 'connected'
      ? wsVersion > 0
        ? `${wsVersion}`
        : statusText
      : statusText

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant='outline'
          size='sm'
          className='hidden h-8 gap-2 px-2.5 text-xs font-medium md:inline-flex'
          aria-label={isAr ? `حالة البث المباشر: ${statusText}` : `Live queue stream: ${statusText}`}
        >
          <SignalBars status={wsStatus} />
          <span className='text-foreground/85'>{isAr ? 'البث' : 'Stream'}</span>
          <span className='text-foreground/25'>|</span>
          <span
            className={cn(
              'font-mono text-[11px] font-semibold tabular-nums',
              wsStatus === 'connected' && 'text-blue-600 dark:text-sky-400',
              (wsStatus === 'reconnecting' || wsStatus === 'connecting') && 'text-amber-600 dark:text-amber-400',
              wsStatus === 'offline' && 'text-muted-foreground'
            )}
          >
            {pillText}
          </span>
        </Button>
      </PopoverTrigger>
      <PopoverContent align='end' className='w-80 max-w-[calc(100vw-2rem)] p-0'>
        <div className='flex items-center justify-between border-b px-4 py-3'>
          <div className='flex items-center gap-2'>
            <SignalBars status={wsStatus} />
            <span className='text-xs font-semibold'>
              {isAr ? 'بث قائمة الانتظار المباشر' : 'Real-Time Queue Stream'}
            </span>
          </div>
          <Badge
            variant={wsStatus === 'connected' ? 'secondary' : 'outline'}
            className={cn(
              'px-1.5 py-0 text-[10px] font-semibold uppercase',
              wsStatus === 'connected' && 'text-blue-600 dark:text-sky-400',
              (wsStatus === 'reconnecting' || wsStatus === 'connecting') && 'text-amber-600 dark:text-amber-400',
              wsStatus === 'offline' && 'text-muted-foreground'
            )}
          >
            {statusText}
          </Badge>
        </div>

        <div className='grid grid-cols-2 gap-x-4 gap-y-2.5 px-4 py-3 text-xs'>
          <div>
            <p className='text-[10px] font-semibold uppercase tracking-wider text-muted-foreground'>
              {isAr ? 'القناة' : 'Channel'}
            </p>
            <p className='mt-0.5 font-mono text-foreground'>/ws/queue</p>
          </div>
          <div>
            <p className='text-[10px] font-semibold uppercase tracking-wider text-muted-foreground'>
              {isAr ? 'الأحداث المستلمة' : 'Events'}
            </p>
            <p className='mt-0.5 font-mono font-semibold tabular-nums text-foreground'>{wsVersion}</p>
          </div>
          <div>
            <p className='text-[10px] font-semibold uppercase tracking-wider text-muted-foreground'>
              {isAr ? 'وقت الاتصال' : 'Connected At'}
            </p>
            <p className='mt-0.5 font-mono tabular-nums text-foreground'>{formatClock(wsConnectedAt, locale)}</p>
          </div>
          <div>
            <p className='text-[10px] font-semibold uppercase tracking-wider text-muted-foreground'>
              {isAr ? 'آخر حدث' : 'Last Event'}
            </p>
            <p className='mt-0.5 truncate font-mono text-foreground' title={lastWsEvent?.type ?? '-'}>
              {lastWsEvent?.type ?? (wsStatus === 'connected' ? 'queue_snapshot' : '-')}
            </p>
            <p className='font-mono text-[10px] tabular-nums text-muted-foreground'>
              {formatClock(lastWsEventAt, locale)}
            </p>
          </div>
        </div>

        <div className='flex items-center justify-between border-t px-4 py-2.5'>
          <span className='text-[11px] text-muted-foreground'>
            {isAr ? 'تحديث تلقائي عبر WebSocket' : 'Auto-sync via WebSocket'}
          </span>
          <Button type='button' variant='outline' size='sm' className='h-7 gap-1.5 px-2.5 text-xs' onClick={reconnectWs}>
            <RefreshCw className='size-3' />
            <span>{isAr ? 'إعادة اتصال' : 'Reconnect'}</span>
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
