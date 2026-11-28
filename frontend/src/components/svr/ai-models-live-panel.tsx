import { Link } from '@tanstack/react-router'
import {
  Activity,
  AudioWaveform,
  Brain,
  Cpu,
  Database,
  GitBranch,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { type Locale, labelForCategory } from '@/lib/i18n'
import { formatPct, formatUtcTimestamp } from '@/lib/taxonomy'
import type { ModelsTelemetryResponse } from '@/lib/types'

interface AiModelsLivePanelProps {
  telemetry: ModelsTelemetryResponse | null
  locale: Locale
  wsConnected?: boolean
  onRefresh?: () => void
  compact?: boolean
}

function fmtMs(ms: number | undefined): string {
  if (ms === undefined || !Number.isFinite(ms) || ms <= 0) return '-'
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${Math.round(ms)}ms`
}

function StatusPill({ status, label }: { status: string; label?: string }) {
  const ok = status === 'online' || status === 'ok' || status === 'verified' || status === 'fast_verified'
  const warn = status === 'corrected' || status === 'adjudicated' || status === 'low_conf' || status === 'verify_only'
  const tone = ok
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-500'
    : warn
      ? 'border-sky-500/30 bg-sky-500/10 text-sky-400'
      : 'border-amber-500/30 bg-amber-500/10 text-amber-500'
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${tone}`}>
      <span className={`size-1.5 rounded-full ${ok ? 'bg-emerald-500' : warn ? 'bg-sky-400' : 'bg-amber-500'}`} />
      {label ?? status}
    </span>
  )
}

const HEAD_LABELS: Record<string, { en: string; ar: string }> = {
  complaint_category: { en: 'Category (11-cls)', ar: 'فئة الشكوى' },
  complaint_urgency: { en: 'Urgency (3-cls)', ar: 'الاستعجال' },
  customer_state: { en: 'Customer State (4-cls)', ar: 'حالة العميل' },
  churn_risk: { en: 'Churn Risk (2-cls)', ar: 'خطر الفقد' },
}

export function AiModelsLivePanel({
  telemetry,
  locale,
  wsConnected = false,
  onRefresh,
  compact = false,
}: AiModelsLivePanelProps) {
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  if (!telemetry) {
    return (
      <Card>
        <CardContent className='flex items-center justify-between py-6 text-sm text-muted-foreground'>
          <span>{L('Loading real-time AI model telemetry...', 'جاري تحميل قياسات النماذج الحية...')}</span>
        </CardContent>
      </Card>
    )
  }

  const { cohere_asr, marbert_v2, voicegate_orchestrator } = telemetry
  const mem = voicegate_orchestrator.memory

  return (
    <div className='space-y-4'>
      {/* Live Pipeline Pulse Strip */}
      <Card className='border-primary/20 bg-gradient-to-r from-card via-card to-muted/30'>
        <CardContent className='flex flex-wrap items-center justify-between gap-4 py-4'>
          <div className='flex items-center gap-3'>
            <div className='flex size-9 items-center justify-center rounded-lg border bg-background'>
              <Activity className='size-4 text-emerald-500' />
            </div>
            <div>
              <div className='flex flex-wrap items-center gap-2'>
                <span className='text-sm font-semibold'>
                  {L('Live Multi-Model AI Pipeline Telemetry', 'مراقبة منظومة نماذج الذكاء الاصطناعي الحية')}
                </span>
                <span className='inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-500'>
                  <span className={`size-1.5 rounded-full bg-emerald-500 ${wsConnected ? 'animate-pulse' : ''}`} />
                  {wsConnected ? L('Real-time Stream', 'بث مباشر') : L('Live DB', 'متصل')}
                </span>
              </div>
              <p className='mt-0.5 text-xs text-muted-foreground'>
                {L(
                  `Updated ${formatUtcTimestamp(telemetry.generated_at, locale)} · Active WS ${telemetry.active_ws_connections} · Last 3 results per model auto-refresh on every ticket`,
                  `آخر تحديث ${formatUtcTimestamp(telemetry.generated_at, locale)} · تحديث تلقائي لآخر 3 نتائج لكل نموذج مع كل تذكرة`
                )}
              </p>
            </div>
          </div>

          <div className='flex flex-wrap items-center gap-4 text-xs'>
            <div className='rounded-md border bg-background/70 px-3 py-1.5'>
              <div className='text-muted-foreground'>{L('Ready / Total', 'جاهزة / الإجمالي')}</div>
              <div className='font-mono text-sm font-bold tabular-nums'>
                {telemetry.ready_tickets} / {telemetry.total_tickets}
              </div>
            </div>
            <div className='rounded-md border bg-background/70 px-3 py-1.5'>
              <div className='text-muted-foreground'>{L('Escalated Review', 'تصعيد المراجعة')}</div>
              <div className='font-mono text-sm font-bold text-emerald-500 tabular-nums'>
                {formatPct(telemetry.escalated_human_review_rate, 1)} ({telemetry.escalated_human_review_count})
              </div>
            </div>
            <div className='rounded-md border bg-background/70 px-3 py-1.5'>
              <div className='text-muted-foreground'>{L('QA 5% Audit Sample', 'عينة التدقيق 5%')}</div>
              <div className='font-mono text-sm font-bold tabular-nums'>
                {telemetry.qa_sampled_count} / {telemetry.total_tickets} ({formatPct(telemetry.qa_sample_rate, 1)})
              </div>
            </div>
            <div className='rounded-md border bg-background/70 px-3 py-1.5'>
              <div className='text-muted-foreground'>{L('Mean Confidence', 'متوسط الثقة')}</div>
              <div className='font-mono text-sm font-bold tabular-nums'>
                {formatPct(telemetry.avg_confidence, 1)}
              </div>
            </div>
            <div className='rounded-md border bg-background/70 px-3 py-1.5'>
              <div className='text-muted-foreground'>{L('E2E p50 / p95', 'الزمن p50 / p95')}</div>
              <div className='font-mono text-sm font-bold tabular-nums' dir='ltr'>
                {fmtMs(telemetry.e2e_latency_ms.p50)} / {fmtMs(telemetry.e2e_latency_ms.p95)}
              </div>
            </div>
            {onRefresh && (
              <Button variant='outline' size='sm' onClick={onRefresh}>
                <RefreshCw className='size-3.5' />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 3 Advanced Model Subsystem Cards */}
      <div className='grid grid-cols-1 gap-4 xl:grid-cols-3'>
        {/* 1. Cohere Arabic ASR */}
        <Card className='flex flex-col'>
          <CardHeader className='pb-3'>
            <div className='flex items-start justify-between gap-2'>
              <div className='flex items-center gap-2.5'>
                <div className='flex size-8 items-center justify-center rounded-md border bg-muted/40'>
                  <AudioWaveform className='size-4 text-sky-400' />
                </div>
                <div>
                  <CardTitle className='text-base'>{cohere_asr.name}</CardTitle>
                  <CardDescription className='font-mono text-[11px]'>{cohere_asr.model_id}</CardDescription>
                </div>
              </div>
              <StatusPill status={cohere_asr.status} label={`${cohere_asr.device.toUpperCase()} · INT8`} />
            </div>
          </CardHeader>
          <CardContent className='flex flex-1 flex-col justify-between gap-4'>
            <div className='grid grid-cols-2 gap-2 text-xs'>
              <div className='rounded-md border bg-muted/20 p-2.5'>
                <div className='text-muted-foreground'>{L('Runs / Success', 'التشغيل / النجاح')}</div>
                <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums'>
                  {cohere_asr.total_runs} · {formatPct(cohere_asr.success_rate, 1)}
                </div>
              </div>
              <div className='rounded-md border bg-muted/20 p-2.5'>
                <div className='text-muted-foreground'>{L('Latency p50 / p95', 'الزمن p50 / p95')}</div>
                <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums' dir='ltr'>
                  {fmtMs(cohere_asr.latency_ms.p50)} / {fmtMs(cohere_asr.latency_ms.p95)}
                </div>
              </div>
              <div className='rounded-md border bg-muted/20 p-2.5'>
                <div className='text-muted-foreground'>{L('Avg Logprob', 'متوسط Logprob')}</div>
                <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums' dir='ltr'>
                  {cohere_asr.avg_logprob !== null && cohere_asr.avg_logprob !== undefined
                    ? cohere_asr.avg_logprob.toFixed(3)
                    : '-'}
                </div>
              </div>
              <div className='rounded-md border bg-muted/20 p-2.5'>
                <div className='text-muted-foreground'>{L('Avg Silence / Flagged', 'الصمت / التنبيه')}</div>
                <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums' dir='ltr'>
                  {cohere_asr.avg_no_speech_prob !== null && cohere_asr.avg_no_speech_prob !== undefined
                    ? cohere_asr.avg_no_speech_prob.toFixed(2)
                    : '-'}{' '}
                  · {formatPct(cohere_asr.flagged_rate, 1)}
                </div>
              </div>
            </div>

            <div className='space-y-2'>
              <div className='flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted-foreground'>
                <span>{L('Last 3 Transcriptions', 'آخر 3 تفريغات صوتية')}</span>
                <span className='font-mono'>{cohere_asr.backend}</span>
              </div>
              {cohere_asr.recent_results.length === 0 ? (
                <p className='rounded-md border border-dashed p-3 text-xs text-muted-foreground'>
                  {L('No transcriptions yet.', 'لا توجد تفريغات بعد.')}
                </p>
              ) : (
                <div className='space-y-2'>
                  {cohere_asr.recent_results.map((item) => (
                    <Link
                      key={item.ticket_id}
                      to='/tickets/$id'
                      params={{ id: item.ticket_id }}
                      className='block rounded-md border p-2.5 transition-colors hover:bg-muted/50'
                    >
                      <div className='flex items-center justify-between gap-2 text-[11px]'>
                        <span className='truncate font-mono font-semibold'>{item.file_name}</span>
                        <div className='flex shrink-0 items-center gap-1.5'>
                          <StatusPill status={item.status} />
                          <span className='font-mono text-muted-foreground tabular-nums'>
                            {fmtMs(item.latency_ms)}
                          </span>
                        </div>
                      </div>
                      <p className='mt-1 line-clamp-2 text-xs text-foreground/90' dir='auto'>
                        {item.transcript_preview || '-'}
                      </p>
                      <div className='mt-1.5 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums'>
                        <span dir='ltr'>
                          logprob: {item.min_avg_logprob !== null && item.min_avg_logprob !== undefined ? item.min_avg_logprob.toFixed(3) : '-'} · nsp:{' '}
                          {item.max_no_speech_prob !== null && item.max_no_speech_prob !== undefined ? item.max_no_speech_prob.toFixed(2) : '-'}
                        </span>
                        <span className='font-mono'>#{item.ticket_id.slice(0, 8)}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 2. MARBERTv2 4-Head Classifier */}
        <Card className='flex flex-col'>
          <CardHeader className='pb-3'>
            <div className='flex items-start justify-between gap-2'>
              <div className='flex items-center gap-2.5'>
                <div className='flex size-8 items-center justify-center rounded-md border bg-muted/40'>
                  <Cpu className='size-4 text-violet-400' />
                </div>
                <div>
                  <CardTitle className='text-base'>{marbert_v2.name}</CardTitle>
                  <CardDescription className='font-mono text-[11px]'>{marbert_v2.model_id}</CardDescription>
                </div>
              </div>
              <StatusPill status={marbert_v2.status} label={marbert_v2.backend.toUpperCase()} />
            </div>
          </CardHeader>
          <CardContent className='flex flex-1 flex-col justify-between gap-4'>
            <div className='space-y-3'>
              <div className='grid grid-cols-3 gap-2 text-xs'>
                <div className='rounded-md border bg-muted/20 p-2'>
                  <div className='text-muted-foreground'>{L('Runs', 'التشغيل')}</div>
                  <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums'>{marbert_v2.total_runs}</div>
                </div>
                <div className='rounded-md border bg-muted/20 p-2'>
                  <div className='text-muted-foreground'>{L('Avg Conf', 'متوسط الثقة')}</div>
                  <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums'>
                    {formatPct(marbert_v2.avg_confidence, 1)}
                  </div>
                </div>
                <div className='rounded-md border bg-muted/20 p-2'>
                  <div className='text-muted-foreground'>{L('p50 / p95', 'p50 / p95')}</div>
                  <div className='mt-0.5 font-mono text-xs font-semibold tabular-nums' dir='ltr'>
                    {fmtMs(marbert_v2.latency_ms.p50)} / {fmtMs(marbert_v2.latency_ms.p95)}
                  </div>
                </div>
              </div>

              {!compact && (
                <div className='space-y-2 rounded-md border bg-muted/15 p-2.5'>
                  <div className='text-[11px] font-semibold uppercase tracking-wider text-muted-foreground'>
                    {L('Per-Head Mean Confidence', 'متوسط ثقة كل نموذج فرعي')}
                  </div>
                  {(['complaint_category', 'complaint_urgency', 'customer_state', 'churn_risk'] as const).map((field) => {
                    const val = marbert_v2.per_head_avg_confidence[field] ?? 0
                    return (
                      <div key={field} className='space-y-1'>
                        <div className='flex items-center justify-between text-[11px]'>
                          <span>{HEAD_LABELS[field][locale]}</span>
                          <span className='font-mono font-semibold tabular-nums'>{formatPct(val, 1)}</span>
                        </div>
                        <div className='h-1.5 w-full overflow-hidden rounded-full bg-muted'>
                          <div
                            className='h-full rounded-full bg-violet-500'
                            style={{ width: `${Math.min(100, Math.round(val * 100))}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div className='space-y-2'>
              <div className='flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted-foreground'>
                <span>{L('Last 3 Classifications', 'آخر 3 تصنيفات')}</span>
                <span className='font-mono'>
                  {L('Below thresh', 'أقل من الحد')}: {formatPct(marbert_v2.below_threshold_rate, 1)}
                </span>
              </div>
              {marbert_v2.recent_results.length === 0 ? (
                <p className='rounded-md border border-dashed p-3 text-xs text-muted-foreground'>
                  {L('No classifications yet.', 'لا توجد تصنيفات بعد.')}
                </p>
              ) : (
                <div className='space-y-2'>
                  {marbert_v2.recent_results.map((item) => (
                    <Link
                      key={item.ticket_id}
                      to='/tickets/$id'
                      params={{ id: item.ticket_id }}
                      className='block rounded-md border p-2.5 transition-colors hover:bg-muted/50'
                    >
                      <div className='flex items-center justify-between gap-2 text-[11px]'>
                        <span className='truncate font-medium'>
                          {labelForCategory(item.complaint_category, locale)}
                        </span>
                        <div className='flex shrink-0 items-center gap-1.5'>
                          <span className='font-mono font-semibold text-emerald-500 tabular-nums'>
                            {formatPct(item.confidence, 1)}
                          </span>
                          <span className='font-mono text-muted-foreground tabular-nums'>
                            {fmtMs(item.latency_ms)}
                          </span>
                        </div>
                      </div>
                      <div className='mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px]'>
                        <span className='rounded bg-muted px-1.5 py-0.5 font-mono'>{item.complaint_urgency ?? '-'}</span>
                        <span className='rounded bg-muted px-1.5 py-0.5 font-mono'>{item.customer_state ?? '-'}</span>
                        <span
                          className={`rounded px-1.5 py-0.5 font-mono ${
                            item.churn_risk === 'at_risk'
                              ? 'bg-destructive/15 text-destructive'
                              : 'bg-muted text-muted-foreground'
                          }`}
                        >
                          {item.churn_risk ?? '-'}
                        </span>
                        <span className='ms-auto font-mono text-muted-foreground'>
                          {item.file_name} · #{item.ticket_id.slice(0, 8)}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 3. VoiceGate Cognitive Orchestrator */}
        <Card className='flex flex-col'>
          <CardHeader className='pb-3'>
            <div className='flex items-start justify-between gap-2'>
              <div className='flex items-center gap-2.5'>
                <div className='flex size-8 items-center justify-center rounded-md border bg-muted/40'>
                  <Brain className='size-4 text-emerald-500' />
                </div>
                <div>
                  <CardTitle className='text-base'>{voicegate_orchestrator.name}</CardTitle>
                  <CardDescription className='font-mono text-[11px]'>
                    {voicegate_orchestrator.model_id} + {voicegate_orchestrator.embed_model}
                  </CardDescription>
                </div>
              </div>
              <StatusPill status={voicegate_orchestrator.status} label='LANGGRAPH · 4-MEM' />
            </div>
          </CardHeader>
          <CardContent className='flex flex-1 flex-col justify-between gap-4'>
            <div className='space-y-3'>
              <div className='grid grid-cols-3 gap-2 text-xs'>
                <div className='rounded-md border bg-muted/20 p-2'>
                  <div className='text-muted-foreground'>{L('Fast / Adj', 'سريع / تدقيق')}</div>
                  <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums'>
                    {voicegate_orchestrator.fast_verified_count} / {voicegate_orchestrator.adjudicated_count}
                  </div>
                </div>
                <div className='rounded-md border bg-muted/20 p-2'>
                  <div className='text-muted-foreground'>{L('Agree / Fix', 'تطابق / تصحيح')}</div>
                  <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums'>
                    {formatPct(voicegate_orchestrator.agreement_rate, 0)} · {voicegate_orchestrator.override_count}
                  </div>
                </div>
                <div className='rounded-md border bg-muted/20 p-2'>
                  <div className='text-muted-foreground'>{L('Adj p50', 'زمن التحكيم')}</div>
                  <div className='mt-0.5 font-mono text-sm font-semibold tabular-nums' dir='ltr'>
                    {fmtMs(voicegate_orchestrator.adjudicate_latency_ms.p50)}
                  </div>
                </div>
              </div>

              {!compact && (
                <div className='grid grid-cols-4 gap-1.5 rounded-md border bg-muted/15 p-2 text-center text-[11px]'>
                  <div>
                    <div className='flex items-center justify-center gap-1 text-muted-foreground'>
                      <Database className='size-3' /> Ep
                    </div>
                    <div className='font-mono font-bold tabular-nums'>{mem.episodic_total}</div>
                  </div>
                  <div>
                    <div className='flex items-center justify-center gap-1 text-muted-foreground'>
                      <GitBranch className='size-3' /> Sem
                    </div>
                    <div className='font-mono font-bold tabular-nums'>{mem.semantic_entries_count}</div>
                  </div>
                  <div>
                    <div className='flex items-center justify-center gap-1 text-muted-foreground'>
                      <Sparkles className='size-3' /> Proc
                    </div>
                    <div className='font-mono font-bold tabular-nums'>{mem.procedural_rules_active_count}</div>
                  </div>
                  <div>
                    <div className='flex items-center justify-center gap-1 text-muted-foreground'>
                      <ShieldCheck className='size-3' /> Train
                    </div>
                    <div className='font-mono font-bold tabular-nums'>{mem.training_feedback_total}</div>
                  </div>
                </div>
              )}
            </div>

            <div className='space-y-2'>
              <div className='flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted-foreground'>
                <span>{L('Last 3 Orchestrator Decisions', 'آخر 3 قرارات للمنسق الذكي')}</span>
                <span className='font-mono'>
                  {L('Repaired', 'مصلح')}: {voicegate_orchestrator.repaired_count}
                </span>
              </div>
              {voicegate_orchestrator.recent_results.length === 0 ? (
                <p className='rounded-md border border-dashed p-3 text-xs text-muted-foreground'>
                  {L('No orchestrator decisions yet.', 'لا توجد قرارات بعد.')}
                </p>
              ) : (
                <div className='space-y-2'>
                  {voicegate_orchestrator.recent_results.map((item) => (
                    <Link
                      key={item.ticket_id}
                      to='/tickets/$id'
                      params={{ id: item.ticket_id }}
                      className='block rounded-md border p-2.5 transition-colors hover:bg-muted/50'
                    >
                      <div className='flex items-center justify-between gap-2 text-[11px]'>
                        <div className='flex items-center gap-1.5'>
                          <StatusPill status={item.adjudicator_mode} />
                          <span className='rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]'>
                            gate:{item.gate_status}
                          </span>
                        </div>
                        <span className='font-mono text-muted-foreground tabular-nums'>
                          {fmtMs(item.latency_ms)}
                        </span>
                      </div>
                      <p className='mt-1 truncate text-xs text-muted-foreground'>
                        {item.assigned_agent_name ?? L('Unassigned', 'غير معين')} ·{' '}
                        {item.memory_episodes_used} {L('ep', 'تجربة')} (sim{' '}
                        {item.max_episode_similarity.toFixed(2)}) · {formatPct(item.calibrated_confidence, 1)}
                      </p>
                      <div className='mt-1 flex items-center justify-between gap-2 text-[11px] text-muted-foreground'>
                        <span className='truncate'>
                          {item.changed_fields.length > 0
                            ? `${L('Adjusted', 'عدل')}: ${item.changed_fields.join(', ')}`
                            : item.reasoning_preview || L('Verified aligned', 'تحقق متطابق')}
                        </span>
                        <span className='shrink-0 font-mono'>#{item.ticket_id.slice(0, 8)}</span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
