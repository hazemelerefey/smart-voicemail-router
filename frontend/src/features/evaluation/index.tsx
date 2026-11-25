import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react'
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
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
              'Validation-split MARBERTv2 Macro-F1, AI9 release gates, FR20 routing agreement, and AI10 latency alerts.',
              'نتائج Macro-F1 على بيانات التحقق وبوابات AI9 ونسبة التوجيه FR20 وتنبيهات AI10.'
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
                    {L('FR20 Routing Agreement', 'توافق التوجيه FR20')}
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
                  <p className='text-xs text-muted-foreground'>AI10 alert &gt; 20.0%</p>
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
                  <p className='text-xs text-muted-foreground'>PRD L8 GPU target &lt;= 10s</p>
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
                  <ResponsiveContainer width='100%' height={250}>
                    <BarChart data={chartData}>
                      <XAxis dataKey='field' stroke='#888888' fontSize={12} tickLine={false} axisLine={false} />
                      <YAxis domain={[0, 1]} stroke='#888888' fontSize={12} tickLine={false} axisLine={false} />
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
                      <Bar dataKey='f1' fill='var(--primary)' radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card className='lg:col-span-4'>
                <CardHeader>
                  <CardTitle>{L('AI9 Release Gates', 'بوابات الاعتماد AI9')}</CardTitle>
                  <CardDescription>
                    {L(
                      'Evaluated exclusively on frozen validation split (1,003 rows, 1 unclear excluded from customer_state).',
                      'التقييم على بيانات التحقق فقط (1,003 صف، استثناء صف unclear واحد من حالة العميل).'
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
                  <CardTitle>{L('Churn Fragility & 5-Seed Breakdown', 'حساسية خطر الفقد عبر 5 بذور')}</CardTitle>
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
                        <TableHead>Seed</TableHead>
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
                  <CardTitle>{L('FR20 Skill Routing & Stage Latencies', 'دقة التوجيه وزمن المراحل')}</CardTitle>
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
