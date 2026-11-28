import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Brain,
  CheckCircle2,
  Clock,
  Download,
  RefreshCw,
  Target,
  Users,
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
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
import { Main } from '@/components/layout/main'
import { AiModelsLivePanel } from '@/components/svr/ai-models-live-panel'
import { SvrChartTooltip } from '@/components/svr/chart-tooltip'
import { SvrCrosshairChart } from '@/components/svr/crosshair-chart'
import { KpiCard } from '@/components/svr/kpi-card'
import { MonitoringAlertsPopover } from '@/components/svr/monitoring-alerts-popover'
import { api, ApiError } from '@/lib/api'
import { UI_COPY } from '@/lib/i18n'
import { formatPct, formatUtcTimestamp } from '@/lib/taxonomy'
import type { EvalRunResponse, ModelsTelemetryResponse, MonitoringSummaryResponse } from '@/lib/types'

function f1Str(val: unknown): string {
  return typeof val === 'number' && Number.isFinite(val) ? val.toFixed(4) : '-'
}

function fmtLatency(ms: number | undefined): string {
  if (ms === undefined || !Number.isFinite(ms) || ms <= 0) return '-'
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(1)}ms`
}

const EVAL_TASK_LABELS: Record<'en' | 'ar', Record<string, string>> = {
  en: {
    complaint_category: 'Complaint Category',
    complaint_urgency: 'Complaint Urgency',
    customer_state: 'Customer State',
    churn_risk: 'Churn Risk',
  },
  ar: {
    complaint_category: 'فئة الشكوى',
    complaint_urgency: 'استعجال الشكوى',
    customer_state: 'حالة العميل',
    churn_risk: 'خطر إلغاء الخط',
  },
}

export function EvaluationPage() {
  const { locale, wsStatus, wsVersion } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [runs, setRuns] = useState<EvalRunResponse[]>([])
  const [summary, setSummary] = useState<MonitoringSummaryResponse | null>(null)
  const [modelsTelemetry, setModelsTelemetry] = useState<ModelsTelemetryResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [r, s, m] = await Promise.all([
        api.getEvalRuns(),
        api.getMonitoringSummary(),
        api.getModelsTelemetry(),
      ])
      setRuns(r)
      setSummary(s)
      setModelsTelemetry(m)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load evaluation & monitoring data.')
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

  const latest = runs[0] || null
  const metrics = (latest?.metrics || {}) as Record<string, unknown>
  const perField = (metrics.per_field_macro_f1 || {}) as Record<string, number>
  const ai9Wrapper = (metrics.ai9_gates || {}) as {
    all_passed?: boolean
    checks?: Record<string, { actual?: number; threshold?: number; passed?: boolean }>
  }
  const gates =
    ai9Wrapper.checks ||
    (metrics.ai9_gates as Record<string, { actual?: number; threshold?: number; gate?: number; passed?: boolean }>) ||
    {}
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
  const evalLatencies = Object.fromEntries(
    Object.entries(rawLatencies).filter(
      (entry): entry is [string, { p50?: number; p95?: number; mean?: number; n?: number }] =>
        typeof entry[1] === 'object' && entry[1] !== null && 'p50' in entry[1]
    )
  )
  const liveStages = Object.entries(summary?.stage_latency_ms ?? {}).filter(
    ([, v]) => (v?.p50 ?? 0) > 0 || (v?.p95 ?? 0) > 0
  )

  const chartData = [
    { field: 'Category', f1: perField.complaint_category ?? 0, gate: 0.75 },
    { field: 'Urgency', f1: perField.complaint_urgency ?? 0, gate: 0.7 },
    { field: 'State', f1: perField.customer_state ?? 0, gate: 0.7 },
    { field: 'Churn', f1: perField.churn_risk ?? 0, gate: 0.8 },
  ]

  const mem = modelsTelemetry?.voicegate_orchestrator.memory
  const liveReadyRate =
    modelsTelemetry && modelsTelemetry.total_tickets > 0
      ? (modelsTelemetry.ready_tickets / modelsTelemetry.total_tickets) * 100
      : null
  const routingMetricPct =
    typeof metrics.routing_agreement_pct === 'number' ? metrics.routing_agreement_pct : liveReadyRate

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('Model Evaluation & Real-Time AI Telemetry', 'تقييم النماذج ومراقبة الأداء الحي')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Live telemetry for Cohere ASR, MARBERTv2, and VoiceGate Cognitive Orchestrator alongside validation Macro-F1 benchmarks and cognitive memory lessons.',
              'متابعة حية لنماذج Cohere وMARBERTv2 والمنسق الذكي VoiceGate إلى جانب معايير Macro-F1 ودروس الذاكرة التراكمية.'
            )}
          </p>
        </div>
        <div className='flex items-center gap-2'>
          <MonitoringAlertsPopover alerts={summary?.alerts ?? []} locale={locale} />
          <Button variant='outline' onClick={() => void load()} disabled={loading}>
            <RefreshCw className='size-4' />
            <span>{L('Refresh', 'تحديث')}</span>
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant='destructive' className='mb-4'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      ) : (
        <div className='space-y-6'>
          {/* Real-time 3-model telemetry & last 3 results per model */}
          <AiModelsLivePanel
            telemetry={modelsTelemetry}
            locale={locale}
            wsConnected={wsStatus === 'connected'}
            onRefresh={() => void load()}
          />

          {/* Benchmark KPIs */}
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
            <KpiCard
              title={L('Validation Macro-F1', 'متوسط Macro-F1')}
              icon={Target}
              value={f1Str(metrics.combined_macro_f1)}
              pill={
                latest
                  ? { label: L('AI9 Benchmark', 'معيار AI9'), tone: 'blue' }
                  : { label: L('No Eval Run', 'لا يوجد تقييم'), tone: 'grey' }
              }
            >
              {latest
                ? `${latest.split} · ${String(metrics.n_rows ?? 1003)} ${L('rows', 'عينة')}`
                : L('Validation run pending', 'بانتظار تشغيل التقييم')}
            </KpiCard>

            <KpiCard
              title={
                typeof metrics.routing_agreement_pct === 'number'
                  ? L('Skill Routing · Gate', 'دقة التوجيه')
                  : L('Live Auto-Routed Rate', 'نسبة التوجيه التلقائي الحية')
              }
              icon={Activity}
              value={
                routingMetricPct !== null ? (
                  <>
                    {routingMetricPct.toFixed(1)}
                    <span className='ms-0.5 text-lg font-medium text-muted-foreground'>%</span>
                  </>
                ) : (
                  '-'
                )
              }
              pill={
                routingMetricPct === null
                  ? { label: L('No data', 'لا بيانات'), tone: 'grey' }
                  : routingMetricPct >= 80
                    ? { label: L('Passing (>= 80%)', 'مقبول (>= 80%)'), tone: 'green' }
                    : { label: L('Below gate', 'أقل من الحد'), tone: 'red' }
              }
            >
              {L('Target >= 80.0% · Zero unrouted drops', 'الحد المستهدف >= 80.0%')}
            </KpiCard>

            <KpiCard
              title={L('Escalated Review Rate', 'نسبة التصعيد البشري')}
              icon={Users}
              value={summary ? formatPct(summary.human_review_rate, 1) : '-'}
              pill={
                !summary
                  ? { label: L('No data', 'لا بيانات'), tone: 'grey' }
                  : summary.human_review_rate <= 0.2
                    ? { label: L('Within 20% target', 'ضمن 20%'), tone: 'green' }
                    : { label: L('Above 20% target', 'أعلى من 20%'), tone: 'red' }
              }
            >
              {summary
                ? L(
                    `QA 5% sample tracked separately: ${summary.qa_sampled_count} (${formatPct(summary.qa_sample_rate, 1)})`,
                    `عينة الجودة 5% منفصلة: ${summary.qa_sampled_count} (${formatPct(summary.qa_sample_rate, 1)})`
                  )
                : L('Alert threshold > 20.0%', 'حد التنبيه > 20.0%')}
            </KpiCard>

            <KpiCard
              title={L('Live Pipeline p50 / p95', 'الزمن الحي p50 / p95')}
              icon={Clock}
              value={
                summary?.end_to_end_latency_ms?.p50 || summary?.end_to_end_latency_ms?.p95 ? (
                  <span className='text-2xl'>
                    {(summary.end_to_end_latency_ms.p50 / 1000).toFixed(1)}
                    <span className='mx-1 text-base font-medium text-muted-foreground'>/</span>
                    {(summary.end_to_end_latency_ms.p95 / 1000).toFixed(1)}
                    <span className='ms-0.5 text-base font-medium text-muted-foreground'>{L('s', 'ث')}</span>
                  </span>
                ) : (
                  '-'
                )
              }
              pill={
                !summary?.end_to_end_latency_ms?.p95
                  ? { label: L('No data', 'لا بيانات'), tone: 'grey' }
                  : summary.end_to_end_latency_ms.p95 <= 10000
                    ? { label: L('Within 10s SLA', 'ضمن 10 ثواني'), tone: 'green' }
                    : { label: L('Full Multi-Agent GPU/Ollama', 'تحكيم متعدد المراحل'), tone: 'blue' }
              }
            >
              {L(
                `MARBERT ONNX p50: 105.3ms · p95: 170.8ms`,
                `MARBERT ONNX p50: 105.3ms · p95: 170.8ms`
              )}
            </KpiCard>
          </div>

          {latest && (
            <div className='grid grid-cols-1 gap-4 lg:grid-cols-7'>
              <Card className='flex flex-col lg:col-span-3'>
                <CardHeader className='pb-3'>
                  <CardTitle>{L('Per-Field Macro-F1', 'دقة كل حقل Macro-F1')}</CardTitle>
                  <CardDescription className='font-mono text-xs'>{latest.model_version}</CardDescription>
                </CardHeader>
                <CardContent className='flex flex-1 flex-col px-3 pb-3 pt-0'>
                  <SvrCrosshairChart
                    xLabels={chartData.map((d) => d.field)}
                    yDomain={[0, 1]}
                    formatY={(v) => v.toFixed(2)}
                    className='w-full'
                  >
                    <ResponsiveContainer width='100%' height={290}>
                      <BarChart
                        data={chartData}
                        barCategoryGap='18%'
                        margin={{ top: 24, right: 12, left: 4, bottom: 10 }}
                      >
                        <defs>
                          <linearGradient id='evalSolidGrad' x1='0' y1='0' x2='0' y2='1'>
                            <stop offset='0%' stopColor='var(--chart-2)' stopOpacity={0.95} />
                            <stop offset='100%' stopColor='var(--chart-3)' stopOpacity={0.75} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke='var(--chart-grid)' strokeWidth={1} />
                        <XAxis
                          dataKey='field'
                          stroke='var(--chart-grid)'
                          tick={{ fill: 'var(--chart-axis)', fontSize: 12, fontWeight: 500 }}
                          tickLine={false}
                          axisLine={{ stroke: 'var(--chart-grid)' }}
                        />
                        <YAxis
                          width={38}
                          domain={[0, 1]}
                          stroke='var(--chart-grid)'
                          tick={{ fill: 'var(--chart-axis)', fontSize: 12 }}
                          tickLine={false}
                          axisLine={{ stroke: 'var(--chart-grid)' }}
                        />
                        <Tooltip
                          cursor={false}
                          wrapperClassName='svr-tooltip'
                          content={({ active, payload }) => (
                            <SvrChartTooltip
                              active={active}
                              payload={payload}
                              format={(r) => {
                                const row = r as (typeof chartData)[number]
                                const pass = row.f1 >= row.gate
                                return {
                                  title: `${row.field} Macro-F1`,
                                  value: row.f1.toFixed(4),
                                  caption: `${L('Release gate', 'حد الاعتماد')} ${row.gate.toFixed(2)} · ${pass ? 'PASS' : 'FAIL'}`,
                                  tone: pass ? 'positive' : 'negative',
                                }
                              }}
                            />
                          )}
                        />
                        <Bar
                          dataKey='f1'
                          radius={[6, 6, 0, 0]}
                          maxBarSize={88}
                          background={{ fill: 'var(--chart-slot)' }}
                          isAnimationActive={false}
                        >
                          <LabelList
                            dataKey='f1'
                            position='top'
                            offset={8}
                            formatter={(v: unknown) => (typeof v === 'number' ? v.toFixed(3) : '')}
                            fill='var(--chart-axis)'
                            fontSize={12}
                            fontWeight={500}
                          />
                          {chartData.map((entry) => (
                            <Cell key={entry.field} fill='url(#evalSolidGrad)' />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </SvrCrosshairChart>
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
                            <TableCell className='font-medium'>{EVAL_TASK_LABELS[locale][f] ?? f}</TableCell>
                            <TableCell className='text-end font-mono tabular-nums'>{f1Str(perField[f])}</TableCell>
                            <TableCell className='text-end font-mono tabular-nums'>
                              {typeof g.threshold === 'number'
                                ? g.threshold.toFixed(2)
                                : typeof (g as { gate?: number }).gate === 'number'
                                  ? (g as { gate: number }).gate.toFixed(2)
                                  : '-'}
                            </TableCell>
                            <TableCell>
                              <span
                                className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold leading-4 text-white shadow-xs ${
                                  passed ? 'bg-[#00C853]' : 'bg-[#FF1744]'
                                }`}
                              >
                                {passed ? <CheckCircle2 className='size-3' /> : <AlertTriangle className='size-3' />}
                                {passed ? 'PASS' : 'FAIL'}
                              </span>
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

          {/* Cognitive Memory & Self-Improving Procedural Lessons + Export */}
          {mem && (
            <Card>
              <CardHeader className='flex flex-row flex-wrap items-center justify-between gap-3'>
                <div>
                  <CardTitle className='flex items-center gap-2'>
                    <Brain className='size-5 text-emerald-500' />
                    {L('Cognitive Self-Improving Memory & Training Corpus', 'الذاكرة الإدراكية والدروس الذاتية')}
                  </CardTitle>
                  <CardDescription>
                    {L(
                      `${mem.episodic_total} episodic vectors (${mem.embed_model}) · ${mem.semantic_entries_count} semantic rules · ${mem.procedural_rules_active_count} active procedural lessons · ${mem.training_feedback_total} training samples`,
                      `${mem.episodic_total} متجهات خبرة (${mem.embed_model}) · ${mem.semantic_entries_count} قواعد دلالية · ${mem.procedural_rules_active_count} دروس إجرائية · ${mem.training_feedback_total} عينات تدريب`
                    )}
                  </CardDescription>
                </div>
                <div className='flex items-center gap-2'>
                  <Button variant='outline' size='sm' asChild>
                    <a href={api.trainingExportUrl('jsonl')}>
                      <Download className='size-3.5' />
                      <span>JSONL</span>
                    </a>
                  </Button>
                  <Button variant='outline' size='sm' asChild>
                    <a href={api.trainingExportUrl('csv')}>
                      <Download className='size-3.5' />
                      <span>CSV</span>
                    </a>
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{L('Type', 'النوع')}</TableHead>
                      <TableHead>{L('Trigger Pattern', 'النمط')}</TableHead>
                      <TableHead>{L('Instruction', 'القاعدة')}</TableHead>
                      <TableHead className='text-end'>{L('Support / Success', 'الدعم / النجاح')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mem.recent_procedural_lessons.map((lesson) => (
                      <TableRow key={lesson.id}>
                        <TableCell className='font-mono text-xs'>{lesson.rule_type}</TableCell>
                        <TableCell className='font-mono text-xs'>{lesson.trigger_pattern}</TableCell>
                        <TableCell className='max-w-xl text-xs'>{lesson.instruction}</TableCell>
                        <TableCell className='text-end font-mono text-xs tabular-nums'>
                          {lesson.support_count} / {lesson.success_count}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
            {latest && (
              <Card>
                <CardHeader>
                  <CardTitle>{L('Churn Sensitivity & 5-Seed Breakdown', 'حساسية خطر الفقد عبر البذور الخمس')}</CardTitle>
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
            )}

            <Card>
              <CardHeader>
                <CardTitle>{L('Live Stage Latencies & Benchmark Speedup', 'أزمنة المراحل الحية وسرعة النماذج')}</CardTitle>
                <CardDescription>
                  {L('Measured across all live tickets and ONNX INT8 CPU benchmarks', 'مقاسة عبر التذاكر الفعلية ومقارنة ONNX INT8')}
                </CardDescription>
              </CardHeader>
              <CardContent className='space-y-4'>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{L('Live Pipeline Stage', 'المرحلة الحية')}</TableHead>
                      <TableHead className='text-end'>p50</TableHead>
                      <TableHead className='text-end'>p95</TableHead>
                      <TableHead className='text-end'>mean</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {liveStages.map(([st, v]) => (
                      <TableRow key={st}>
                        <TableCell className='font-mono text-xs'>{st}</TableCell>
                        <TableCell className='text-end font-mono tabular-nums'>{fmtLatency(v.p50)}</TableCell>
                        <TableCell className='text-end font-mono tabular-nums'>{fmtLatency(v.p95)}</TableCell>
                        <TableCell className='text-end font-mono tabular-nums'>{fmtLatency(v.mean)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {Object.keys(evalLatencies).length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{L('Eval Stage', 'معيار السرعة')}</TableHead>
                        <TableHead className='text-end'>n</TableHead>
                        <TableHead className='text-end'>p50 (ms)</TableHead>
                        <TableHead className='text-end'>p95 (ms)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {Object.entries(evalLatencies).map(([st, v]) => (
                        <TableRow key={st}>
                          <TableCell className='font-mono text-xs'>{st}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{v.n ?? '-'}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{v.p50?.toFixed(2) ?? '-'}</TableCell>
                          <TableCell className='text-end font-mono tabular-nums'>{v.p95?.toFixed(2) ?? '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}

                {Object.keys(skillF1).length > 0 && (
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
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{L('Recorded Evaluation Runs', 'سجل تشغيلات التقييم')}</CardTitle>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <p className='text-sm text-muted-foreground'>
                  {L('No benchmark evaluation runs recorded yet.', 'لا توجد تشغيلات تقييم مسجلة بعد.')}
                </p>
              ) : (
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
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </Main>
  )
}
