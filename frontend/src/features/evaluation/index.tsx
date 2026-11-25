import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
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
import { Main } from '@/components/layout/main'
import { api, ApiError } from '@/lib/api'
import { UI_COPY } from '@/lib/i18n'
import { formatPct, formatUtcTimestamp } from '@/lib/taxonomy'
import type { EvalRunResponse, MonitoringSummaryResponse } from '@/lib/types'

function f1Str(val: unknown): string {
  return typeof val === 'number' && Number.isFinite(val) ? val.toFixed(4) : '-'
}

export function EvaluationPage() {
  const { locale } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [runs, setRuns] = useState<EvalRunResponse[]>([])
  const [summary, setSummary] = useState<MonitoringSummaryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [r, s] = await Promise.all([api.getEvalRuns(), api.getMonitoringSummary()])
      setRuns(r)
      setSummary(s)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load evaluation & monitoring data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const latest = runs[0] || null
  const metrics = (latest?.metrics || {}) as Record<string, unknown>
  const perField = (metrics.per_field_macro_f1 || {}) as Record<string, number>
  const ai9Wrapper = (metrics.ai9_gates || {}) as {
    all_passed?: boolean
    checks?: Record<string, { actual?: number; threshold?: number; passed?: boolean }>
  }
  const gates = ai9Wrapper.checks || (metrics.ai9_gates as Record<string, { actual?: number; threshold?: number; gate?: number; passed?: boolean }>) || {}
  const churnDetails = (metrics.churn_at_risk_analysis || {}) as Record<string, unknown>
  const fairRerun = (metrics.fair_rerun_5seed || {}) as { per_seed?: Array<Record<string, number>> }
  const fiveSeed = fairRerun.per_seed || []
  const skillF1 = (metrics.routing_per_skill || {}) as Record<
    string,
    { f1?: number; precision?: number; recall?: number; support?: number }
  >
  const rawLatencies = (metrics.latency_ms || {}) as Record<
    string,
    { p50?: number; p95?: number; mean?: number; n?: number } | number
  >
  const latencies = Object.fromEntries(
    Object.entries(rawLatencies).filter(
      (entry): entry is [string, { p50?: number; p95?: number; mean?: number; n?: number }] =>
        typeof entry[1] === 'object' && entry[1] !== null && 'p50' in entry[1]
    )
  )

  const chartData = [
    { field: 'Category', f1: perField.complaint_category ?? 0, gate: 0.75 },
    { field: 'Urgency', f1: perField.complaint_urgency ?? 0, gate: 0.7 },
    { field: 'State', f1: perField.customer_state ?? 0, gate: 0.7 },
    { field: 'Churn', f1: perField.churn_risk ?? 0, gate: 0.8 },
  ]

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('Model Evaluation & Monitoring', 'تقييم النموذج ومراقبة الأداء')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Validation Macro-F1 scores, release quality gates, skill routing accuracy, and pipeline latency monitoring.',
              'نتائج Macro-F1 على بيانات التحقق وبوابات الجودة ودقة التوجيه ومراقبة زمن المعالجة.'
            )}
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

      {loading ? (
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      ) : (
        <div className='space-y-4'>
          {latest && (
            <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
              <Card>
                <CardHeader className='pb-2'>
                  <CardTitle className='text-sm font-medium'>
                    {L('Combined Macro-F1', 'متوسط Macro-F1')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold tabular-nums'>
                    {f1Str(metrics.combined_macro_f1)}
                  </div>
                  <p className='text-xs text-muted-foreground'>
                    {latest.split} · {String(metrics.n_rows ?? 1003)} rows
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className='pb-2'>
                  <CardTitle className='text-sm font-medium'>
                    {L('Skill Routing Agreement', 'دقة التوجيه بالمهارات')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold tabular-nums'>
                    {typeof metrics.routing_agreement_pct === 'number'
                      ? `${metrics.routing_agreement_pct.toFixed(2)}%`
                      : '-'}
                  </div>
                  <p className='text-xs text-muted-foreground'>Gate &gt;= 80.0%</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className='pb-2'>
                  <CardTitle className='text-sm font-medium'>
                    {L('24h Human Review Rate', 'معدل المراجعة (24س)')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold tabular-nums'>
                    {summary ? formatPct(summary.human_review_rate_24h, 1) : '-'}
                  </div>
                  <p className='text-xs text-muted-foreground'>Alert threshold &gt; 20.0%</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className='pb-2'>
                  <CardTitle className='text-sm font-medium'>
                    {L('End-to-End p50 / p95', 'الزمن الكلي p50 / p95')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className='text-2xl font-bold tabular-nums'>
                    {latencies.end_to_end?.p50 ? `${(latencies.end_to_end.p50 / 1000).toFixed(1)}s` : '-'} /{' '}
                    {latencies.end_to_end?.p95 ? `${(latencies.end_to_end.p95 / 1000).toFixed(1)}s` : '-'}
                  </div>
                  <p className='text-xs text-muted-foreground'>Production GPU SLA target &lt;= 10s</p>
                </CardContent>
              </Card>
            </div>
          )}

          {latest && (
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-7'>
              <Card className='lg:col-span-3'>
                <CardHeader>
                  <CardTitle>{L('Per-Field Macro-F1', 'دقة كل حقل Macro-F1')}</CardTitle>
                  <CardDescription className='font-mono text-xs'>{latest.model_version}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className='svr-chart'>
                  <ResponsiveContainer width='100%' height={250}>
                    <BarChart
                      data={chartData}
                      margin={{ top: 24, right: 12, left: 0, bottom: 4 }}
                    >
                      <defs>
                        <linearGradient id='evalFadeGrad' x1='0' y1='0' x2='0' y2='1'>
                          <stop offset='0%' stopColor='#ffffff' stopOpacity={1} />
                          <stop offset='70%' stopColor='#ffffff' stopOpacity={0.55} />
                          <stop offset='100%' stopColor='#ffffff' stopOpacity={0.04} />
                        </linearGradient>
                        <mask id='evalFadeMask' maskUnits='objectBoundingBox' maskContentUnits='objectBoundingBox'>
                          <rect x='0' y='0' width='1' height='1' fill='url(#evalFadeGrad)' />
                        </mask>
                        <pattern id='evalPat' width='8' height='8' patternUnits='userSpaceOnUse' patternTransform='rotate(45)'>
                          <rect width='8' height='8' fill='#38bdf8' />
                          <line x1='0' y1='0' x2='0' y2='8' stroke='var(--card)' strokeWidth='2.2' strokeOpacity='0.6' />
                        </pattern>
                      </defs>
                      <CartesianGrid strokeDasharray='3 3' stroke='var(--border)' opacity={0.45} />
                      <XAxis dataKey='field' stroke='var(--muted-foreground)' fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis domain={[0, 1]} stroke='var(--muted-foreground)' fontSize={12} tickLine={false} axisLine={false} />
                      <Tooltip
                        cursor={false}
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
                      <Bar
                        dataKey='f1'
                        radius={[6, 6, 0, 0]}
                        isAnimationActive
                        animationDuration={650}
                      >
                        <LabelList
                          dataKey='f1'
                          position='top'
                          offset={6}
                          formatter={(v: unknown) => (typeof v === 'number' ? v.toFixed(2) : '')}
                          fill='var(--foreground)'
                          fontSize={12}
                          fontWeight={600}
                        />
                        {chartData.map((entry) => (
                          <Cell
                            key={entry.field}
                            fill='url(#evalPat)'
                            mask='url(#evalFadeMask)'
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>

              <Card className='lg:col-span-4'>
                <CardHeader>
                  <CardTitle>{L('Release Quality Gates', 'بوابات اعتماد الجودة')}</CardTitle>
                  <CardDescription>
                    {L(
                      'Evaluated on the validation benchmark split (1,003 samples).',
                      'التقييم على بيانات التحقق المعتمدة (1,003 عينة).'
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{L('Task', 'الحقل')}</TableHead>
                        <TableHead className='text-end'>{L('Measured F1', 'النتيجة')}</TableHead>
                        <TableHead className='text-end'>{L('Gate', 'الحد')}</TableHead>
                        <TableHead>{L('Status', 'الحالة')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {['complaint_category', 'complaint_urgency', 'customer_state', 'churn_risk'].map((f) => {
                        const g = gates[f] || {}
                        const passed = Boolean(g.passed)
                        return (
                          <TableRow key={f}>
                            <TableCell className='font-mono text-xs'>{f}</TableCell>
                            <TableCell className='text-end font-mono tabular-nums'>{f1Str(perField[f])}</TableCell>
                            <TableCell className='text-end font-mono tabular-nums'>
                              {typeof g.threshold === 'number'
                                ? g.threshold.toFixed(2)
                                : typeof (g as { gate?: number }).gate === 'number'
                                  ? (g as { gate: number }).gate.toFixed(2)
                                  : '-'}
                            </TableCell>
                            <TableCell>
                              <Badge variant={passed ? 'default' : 'destructive'} className='gap-1'>
                                {passed ? <CheckCircle2 className='size-3' /> : <AlertTriangle className='size-3' />}
                                {passed ? 'PASS' : 'FAIL'}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}

          {latest && (
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
              <Card>
                <CardHeader>
                  <CardTitle>{L('Churn Sensitivity & Multi-Run Breakdown', 'حساسية خطر الفقد عبر التشغيلات')}</CardTitle>
                  <CardDescription>
                    True at_risk in validation: {String(churnDetails.true_at_risk_count ?? 7)} / 1,003 (TP{' '}
                    {String(churnDetails.true_positives ?? '-')}, FP {String(churnDetails.false_positives ?? '-')}, FN{' '}
                    {String(churnDetails.false_negatives ?? '-')})
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Run</TableHead>
                        <TableHead className='text-end'>Category</TableHead>
                        <TableHead className='text-end'>Urgency</TableHead>
                        <TableHead className='text-end'>State</TableHead>
                        <TableHead className='text-end'>Churn</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fiveSeed.map((row) => (
                        <TableRow key={row.seed}>
                          <TableCell className='font-mono'>{row.seed}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{f1Str(row.complaint_category)}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{f1Str(row.complaint_urgency)}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{f1Str(row.customer_state)}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{f1Str(row.churn_risk)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>{L('Skill Routing & Stage Latencies', 'دقة التوجيه وزمن المراحل')}</CardTitle>
                </CardHeader>
                <CardContent className='space-y-4'>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{L('Skill', 'المهارة')}</TableHead>
                        <TableHead className='text-end'>Support</TableHead>
                        <TableHead className='text-end'>Precision</TableHead>
                        <TableHead className='text-end'>Recall</TableHead>
                        <TableHead className='text-end'>F1</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {Object.entries(skillF1).map(([sk, v]) => (
                        <TableRow key={sk}>
                          <TableCell className='font-medium'>{sk}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{v.support ?? '-'}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{f1Str(v.precision)}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{f1Str(v.recall)}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{f1Str(v.f1)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{L('Eval Stage', 'المرحلة')}</TableHead>
                        <TableHead className='text-end'>n</TableHead>
                        <TableHead className='text-end'>p50 (ms)</TableHead>
                        <TableHead className='text-end'>p95 (ms)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {Object.entries(latencies).map(([st, v]) => (
                        <TableRow key={st}>
                          <TableCell className='font-mono text-xs'>{st}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{v.n ?? '-'}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{v.p50?.toFixed(2) ?? '-'}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{v.p95?.toFixed(2) ?? '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{L('Recorded Evaluation Runs', 'سجل تشغيلات التقييم')}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Split</TableHead>
                    <TableHead>Model Version</TableHead>
                    <TableHead>Created By</TableHead>
                    <TableHead>Timestamp</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className='font-mono text-xs'>{r.id.slice(0, 8)}</TableCell>
                      <TableCell>{r.split}</TableCell>
                      <TableCell className='font-mono text-xs'>{r.model_version}</TableCell>
                      <TableCell>{r.created_by}</TableCell>
                      <TableCell className='font-mono text-xs tabular-nums'>
                        {formatUtcTimestamp(r.created_at, locale)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}
    </Main>
  )
}
