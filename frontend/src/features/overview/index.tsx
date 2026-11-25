import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  BellRing,
  CheckCircle2,
  Mic,
  RefreshCw,
  Users,
} from 'lucide-react'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Main } from '@/components/layout/main'
import { BucketText, TicketStatusText, scoreSquareClass } from '@/components/svr/status-badges'
import { VoicemailIntakeSheet } from '@/components/svr/voicemail-intake-sheet'
import { api, ApiError } from '@/lib/api'
import { UI_COPY, labelForBucket, labelForCategory } from '@/lib/i18n'
import { QUEUE_BUCKETS, formatPct, formatUtcTimestamp } from '@/lib/taxonomy'
import type { AgentResponse, MonitoringSummaryResponse, TicketListResponse } from '@/lib/types'

const REVIEW_RATE_TARGET = 0.2
const LATENCY_TARGET_MS = 10000

const STATE_ORDER = ['mad', 'frustrated', 'calm', 'satisfied'] as const
const STATE_LABEL: Record<string, { en: string; ar: string }> = {
  mad: { en: 'Mad', ar: 'غاضب' },
  frustrated: { en: 'Frustrated', ar: 'منزعج' },
  calm: { en: 'Calm', ar: 'هادئ' },
  satisfied: { en: 'Satisfied', ar: 'راضي' },
}
const CHURN_ORDER = ['at_risk', 'not_at_risk'] as const
const CHURN_LABEL: Record<string, { en: string; ar: string }> = {
  at_risk: { en: 'At risk', ar: 'معرض للفقد' },
  not_at_risk: { en: 'Not at risk', ar: 'مش معرض للفقد' },
}

function seconds(ms: number | undefined): string {
  if (ms === undefined || !Number.isFinite(ms) || ms <= 0) return '-'
  return `${(ms / 1000).toFixed(1)}s`
}

function prettyStage(key: string): string {
  return key.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function OverviewPage() {
  const { locale, wsVersion, settings } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [summary, setSummary] = useState<MonitoringSummaryResponse | null>(null)
  const [queue, setQueue] = useState<TicketListResponse | null>(null)
  const [agents, setAgents] = useState<AgentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [intakeOpen, setIntakeOpen] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [s, q, a] = await Promise.all([
        api.getMonitoringSummary(),
        api.listTickets({ limit: 6 }),
        api.listAgents(),
      ])
      setSummary(s)
      setQueue(q)
      setAgents(a)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load operations overview.')
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

  const counts = queue?.counts_by_bucket ?? {}
  const urgent = counts.urgent ?? 0
  const unassigned = queue?.counts_by_status?.unassigned ?? 0
  const humanReview = queue?.human_review_count ?? 0

  const categoryData = Object.entries(summary?.classification_distribution?.complaint_category ?? {})
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([cat, count]) => ({
      name: labelForCategory(cat, locale),
      count,
    }))
  const classifiedTotal = categoryData.reduce((acc, r) => acc + r.count, 0)

  const threshold = settings?.confidence_threshold ?? 0.5
  const histData = (summary?.confidence_histogram ?? []).map((h, i) => {
    const lo = (h as { min?: number }).min ?? i / 10
    return {
      bin: lo.toFixed(1),
      count: h.count,
      below: lo + 0.1 <= threshold + 1e-9,
    }
  })

  const stateDist = summary?.classification_distribution?.customer_state ?? {}
  const churnDist = summary?.classification_distribution?.churn_risk ?? {}

  const has24h = (summary?.tickets_last_24h ?? 0) > 0
  const reviewRate24h = summary?.human_review_rate_24h ?? 0
  const p95_24h = summary?.end_to_end_latency_24h_ms?.p95
  const reviewOk = reviewRate24h <= REVIEW_RATE_TARGET
  const latencyOk = (p95_24h ?? 0) <= LATENCY_TARGET_MS

  const stageRows = Object.entries(summary?.stage_latency_ms ?? {}).filter(
    ([, v]) => (v?.p50 ?? 0) > 0 || (v?.p95 ?? 0) > 0
  )

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('Operations Overview', 'نظرة عامة على التشغيل')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Live view of voicemail transcription, MARBERTv2 triage, and telecom agent capacity.',
              'متابعة مباشرة لتفريغ الرسائل الصوتية وتصنيف MARBERTv2 وسعة الموظفين.'
            )}
          </p>
        </div>
        <div className='flex items-center gap-2'>
          <Button variant='outline' onClick={() => void load()} disabled={loading}>
            <RefreshCw className='size-4' />
            <span>{L('Refresh', 'تحديث')}</span>
          </Button>
          <Button onClick={() => setIntakeOpen(true)}>
            <Mic className='size-4' />
            <span>{t.intakeOpen}</span>
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant='destructive' className='mb-4'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {summary?.alerts?.map((a) => (
        <Alert
          key={a.code}
          variant={a.severity === 'critical' ? 'destructive' : 'default'}
          className='mb-3'
        >
          <AlertTriangle className='size-4' />
          <AlertDescription>{a.message}</AlertDescription>
        </Alert>
      ))}

      <Tabs defaultValue='overview' className='space-y-4'>
        <TabsList>
          <TabsTrigger value='overview'>{L('Overview', 'نظرة عامة')}</TabsTrigger>
          <TabsTrigger value='analytics'>{L('Analytics', 'التحليلات')}</TabsTrigger>
        </TabsList>

        <TabsContent value='overview' className='space-y-4'>
          {/* 4 Shadcn KPI Cards */}
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>{L('Urgent Now', 'عاجل الآن')}</CardTitle>
                <BellRing className='size-4 text-destructive' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold tabular-nums text-destructive'>
                  {queue ? urgent : '-'}
                </div>
                <p className='text-xs text-muted-foreground'>
                  {L(
                    `${unassigned} unassigned · ${QUEUE_BUCKETS.map((b) => `${labelForBucket(b, locale)} ${counts[b] ?? 0}`).join(' / ')}`,
                    `${unassigned} بدون موظف`
                  )}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>
                  {L('Voicemails (24h)', 'الرسائل (24 ساعة)')}
                </CardTitle>
                <Activity className='size-4 text-muted-foreground' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold tabular-nums'>
                  {summary?.tickets_last_24h ?? 0}
                </div>
                <p className='text-xs text-muted-foreground'>
                  {L(`${summary?.total_tickets ?? 0} total tickets`, `${summary?.total_tickets ?? 0} تذكرة إجمالا`)}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>
                  {L('Human Review Rate (24h)', 'نسبة المراجعة (24 ساعة)')}
                </CardTitle>
                <Users className='size-4 text-muted-foreground' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold tabular-nums'>
                  {has24h ? formatPct(reviewRate24h, 1) : '-'}
                </div>
                <p className='text-xs text-muted-foreground'>
                  {has24h ? (
                    reviewOk ? (
                      <span className='text-emerald-600 dark:text-emerald-400'>
                        {L(`${humanReview} in review · Within 20% target`, `${humanReview} للمراجعة · ضمن 20%`)}
                      </span>
                    ) : (
                      <span className='text-destructive'>
                        {L(`${humanReview} in review · Above 20% target`, `${humanReview} للمراجعة · أعلى من 20%`)}
                      </span>
                    )
                  ) : (
                    L('No 24h tickets', 'لا توجد تذاكر خلال 24 ساعة')
                  )}
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className='flex flex-row items-center justify-between space-y-0 pb-2'>
                <CardTitle className='text-sm font-medium'>
                  {L('End-to-End p95 (24h)', 'زمن المعالجة p95')}
                </CardTitle>
                <CheckCircle2 className='size-4 text-muted-foreground' />
              </CardHeader>
              <CardContent>
                <div className='text-2xl font-bold tabular-nums'>
                  {has24h ? seconds(p95_24h) : '-'}
                </div>
                <p className='text-xs text-muted-foreground'>
                  {L('Success', 'النجاح')}: {formatPct(summary?.processing_success_rate ?? 0, 1)} ·{' '}
                  {has24h && p95_24h
                    ? latencyOk
                      ? L('Within 10s', 'ضمن 10 ثواني')
                      : L('Above 10s CPU SLA', 'أعلى من 10 ثواني')
                    : '-'}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Main 7-col grid: Recharts Categories + Top of Queue */}
          <div className='grid grid-cols-1 gap-4 lg:grid-cols-7'>
            <Card className='col-span-1 lg:col-span-4'>
              <CardHeader>
                <CardTitle>{L('Complaint Categories', 'أنواع الشكاوى')}</CardTitle>
                <CardDescription>
                  {L(
                    `${classifiedTotal} classified of ${summary?.total_tickets ?? 0} total tickets`,
                    `${classifiedTotal} مصنفة من إجمالي ${summary?.total_tickets ?? 0} تذكرة`
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className='ps-2'>
                {categoryData.length === 0 ? (
                  <p className='px-4 py-8 text-sm text-muted-foreground'>
                    {L('No classified tickets yet.', 'لا توجد تذاكر مصنفة بعد.')}
                  </p>
                ) : (
                  <ResponsiveContainer width='100%' height={300}>
                    <BarChart data={categoryData} margin={{ top: 8, right: 16, left: 0, bottom: 24 }}>
                      <XAxis
                        dataKey='name'
                        stroke='#888888'
                        fontSize={11}
                        tickLine={false}
                        axisLine={false}
                        interval={0}
                        angle={-15}
                        textAnchor='end'
                        height={52}
                      />
                      <YAxis
                        stroke='#888888'
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                        allowDecimals={false}
                      />
                      <Tooltip
                        cursor={{ fill: 'var(--accent)', opacity: 0.4 }}
                        contentStyle={{
                          backgroundColor: 'var(--popover)',
                          borderColor: 'var(--border)',
                          borderRadius: 'var(--radius)',
                          color: 'var(--popover-foreground)',
                          fontSize: '12px',
                        }}
                        itemStyle={{ color: 'var(--popover-foreground)' }}
                        labelStyle={{ color: 'var(--muted-foreground)' }}
                      />
                      <Bar dataKey='count' fill='currentColor' radius={[4, 4, 0, 0]} className='fill-primary' />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card className='col-span-1 lg:col-span-3'>
              <CardHeader className='flex flex-row items-center justify-between'>
                <div>
                  <CardTitle>{L('Top of the Queue', 'أعلى القائمة')}</CardTitle>
                  <CardDescription>
                    {L('Highest priority callback tickets', 'التذاكر الأعلى أولوية لمعاودة الاتصال')}
                  </CardDescription>
                </div>
                <Button variant='ghost' size='sm' asChild>
                  <Link to='/dashboard'>
                    {L('View all', 'الكل')}
                    <ArrowRight className='ms-1 size-4' />
                  </Link>
                </Button>
              </CardHeader>
              <CardContent>
                {!queue || queue.items.length === 0 ? (
                  <p className='text-sm text-muted-foreground'>{t.noTickets}</p>
                ) : (
                  <div className='space-y-3'>
                    {queue.items.map((ticket) => (
                      <Link
                        key={ticket.id}
                        to='/tickets/$id'
                        params={{ id: ticket.id }}
                        className='flex items-center justify-between gap-3 rounded-md border p-2.5 transition-colors hover:bg-muted/50'
                      >
                        <div className='flex min-w-0 items-center gap-3'>
                          <div
                            className={`flex size-9 shrink-0 items-center justify-center rounded-md text-sm font-bold tabular-nums ${scoreSquareClass(ticket.queue_priority)}`}
                          >
                            {ticket.priority_score !== null ? ticket.priority_score : '-'}
                          </div>
                          <div className='min-w-0'>
                            <p className='truncate text-sm font-medium leading-none'>
                              {labelForCategory(ticket.complaint_category, locale)}
                            </p>
                            <p className='mt-1 truncate text-xs text-muted-foreground' dir='auto'>
                              {ticket.summary || ticket.customer_request || ticket.route_reason || '-'}
                            </p>
                          </div>
                        </div>
                        <div className='flex shrink-0 flex-col items-end gap-1'>
                          <TicketStatusText status={ticket.status} locale={locale} />
                          <BucketText bucket={ticket.queue_priority} locale={locale} />
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value='analytics' className='space-y-4'>
          <div className='grid grid-cols-1 gap-4 lg:grid-cols-7'>
            {/* Confidence Histogram */}
            <Card className='col-span-1 lg:col-span-4'>
              <CardHeader>
                <CardTitle>{L('Classification Confidence', 'ثقة التصنيف')}</CardTitle>
                <CardDescription>
                  {L(
                    `Amber bars fall below the ${formatPct(threshold, 0)} human review threshold.`,
                    `الأعمدة البرتقالية أقل من حد المراجعة (${formatPct(threshold, 0)}).`
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className='ps-2'>
                <ResponsiveContainer width='100%' height={240}>
                  <BarChart data={histData}>
                    <XAxis dataKey='bin' stroke='#888888' fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke='#888888' fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip
                      cursor={{ fill: 'var(--accent)', opacity: 0.4 }}
                      contentStyle={{
                        backgroundColor: 'var(--popover)',
                        borderColor: 'var(--border)',
                        borderRadius: 'var(--radius)',
                        color: 'var(--popover-foreground)',
                        fontSize: '12px',
                      }}
                      itemStyle={{ color: 'var(--popover-foreground)' }}
                      labelStyle={{ color: 'var(--muted-foreground)' }}
                    />
                    <Bar dataKey='count' radius={[4, 4, 0, 0]}>
                      {histData.map((entry, idx) => (
                        <Cell
                          key={idx}
                          fill={entry.below ? 'var(--bar-warn)' : 'var(--primary)'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            {/* Agent Workload */}
            <Card className='col-span-1 lg:col-span-3'>
              <CardHeader className='flex flex-row items-center justify-between'>
                <div>
                  <CardTitle>{L('Agent Workload', 'حمل الموظفين')}</CardTitle>
                  <CardDescription>{L('Active shift capacity', 'السعة الحالية للموظفين')}</CardDescription>
                </div>
                <Button variant='ghost' size='sm' asChild>
                  <Link to='/admin/agents'>{L('Manage', 'إدارة')}</Link>
                </Button>
              </CardHeader>
              <CardContent className='space-y-4'>
                {agents
                  .filter((a) => a.active)
                  .sort((a, b) => a.seed_order - b.seed_order)
                  .map((a) => {
                    const pct = Math.min(100, (a.current_load / Math.max(1, a.capacity)) * 100)
                    const full = a.current_load >= a.capacity
                    return (
                      <div key={a.id} className='space-y-1.5'>
                        <div className='flex items-center justify-between text-sm'>
                          <span className='font-medium'>{a.name}</span>
                          <span className='font-mono text-xs font-semibold tabular-nums' dir='ltr'>
                            {a.current_load} / {a.capacity}
                          </span>
                        </div>
                        <div className='h-2 w-full overflow-hidden rounded-full bg-muted'>
                          <div
                            className={`h-full rounded-full ${full ? 'bg-destructive' : 'bg-primary'}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <p className='text-xs text-muted-foreground'>
                          {a.skills.join(', ')} ·{' '}
                          {a.available ? L('Available', 'متاح') : L('Off shift', 'خارج الوردية')}
                        </p>
                      </div>
                    )
                  })}
              </CardContent>
            </Card>
          </div>

          <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
            {/* Customer Signals */}
            <Card>
              <CardHeader>
                <CardTitle>{L('Customer Signals', 'إشارات العملاء')}</CardTitle>
                <CardDescription>
                  {L('MARBERTv2 customer state & churn risk breakdown', 'توزيع حالة العميل وخطر الفقد')}
                </CardDescription>
              </CardHeader>
              <CardContent className='space-y-5'>
                <div>
                  <div className='mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground'>
                    {L('Customer State', 'حالة العميل')}
                  </div>
                  <div className='grid grid-cols-2 gap-3 sm:grid-cols-4'>
                    {STATE_ORDER.map((k) => (
                      <div key={k} className='rounded-md border p-3'>
                        <div className='text-xs text-muted-foreground'>{STATE_LABEL[k][locale]}</div>
                        <div className='mt-1 text-xl font-bold tabular-nums'>{stateDist[k] ?? 0}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className='mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground'>
                    {L('Churn Risk', 'خطر فقد العميل')}
                  </div>
                  <div className='grid grid-cols-2 gap-3'>
                    {CHURN_ORDER.map((k) => (
                      <div key={k} className='rounded-md border p-3'>
                        <div className='text-xs text-muted-foreground'>{CHURN_LABEL[k][locale]}</div>
                        <div
                          className={`mt-1 text-xl font-bold tabular-nums ${k === 'at_risk' ? 'text-destructive' : ''}`}
                        >
                          {churnDist[k] ?? 0}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Pipeline Stage Latency */}
            <Card>
              <CardHeader>
                <CardTitle>{L('Pipeline Stage Latency', 'زمن مراحل المعالجة')}</CardTitle>
                <CardDescription>
                  {L('Measured across all processed tickets', 'مقاس عبر كل التذاكر المكتملة')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{L('Stage', 'المرحلة')}</TableHead>
                      <TableHead className='text-end'>p50</TableHead>
                      <TableHead className='text-end'>p95</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {stageRows.map(([stage, v]) => (
                      <TableRow key={stage}>
                        <TableCell>{prettyStage(stage)}</TableCell>
                        <TableCell className='text-end font-mono tabular-nums'>
                          {seconds(v.p50)}
                        </TableCell>
                        <TableCell className='text-end font-mono tabular-nums'>
                          {seconds(v.p95)}
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow className='font-semibold'>
                      <TableCell>{L('End to end', 'من البداية للنهاية')}</TableCell>
                      <TableCell className='text-end font-mono tabular-nums'>
                        {seconds(summary?.end_to_end_latency_ms?.p50)}
                      </TableCell>
                      <TableCell className='text-end font-mono tabular-nums'>
                        {seconds(summary?.end_to_end_latency_ms?.p95)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
                {queue?.items[0] && (
                  <p className='mt-3 text-xs text-muted-foreground'>
                    {L('Latest ticket:', 'أحدث تذكرة:')}{' '}
                    <span className='font-mono'>
                      {formatUtcTimestamp(queue.items[0].created_at, locale)}
                    </span>
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <VoicemailIntakeSheet
        open={intakeOpen}
        locale={locale}
        onOpenChange={setIntakeOpen}
        onSubmitted={() => void load()}
      />
    </Main>
  )
}
