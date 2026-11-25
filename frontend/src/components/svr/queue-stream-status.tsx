import { Link } from '@tanstack/react-router'
import { ArrowUpRight, RefreshCw, Trash2 } from 'lucide-react'
import { useSvr, type WsFeedItem, type WsStatus } from '@/context/svr-provider'
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

function describeFeedItem(item: WsFeedItem, isAr: boolean): {
  title: string
  subtitle: string
  to: '/tickets/$id' | '/admin/settings' | '/dashboard'
  ticketId?: string
} {
  const ev = item.event
  if (ev.type === 'settings_updated' || ev.type === 'settings.updated') {
    return {
      title: isAr ? 'تم تحديث إعدادات التوجيه' : 'Routing settings updated',
      subtitle: isAr ? 'تطبق الحدود الجديدة على التذاكر الواردة' : 'Updated configuration active',
      to: '/admin/settings',
    }
  }
  const shortId = ev.ticket_id ? `#${ev.ticket_id.slice(0, 8)}` : ''
  const title =
    ev.type === 'ticket_stage_update'
      ? isAr
        ? `تحديث مرحلة المعالجة ${shortId}`
        : `Pipeline stage ${shortId}`
      : isAr
        ? `تحديث التذكرة ${shortId}`
        : `Ticket updated ${shortId}`
  const parts: string[] = []
  if (typeof ev.stage === 'string' && ev.stage) parts.push(ev.stage)
  if (typeof ev.status === 'string' && ev.status) parts.push(ev.status)
  if (typeof ev.queue_priority === 'string' && ev.queue_priority) parts.push(ev.queue_priority)
  const subtitle = parts.length > 0 ? parts.join(' · ') : ev.type

  if (ev.ticket_id) {
    return { title, subtitle, to: '/tickets/$id', ticketId: ev.ticket_id }
  }
  return { title, subtitle, to: '/dashboard' }
}

/**
 * Interactive WebSocket stream status button + real-time Live Activity Feed popover.
 * Displays live operational events from /ws/queue (ticket stages, routing updates, settings).
 */
export function QueueStreamStatus() {
  const {
    locale,
    wsStatus,
    wsConnectedAt,
    wsFeed,
    wsUnreadCount,
    markWsFeedRead,
    clearWsFeed,
    reconnectWs,
  } = useSvr()
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

  return (
    <Popover
      onOpenChange={(open) => {
        if (open) markWsFeedRead()
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant='outline'
          size='sm'
          className='hidden h-8 gap-2 px-2.5 text-xs font-medium md:inline-flex'
          aria-label={isAr ? `البث المباشر: ${statusText}` : `Live queue stream: ${statusText}`}
        >
          <SignalBars status={wsStatus} />
          <span
            className={cn(
              'font-medium',
              wsStatus === 'connected' && 'text-blue-600 dark:text-sky-400',
              (wsStatus === 'reconnecting' || wsStatus === 'connecting') && 'text-amber-600 dark:text-amber-400',
              wsStatus === 'offline' && 'text-muted-foreground'
            )}
          >
            {statusText}
          </span>
          {wsUnreadCount > 0 && (
            <Badge
              variant='secondary'
              className='h-4 min-w-4 justify-center px-1 font-mono text-[10px] font-semibold tabular-nums text-blue-600 dark:text-sky-400'
            >
              {wsUnreadCount}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>

      <PopoverContent align='end' className='w-96 max-w-[calc(100vw-2rem)] p-0'>
        <div className='flex items-center justify-between border-b px-4 py-3'>
          <div className='flex items-center gap-2'>
            <SignalBars status={wsStatus} />
            <span className='text-xs font-semibold'>
              {isAr ? 'النشاط المباشر' : 'Live Activity'}
            </span>
          </div>
          <div className='flex items-center gap-2'>
            {wsConnectedAt && (
              <span className='font-mono text-[11px] tabular-nums text-muted-foreground'>
                {formatClock(wsConnectedAt, locale)}
              </span>
            )}
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
        </div>

        <div className='max-h-72 overflow-y-auto'>
          {wsFeed.length === 0 ? (
            <div className='px-4 py-6 text-center'>
              <p className='text-xs font-medium text-foreground'>
                {isAr ? 'في انتظار التحديثات المباشرة' : 'Listening for live events'}
              </p>
              <p className='mt-1 text-[11px] text-muted-foreground'>
                {isAr
                  ? 'ستظهر هنا تحديثات الرسائل الصوتية والتوجيه والإعدادات فور حدوثها.'
                  : 'New voicemails, pipeline stages, and routing updates appear here in real time.'}
              </p>
            </div>
          ) : (
            <div className='divide-y'>
              {wsFeed.map((item) => {
                const info = describeFeedItem(item, isAr)
                const content = (
                  <div className='flex items-start justify-between gap-3 px-4 py-2.5 transition-colors hover:bg-muted/50'>
                    <div className='min-w-0 flex-1'>
                      <p className='truncate text-xs font-semibold text-foreground'>{info.title}</p>
                      <p className='mt-0.5 truncate font-mono text-[11px] text-muted-foreground'>
                        {info.subtitle}
                      </p>
                    </div>
                    <div className='flex shrink-0 items-center gap-1.5'>
                      <span className='font-mono text-[10px] tabular-nums text-muted-foreground'>
                        {formatClock(item.receivedAt, locale)}
                      </span>
                      <ArrowUpRight className='size-3 text-muted-foreground' />
                    </div>
                  </div>
                )
                return info.to === '/tickets/$id' && info.ticketId ? (
                  <Link key={item.id} to='/tickets/$id' params={{ id: info.ticketId }} className='block'>
                    {content}
                  </Link>
                ) : (
                  <Link key={item.id} to={info.to === '/tickets/$id' ? '/dashboard' : info.to} className='block'>
                    {content}
                  </Link>
                )
              })}
            </div>
          )}
        </div>

        <div className='flex items-center justify-between border-t px-4 py-2.5'>
          <span className='font-mono text-[11px] text-muted-foreground'>/ws/queue</span>
          <div className='flex items-center gap-1.5'>
            {wsFeed.length > 0 && (
              <Button
                type='button'
                variant='ghost'
                size='sm'
                className='h-7 gap-1 px-2 text-xs text-muted-foreground'
                onClick={clearWsFeed}
              >
                <Trash2 className='size-3' />
                <span>{isAr ? 'مسح' : 'Clear'}</span>
              </Button>
            )}
            <Button
              type='button'
              variant='outline'
              size='sm'
              className='h-7 gap-1.5 px-2.5 text-xs'
              onClick={reconnectWs}
            >
              <RefreshCw className='size-3' />
              <span>{isAr ? 'إعادة اتصال' : 'Reconnect'}</span>
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  )
}
