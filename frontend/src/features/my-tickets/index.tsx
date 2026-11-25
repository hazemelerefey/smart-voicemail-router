import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { AlertCircle, CheckCircle2, PhoneCall, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Main } from '@/components/layout/main'
import { BucketText, PriorityScoreAvatar, TicketStatusText } from '@/components/svr/status-badges'
import { api, ApiError } from '@/lib/api'
import { UI_COPY, labelForCategory } from '@/lib/i18n'
import { formatDuration, formatPct, formatUtcTimestamp } from '@/lib/taxonomy'
import type { TicketSummary } from '@/lib/types'

export function MyTicketsPage() {
  const { user, locale, wsVersion } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [tickets, setTickets] = useState<TicketSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const res = await api.listTickets({ limit: 50 })
      setTickets(res.items)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load your assigned tickets.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (wsVersion > 0) void load()
  }, [wsVersion, load])

  const updateStatus = async (ticketId: string, status: string) => {
    setBusyId(ticketId)
    try {
      await api.patchTicket(ticketId, { status })
      toast.success(L(`Ticket updated to ${status}.`, 'تم تحديث حالة التذكرة.'))
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to update status.')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('My Assigned Callbacks', 'تذاكر معاودة الاتصال الخاصة بي')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {user?.full_name} · {L('Prioritized urgent-first', 'مرتبة حسب الأولوية (العاجل أولا)')}
          </p>
        </div>
        <Button variant='outline' onClick={() => void load()} disabled={loading}>
          <RefreshCw className='size-4' />
          <span>{L('Refresh', 'تحديث')}</span>
        </Button>
      </div>

      {error && (
        <Alert variant='destructive' className='mb-4'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      ) : tickets.length === 0 ? (
        <Card>
          <CardContent className='py-12 text-center text-sm text-muted-foreground'>
            {L('No callback tickets are currently assigned to you.', 'لا توجد تذاكر مخصصة لك حاليا.')}
          </CardContent>
        </Card>
      ) : (
        <div className='space-y-3'>
          {tickets.map((ticket) => (
            <Card key={ticket.id}>
              <CardHeader className='pb-3'>
                <div className='flex flex-wrap items-start justify-between gap-3'>
                  <div className='flex items-start gap-3'>
                    <PriorityScoreAvatar score={ticket.priority_score} bucket={ticket.queue_priority} size='md' />
                    <div>
                      <CardTitle className='flex flex-wrap items-center gap-2 text-base'>
                        <Link
                          to='/tickets/$id'
                          params={{ id: ticket.id }}
                          className='hover:underline'
                        >
                          {labelForCategory(ticket.complaint_category, locale)}
                        </Link>
                        <span className='font-mono text-xs text-muted-foreground'>
                          #{ticket.id.slice(0, 8)}
                        </span>
                      </CardTitle>
                      <CardDescription className='mt-1'>
                        {L('Confidence', 'الثقة')}:{' '}
                        <span className='tabular-nums'>{formatPct(ticket.confidence)}</span> ·{' '}
                        {formatDuration(ticket.duration_seconds)} ·{' '}
                        {formatUtcTimestamp(ticket.created_at, locale)}
                      </CardDescription>
                    </div>
                  </div>
                  <div className='flex items-center gap-3'>
                    <TicketStatusText status={ticket.status} locale={locale} />
                    <BucketText bucket={ticket.queue_priority} locale={locale} />
                  </div>
                </div>
              </CardHeader>
              <CardContent className='space-y-3'>
                <p className='text-sm' dir='auto'>
                  {ticket.summary || ticket.customer_request || '-'}
                </p>
                <div className='flex flex-wrap items-center gap-2 border-t pt-3'>
                  {ticket.status === 'ready' && (
                    <Button
                      size='sm'
                      disabled={busyId === ticket.id}
                      onClick={() => void updateStatus(ticket.id, 'in_progress')}
                    >
                      <PhoneCall className='size-4' />
                      {L('Start Callback', 'بدء معاودة الاتصال')}
                    </Button>
                  )}
                  {(ticket.status === 'ready' || ticket.status === 'in_progress') && (
                    <Button
                      size='sm'
                      variant='outline'
                      disabled={busyId === ticket.id}
                      onClick={() => void updateStatus(ticket.id, 'resolved')}
                    >
                      <CheckCircle2 className='size-4' />
                      {L('Mark Resolved', 'تم الحل')}
                    </Button>
                  )}
                  <Button size='sm' variant='ghost' asChild>
                    <Link to='/tickets/$id' params={{ id: ticket.id }}>
                      {L('Open Brief & Audio', 'عرض الملخص والصوت')}
                    </Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </Main>
  )
}
