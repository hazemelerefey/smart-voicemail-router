import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import { AlertCircle, AlertTriangle, CheckCircle2, RefreshCw, UserCheck } from 'lucide-react'
import { toast } from 'sonner'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Main } from '@/components/layout/main'
import { BucketText, PriorityScoreAvatar, TicketStatusText } from '@/components/svr/status-badges'
import { api, ApiError } from '@/lib/api'
import { UI_COPY, formatTicketSummary, labelForCategory, labelForReviewReason } from '@/lib/i18n'
import { formatPct, formatUtcTimestamp } from '@/lib/taxonomy'
import type { AgentResponse, TicketSummary } from '@/lib/types'

const REVIEW_REASONS = [
  'low_confidence',
  'null_field',
  'unsupported_label',
  'no_eligible_agent',
  'auto_routing_disabled',
  'processing_error',
  'weekly_quality_sample',
]

export function ReviewQueuePage() {
  const { locale, wsVersion, refreshReviewBadge } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [items, setItems] = useState<TicketSummary[]>([])
  const [agents, setAgents] = useState<AgentResponse[]>([])
  const [reasonFilter, setReasonFilter] = useState<string>('all')
  const [selectedAgent, setSelectedAgent] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [ticketRes, agentRes] = await Promise.all([
        api.listTickets({
          needs_human_review: true,
          review_reason: reasonFilter === 'all' ? undefined : reasonFilter,
          limit: 50,
        }),
        api.listAgents(),
      ])
      setItems(ticketRes.items)
      setAgents(agentRes.filter((a) => a.active))
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load Human Routing Queue.')
    } finally {
      setLoading(false)
    }
  }, [reasonFilter])

  useEffect(() => {
    setLoading(true)
    void load()
  }, [load])

  useEffect(() => {
    if (wsVersion > 0) void load()
  }, [wsVersion, load])

  const handleAssignAndResolve = async (ticket: TicketSummary) => {
    const chosen = selectedAgent[ticket.id] ?? ticket.assigned_agent_id ?? ''
    setBusyId(ticket.id)
    try {
      await api.patchTicket(ticket.id, {
        assigned_agent_id: chosen || undefined,
        needs_human_review: false,
        status: chosen ? 'ready' : undefined,
        note: 'Resolved from Human Routing Queue',
      })
      toast.success(
        L(
          `Ticket #${ticket.id.slice(0, 8)} updated and cleared from review queue.`,
          `تمت مراجعة وتوجيه التذكرة #${ticket.id.slice(0, 8)}.`
        )
      )
      await Promise.all([load(), refreshReviewBadge()])
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Could not update ticket.')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('Human Routing Queue', 'قائمة المراجعة والتوجيه البشري')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Voicemails flagged for low confidence, null/unsupported fields, no eligible agent, processing error, or 5% quality sampling.',
              'الرسائل المحولة بسبب انخفاض الثقة، تعذر التوفر، خطأ المعالجة، أو عينة الجودة الأسبوعية (5%).'
            )}
          </p>
        </div>
        <Button variant='outline' onClick={() => void load()} disabled={loading}>
          <RefreshCw className='size-4' />
          <span>{L('Refresh', 'تحديث')}</span>
        </Button>
      </div>

      <Card className='mb-4'>
        <CardContent className='flex flex-wrap items-center justify-between gap-3 pt-4'>
          <div className='flex items-center gap-3'>
            <Select value={reasonFilter} onValueChange={setReasonFilter}>
              <SelectTrigger className='w-64'>
                <SelectValue placeholder={L('Filter by Review Reason', 'تصفية حسب السبب')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>{t.allOption}</SelectItem>
                {REVIEW_REASONS.map((r) => (
                  <SelectItem key={r} value={r}>
                    {labelForReviewReason(r, locale)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <span className='text-sm text-muted-foreground tabular-nums'>
            {items.length} {L('tickets awaiting human review', 'تذكرة في انتظار المراجعة')}
          </span>
        </CardContent>
      </Card>

      {error && (
        <Alert variant='destructive' className='mb-4'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className='flex flex-col items-center gap-2 py-12 text-center'>
            <CheckCircle2 className='size-8 text-emerald-600' />
            <p className='text-sm font-medium'>
              {L('Human Routing Queue is clear.', 'قائمة المراجعة البشرية فارغة.')}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className='space-y-3'>
          {items.map((ticket) => (
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
                        <span className='inline-flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400'>
                          <AlertTriangle className='size-3.5' />
                          {labelForReviewReason(ticket.review_reason, locale)}
                        </span>
                      </CardTitle>
                      <CardDescription className='mt-1'>
                        <span className='font-mono'>{ticket.file_name}</span> ·{' '}
                        {L('Confidence', 'الثقة')}:{' '}
                        <strong className='tabular-nums'>{formatPct(ticket.confidence)}</strong> /{' '}
                        {formatPct(ticket.confidence_threshold_snapshot, 0)} ·{' '}
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
                  {formatTicketSummary(ticket, locale)}
                </p>
                {ticket.route_reason && ticket.summary && (
                  <p className='text-xs text-muted-foreground'>
                    <strong>{L('Pipeline context:', 'سياق خط المعالجة:')}</strong>{' '}
                    {ticket.route_reason}
                  </p>
                )}

                <div className='flex flex-wrap items-center gap-3 border-t pt-3'>
                  <Select
                    value={selectedAgent[ticket.id] ?? ticket.assigned_agent_id ?? 'none'}
                    onValueChange={(val) =>
                      setSelectedAgent((prev) => ({
                        ...prev,
                        [ticket.id]: val === 'none' ? '' : val,
                      }))
                    }
                  >
                    <SelectTrigger className='w-64'>
                      <SelectValue placeholder={L('Assign Agent', 'تعيين موظف')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value='none'>{t.unassignedOption}</SelectItem>
                      {agents.map((a) => (
                        <SelectItem key={a.id} value={a.id}>
                          {a.name} ({a.current_load}/{a.capacity})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  <Button
                    size='sm'
                    disabled={busyId === ticket.id}
                    onClick={() => void handleAssignAndResolve(ticket)}
                  >
                    <UserCheck className='size-4' />
                    {L('Assign & Clear Review', 'تعيين وإنهاء المراجعة')}
                  </Button>

                  <Button variant='outline' size='sm' asChild>
                    <Link to='/tickets/$id' params={{ id: ticket.id }}>
                      {L('Inspect Evidence', 'فحص التفاصيل')}
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
