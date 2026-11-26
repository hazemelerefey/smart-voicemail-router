import React, { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Download,
  Mic,
  RefreshCw,
  Search,
} from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Main } from '@/components/layout/main'
import { SlaCountdownBadge } from '@/components/svr/sla-badge'
import { BucketText, PriorityScoreAvatar, TicketStatusText } from '@/components/svr/status-badges'
import { VoicemailIntakeSheet } from '@/components/svr/voicemail-intake-sheet'
import { api, ApiError } from '@/lib/api'
import {
  UI_COPY,
  labelForBucket,
  labelForCategory,
  labelForReviewReason,
  labelForStatus,
} from '@/lib/i18n'
import {
  COMPLAINT_CATEGORIES,
  QUEUE_BUCKETS,
  TICKET_STATUSES,
  formatDuration,
  formatPct,
  formatUtcTimestamp,
} from '@/lib/taxonomy'
import type { AgentResponse, TicketListResponse } from '@/lib/types'

export function CallbackQueuePage() {
  const { locale, wsVersion } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [bucket, setBucket] = useState<string>('all')
  const [category, setCategory] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [agentId, setAgentId] = useState<string>('all')
  const [searchInput, setSearchInput] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [cursor, setCursor] = useState<string | null>(null)

  const [data, setData] = useState<TicketListResponse | null>(null)
  const [agents, setAgents] = useState<AgentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [intakeOpen, setIntakeOpen] = useState(false)

  const fetchQueue = useCallback(async () => {
    setError(null)
    try {
      const res = await api.listTickets({
        limit: 20,
        cursor: cursor || undefined,
        bucket: bucket === 'all' ? undefined : bucket,
        category: category === 'all' ? undefined : category,
        status: statusFilter === 'all' ? undefined : statusFilter,
        assigned_agent_id: agentId === 'all' ? undefined : agentId,
        q: searchQuery || undefined,
      })
      setData(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load callback queue.')
    } finally {
      setLoading(false)
    }
  }, [bucket, category, statusFilter, agentId, searchQuery, cursor])

  useEffect(() => {
    setLoading(true)
    void fetchQueue()
  }, [fetchQueue])

  useEffect(() => {
    if (wsVersion > 0) void fetchQueue()
  }, [wsVersion, fetchQueue])

  useEffect(() => {
    api
      .listAgents()
      .then(setAgents)
      .catch((err) => console.warn('Failed to load agents for filter:', err))
  }, [])

  const handleSearchSubmit = (ev: React.FormEvent) => {
    ev.preventDefault()
    setCursor(null)
    setSearchQuery(searchInput.trim())
  }

  const resetFilters = () => {
    setBucket('all')
    setCategory('all')
    setStatusFilter('all')
    setAgentId('all')
    setSearchInput('')
    setSearchQuery('')
    setCursor(null)
  }

  const counts = data?.counts_by_bucket || {}
  const totalAll = Object.values(counts).reduce((a, b) => a + b, 0)
  const hasFilters =
    bucket !== 'all' ||
    category !== 'all' ||
    statusFilter !== 'all' ||
    agentId !== 'all' ||
    Boolean(searchQuery)

  const handleExportCsv = () => {
    const items = data?.items ?? []
    if (items.length === 0) return
    const escapeCell = (val: unknown) => {
      const s = String(val ?? '').replace(/"/g, '""')
      return `"${s}"`
    }
    const headers = [
      'Ticket ID',
      'Priority Score',
      'Queue Bucket',
      'Status',
      'Category',
      'Assigned Agent',
      'Confidence',
      'Created At',
      'Summary',
    ]
    const rows = items.map((tk) => [
      tk.id,
      tk.priority_score ?? '',
      tk.queue_priority ?? '',
      tk.status,
      labelForCategory(tk.complaint_category, locale),
      tk.assigned_agent_name ?? '',
      formatPct(tk.confidence),
      tk.created_at,
      tk.summary || tk.customer_request || tk.route_reason || '',
    ])
    const csv = '\uFEFF' + [headers, ...rows].map((r) => r.map(escapeCell).join(',')).join('\r\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `svr-callback-queue-${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('Subscriber Callback Queue', 'قائمة معاودة الاتصال')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Prioritized subscriber voicemails ordered urgent-first with real-time pipeline status.',
              'الرسائل الصوتية مرتبة حسب الأولوية (العاجل أولا) مع تحديث مباشر لحالة المعالجة.'
            )}
          </p>
        </div>
        <div className='flex items-center gap-2'>
          <Button
            variant='outline'
            onClick={handleExportCsv}
            disabled={loading || !(data?.items.length)}
          >
            <Download className='size-4' />
            <span>{L('Export CSV', 'تصدير CSV')}</span>
          </Button>
          <Button variant='outline' onClick={() => void fetchQueue()} disabled={loading}>
            <RefreshCw className='size-4' />
            <span>{L('Refresh', 'تحديث')}</span>
          </Button>
          <Button onClick={() => setIntakeOpen(true)}>
            <Mic className='size-4' />
            <span>{t.intakeOpen}</span>
          </Button>
        </div>
      </div>

      {/* Bucket Tabs */}
      <Tabs
        value={bucket}
        onValueChange={(val) => {
          setBucket(val)
          setCursor(null)
        }}
        className='mb-4'
      >
        <TabsList className='h-auto flex-wrap'>
          <TabsTrigger value='all'>
            {t.allBuckets} ({totalAll})
          </TabsTrigger>
          {QUEUE_BUCKETS.map((b) => (
            <TabsTrigger key={b} value={b}>
              {labelForBucket(b, locale)} ({counts[b] ?? 0})
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Filters Toolbar */}
      <Card className='mb-4'>
        <CardContent className='pt-4'>
          <form onSubmit={handleSearchSubmit} className='flex flex-wrap items-end gap-3'>
            <div className='flex min-w-[220px] flex-1 gap-2'>
              <Input
                type='search'
                value={searchInput}
                onChange={(ev) => setSearchInput(ev.target.value)}
                placeholder={t.searchPlaceholder}
                aria-label={L('Transcript search', 'بحث في النص الصوتي')}
              />
              <Button type='submit' variant='outline' aria-label={L('Search', 'بحث')}>
                <Search className='size-4' />
              </Button>
            </div>

            <Select
              value={category}
              onValueChange={(val) => {
                setCategory(val)
                setCursor(null)
              }}
            >
              <SelectTrigger className='w-full sm:w-48'>
                <SelectValue placeholder={t.filterCategory} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>{t.allOption}</SelectItem>
                {COMPLAINT_CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>
                    {labelForCategory(c, locale)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={statusFilter}
              onValueChange={(val) => {
                setStatusFilter(val)
                setCursor(null)
              }}
            >
              <SelectTrigger className='w-full sm:w-40'>
                <SelectValue placeholder={t.filterStatus} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>{t.allOption}</SelectItem>
                {TICKET_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {labelForStatus(s, locale)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={agentId}
              onValueChange={(val) => {
                setAgentId(val)
                setCursor(null)
              }}
            >
              <SelectTrigger className='w-full sm:w-48'>
                <SelectValue placeholder={t.filterAgent} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>{t.allOption}</SelectItem>
                <SelectItem value='unassigned'>{t.unassignedOption}</SelectItem>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {hasFilters && (
              <Button type='button' variant='ghost' onClick={resetFilters}>
                {L('Clear', 'مسح')}
              </Button>
            )}
          </form>
        </CardContent>
      </Card>

      {error && (
        <Alert variant='destructive' className='mb-4'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && !data ? (
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      ) : !data || data.items.length === 0 ? (
        <Card>
          <CardContent className='flex flex-col items-center justify-center gap-3 py-12 text-center'>
            <p className='text-sm text-muted-foreground'>{t.noTickets}</p>
            <Button variant='outline' onClick={() => setIntakeOpen(true)}>
              <Mic className='size-4' />
              {t.intakeOpen}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className='rounded-md border bg-card'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className='w-16'>{L('Score', 'الأولوية')}</TableHead>
                  <TableHead>{L('Ticket & Summary', 'التذكرة والملخص')}</TableHead>
                  <TableHead className='hidden md:table-cell'>{L('Agent', 'الموظف')}</TableHead>
                  <TableHead className='hidden lg:table-cell'>{L('Confidence', 'الثقة')}</TableHead>
                  <TableHead className='hidden lg:table-cell'>{L('Received', 'الاستلام')}</TableHead>
                  <TableHead>{L('Status', 'الحالة')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((ticket) => (
                  <TableRow key={ticket.id}>
                    <TableCell>
                      <PriorityScoreAvatar score={ticket.priority_score} bucket={ticket.queue_priority} size='sm' />
                    </TableCell>
                    <TableCell className='max-w-md'>
                      <Link
                        to='/tickets/$id'
                        params={{ id: ticket.id }}
                        className='block space-y-1 hover:underline'
                      >
                        <div className='flex flex-wrap items-center gap-2'>
                          <span className='font-semibold'>
                            {labelForCategory(ticket.complaint_category, locale)}
                          </span>
                          <span className='font-mono text-xs text-muted-foreground'>
                            #{ticket.id.slice(0, 8)}
                          </span>
                          <SlaCountdownBadge
                            createdAt={ticket.created_at}
                            priority={ticket.queue_priority}
                            status={ticket.status}
                            locale={locale}
                          />
                          {ticket.needs_human_review && (
                            <span className='inline-flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400'>
                              <AlertTriangle className='size-3.5' />
                              {ticket.review_reason
                                ? labelForReviewReason(ticket.review_reason, locale)
                                : L('Human Review', 'مراجعة بشرية')}
                            </span>
                          )}
                        </div>
                        <p className='truncate text-xs text-muted-foreground' dir='auto'>
                          {ticket.summary || ticket.customer_request || ticket.route_reason || '-'}
                        </p>
                      </Link>
                    </TableCell>
                    <TableCell className='hidden md:table-cell text-sm'>
                      {ticket.assigned_agent_name ?? (
                        <span className='text-muted-foreground'>-</span>
                      )}
                    </TableCell>
                    <TableCell className='hidden lg:table-cell font-mono text-xs tabular-nums'>
                      <strong>{formatPct(ticket.confidence)}</strong>{' '}
                      <span className='text-muted-foreground'>
                        / {formatPct(ticket.confidence_threshold_snapshot, 0)}
                      </span>
                    </TableCell>
                    <TableCell className='hidden lg:table-cell text-xs text-muted-foreground tabular-nums'>
                      <div>{formatUtcTimestamp(ticket.created_at, locale)}</div>
                      <div>{formatDuration(ticket.duration_seconds)}</div>
                    </TableCell>
                    <TableCell>
                      <div className='flex flex-col gap-1.5'>
                        <TicketStatusText status={ticket.status} locale={locale} />
                        <BucketText bucket={ticket.queue_priority} locale={locale} />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className='mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground'>
            <span className='tabular-nums'>
              {isAr
                ? `عرض ${data.items.length} من أصل ${data.total} تذكرة`
                : `Showing ${data.items.length} of ${data.total} tickets`}
            </span>
            <div className='flex items-center gap-2'>
              <Button
                variant='outline'
                size='sm'
                disabled={!data.prev_cursor}
                onClick={() => setCursor(data.prev_cursor)}
              >
                <ArrowLeft className='size-4' />
                {t.previous}
              </Button>
              <Button
                variant='outline'
                size='sm'
                disabled={!data.next_cursor}
                onClick={() => setCursor(data.next_cursor)}
              >
                {t.next}
                <ArrowRight className='size-4' />
              </Button>
            </div>
          </div>
        </>
      )}

      <VoicemailIntakeSheet
        open={intakeOpen}
        locale={locale}
        onOpenChange={setIntakeOpen}
        onSubmitted={() => {
          setCursor(null)
          void fetchQueue()
        }}
      />
    </Main>
  )
}
