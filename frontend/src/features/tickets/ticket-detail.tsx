import { useCallback, useEffect, useState } from 'react'
import { Link } from '@tanstack/react-router'
import {
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  Bot,
  Check,
  ChevronDown,
  Copy,
  RefreshCw,
  UserCheck,
  Volume2,
} from 'lucide-react'
import { toast } from 'sonner'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
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
import { Textarea } from '@/components/ui/textarea'
import { Main } from '@/components/layout/main'
import { BucketText, PriorityScoreAvatar, TicketStatusText } from '@/components/svr/status-badges'
import { VoicemailAudioPlayer } from '@/components/svr/voicemail-audio-player'
import { api, apiUrl, ApiError } from '@/lib/api'
import {
  UI_COPY,
  labelForCategory,
  labelForChurn,
  labelForReviewReason,
  labelForState,
  labelForStatus,
  labelForUrgency,
} from '@/lib/i18n'
import {
  CHURN_RISKS,
  COMPLAINT_CATEGORIES,
  COMPLAINT_URGENCIES,
  CUSTOMER_STATES,
  formatDuration,
  formatPct,
  formatUtcTimestamp,
} from '@/lib/taxonomy'
import type {
  AgentResponse,
  CorrectionPreviewResponse,
  TicketDetail,
} from '@/lib/types'

const FIELD_ORDER = [
  'complaint_category',
  'complaint_urgency',
  'customer_state',
  'churn_risk',
] as const

export function TicketDetailPage({ ticketId }: { ticketId: string }) {
  const { user, locale, wsVersion, refreshReviewBadge } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [ticket, setTicket] = useState<TicketDetail | null>(null)
  const [agents, setAgents] = useState<AgentResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)

  const [editCat, setEditCat] = useState('')
  const [editUrg, setEditUrg] = useState('')
  const [editState, setEditState] = useState('')
  const [editChurn, setEditChurn] = useState('')
  const [editNote, setEditNote] = useState('')
  const [preview, setPreview] = useState<CorrectionPreviewResponse | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)

  const [reassignAgentId, setReassignAgentId] = useState('none')
  const [reassignNote, setReassignNote] = useState('')

  const isSupervisorOrAdmin = user?.role === 'supervisor' || user?.role === 'admin'

  const load = useCallback(async () => {
    setError(null)
    try {
      const detail = await api.getTicket(ticketId)
      setTicket(detail)
      setEditCat(detail.complaint_category || '')
      setEditUrg(detail.complaint_urgency || '')
      setEditState(detail.customer_state || '')
      setEditChurn(detail.churn_risk || '')
      setReassignAgentId(detail.assigned_agent_id || 'none')
      setPreview(null)
      if (isSupervisorOrAdmin) {
        const ag = await api.listAgents()
        setAgents(ag.filter((a) => a.active))
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load ticket.')
    } finally {
      setLoading(false)
    }
  }, [ticketId, isSupervisorOrAdmin])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (wsVersion > 0) void load()
  }, [wsVersion, load])

  const handleCopyScript = async () => {
    if (!ticket?.suggested_script) return
    try {
      await navigator.clipboard.writeText(ticket.suggested_script)
      setCopied(true)
      toast.success(L('Opening script copied.', 'تم نسخ جملة الافتتاح.'))
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(L('Clipboard copy failed.', 'تعذر النسخ إلى الحافظة.'))
    }
  }

  const handlePreview = async () => {
    if (!ticket) return
    setBusy(true)
    try {
      const res = await api.previewCorrection(ticket.id, {
        complaint_category: editCat || null,
        complaint_urgency: editUrg || null,
        customer_state: editState || null,
        churn_risk: editChurn || null,
      })
      setPreview(res)
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Preview failed.')
    } finally {
      setBusy(false)
    }
  }

  const handleApplyCorrection = async () => {
    if (!ticket) return
    setBusy(true)
    setConfirmOpen(false)
    try {
      await api.applyCorrection(ticket.id, {
        complaint_category: editCat || null,
        complaint_urgency: editUrg || null,
        customer_state: editState || null,
        churn_risk: editChurn || null,
        apply_recommended_route: true,
        clear_human_review: true,
        note: editNote.trim() || undefined,
      })
      toast.success(
        L(
          'Correction saved with human label provenance and audit record.',
          'تم حفظ التصحيح مع توثيق المصدر البشري وسجل التدقيق.'
        )
      )
      setEditNote('')
      await Promise.all([load(), refreshReviewBadge()])
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Correction failed.')
    } finally {
      setBusy(false)
    }
  }

  const handleReassign = async (unassign: boolean) => {
    if (!ticket) return
    setBusy(true)
    try {
      await api.patchTicket(ticket.id, {
        assigned_agent_id: unassign || reassignAgentId === 'none' ? undefined : reassignAgentId,
        unassign,
        needs_human_review: false,
        note: reassignNote.trim() || undefined,
      })
      toast.success(
        unassign
          ? L('Ticket returned to Unassigned.', 'تمت إعادة التذكرة لقائمة بدون موظف.')
          : L('Ticket reassigned.', 'تم إعادة توجيه التذكرة.')
      )
      setReassignNote('')
      await Promise.all([load(), refreshReviewBadge()])
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Reassignment failed.')
    } finally {
      setBusy(false)
    }
  }

  const handleStatusChange = async (status: string) => {
    if (!ticket) return
    setBusy(true)
    try {
      await api.patchTicket(ticket.id, { status })
      toast.success(L(`Ticket moved to ${labelForStatus(status, locale)}.`, 'تم تحديث حالة التذكرة.'))
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Status update failed.')
    } finally {
      setBusy(false)
    }
  }

  const backHref = user?.role === 'agent' ? '/my-tickets' : '/dashboard'

  if (loading && !ticket) {
    return (
      <Main>
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      </Main>
    )
  }

  if (error || !ticket) {
    return (
      <Main>
        <Alert variant='destructive'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error || 'Ticket not found.'}</AlertDescription>
        </Alert>
        <Button variant='outline' className='mt-4' asChild>
          <Link to={backHref}>
            <ArrowLeft className='size-4' />
            {L('Back to Queue', 'العودة للقائمة')}
          </Link>
        </Button>
      </Main>
    )
  }

  const fieldMeta: Record<string, { title: string; value: string; probs: Record<string, number> }> = {
    complaint_category: {
      title: L('Complaint Category', 'نوع الشكوى'),
      value: labelForCategory(ticket.complaint_category, locale),
      probs: ticket.probabilities?.complaint_category || {},
    },
    complaint_urgency: {
      title: L('Complaint Urgency', 'مستوى الاستعجال'),
      value: labelForUrgency(ticket.complaint_urgency, locale),
      probs: ticket.probabilities?.complaint_urgency || {},
    },
    customer_state: {
      title: L('Customer State', 'حالة العميل'),
      value: labelForState(ticket.customer_state, locale),
      probs: ticket.probabilities?.customer_state || {},
    },
    churn_risk: {
      title: L('Churn Risk', 'خطر فقد العميل'),
      value: labelForChurn(ticket.churn_risk, locale),
      probs: ticket.probabilities?.churn_risk || {},
    },
  }

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-start justify-between gap-3'>
        <div className='flex items-start gap-3'>
          <PriorityScoreAvatar score={ticket.priority_score} bucket={ticket.queue_priority} size='lg' />
          <div>
            <div className='flex flex-wrap items-center gap-2'>
              <h1 className='text-2xl font-bold tracking-tight'>
                {ticket.complaint_category
                  ? labelForCategory(ticket.complaint_category, locale)
                  : L('Unclassified Ticket', 'تذكرة غير مصنفة')}{' '}
                <span className='font-mono text-base font-normal text-muted-foreground'>
                  #{ticket.id.slice(0, 8)}
                </span>
              </h1>
              <TicketStatusText status={ticket.status} locale={locale} />
              <BucketText bucket={ticket.queue_priority} locale={locale} />
            </div>
            <p className='mt-1 text-xs text-muted-foreground'>
              <span className='font-mono'>{ticket.file_name}</span> ·{' '}
              {formatDuration(ticket.duration_seconds)} ·{' '}
              {L('Agent:', 'الموظف:')} <strong>{ticket.assigned_agent_name || t.unassignedOption}</strong> ·{' '}
              {L('Confidence:', 'الثقة:')}{' '}
              <strong className='tabular-nums'>{formatPct(ticket.confidence)}</strong> /{' '}
              {formatPct(ticket.confidence_threshold_snapshot, 0)} ·{' '}
              {formatUtcTimestamp(ticket.created_at, locale)}
            </p>
          </div>
        </div>

        <div className='flex flex-wrap items-center gap-2'>
          <Button variant='outline' size='sm' asChild>
            <Link to={backHref}>
              <ArrowLeft className='size-4' />
              {L('Back', 'رجوع')}
            </Link>
          </Button>
          <Button variant='outline' size='sm' onClick={() => void load()} disabled={busy}>
            <RefreshCw className='size-4' />
            {L('Refresh', 'تحديث')}
          </Button>
          {ticket.status === 'ready' && (
            <Button size='sm' disabled={busy} onClick={() => void handleStatusChange('in_progress')}>
              {L('Start Callback', 'بدء معاودة الاتصال')}
            </Button>
          )}
          {(ticket.status === 'ready' || ticket.status === 'in_progress') && (
            <Button size='sm' variant='outline' disabled={busy} onClick={() => void handleStatusChange('resolved')}>
              {L('Mark Resolved', 'تم الحل')}
            </Button>
          )}
          {ticket.status === 'resolved' && isSupervisorOrAdmin && (
            <Button size='sm' variant='outline' disabled={busy} onClick={() => void handleStatusChange('closed')}>
              {L('Close Ticket', 'إغلاق التذكرة')}
            </Button>
          )}
        </div>
      </div>

      {ticket.needs_human_review && (
        <Alert className='mb-4 border-amber-500/40 bg-amber-500/10'>
          <AlertTriangle className='size-4 text-amber-600' />
          <AlertDescription>
            <strong>{L('Flagged for Human Review:', 'محولة للمراجعة البشرية:')}</strong>{' '}
            {labelForReviewReason(ticket.review_reason, locale)}
          </AlertDescription>
        </Alert>
      )}

      {/* Audio Playback */}
      <Card className='mb-4'>
        <CardContent className='flex flex-wrap items-center gap-4 pt-4'>
          <div className='flex items-center gap-2 text-sm font-medium'>
            <Volume2 className='size-4 text-muted-foreground' />
            <span>
              {L('Subscriber Voicemail Audio', 'تسجيل الرسالة الصوتية')} ({ticket.format.toUpperCase()} ·{' '}
              {formatDuration(ticket.duration_seconds)} · {(ticket.size_bytes / 1024).toFixed(1)} KB)
            </span>
          </div>
          <VoicemailAudioPlayer
            src={apiUrl(ticket.audio_url)}
            initialDurationSeconds={ticket.duration_seconds}
            className='min-w-[280px] flex-1'
          />
        </CardContent>
      </Card>

      {/* Brief & Arabic Transcript */}
      <div className='mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2'>
        <Card>
          <CardHeader>
            <CardTitle>{L('Subscriber Callback Brief', 'ملخص معاودة الاتصال')}</CardTitle>
            <CardDescription>
              {L('Generated from voicemail details and approved response templates', 'مبني على تفاصيل الرسالة وقوالب الرد المعتمدة')}
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-3 text-sm'>
            <div>
              <div className='text-xs font-semibold uppercase text-muted-foreground'>
                {L('Customer Request', 'طلب المشترك')}
              </div>
              <p className='mt-1' dir='auto'>{ticket.customer_request || '-'}</p>
            </div>
            <div className='border-t pt-3'>
              <div className='text-xs font-semibold uppercase text-muted-foreground'>
                {L('Summary', 'الملخص')}
              </div>
              <p className='mt-1' dir='auto'>{ticket.summary || '-'}</p>
            </div>
            <div className='border-t pt-3'>
              <div className='flex items-center justify-between gap-2'>
                <span className='text-xs font-semibold uppercase text-muted-foreground'>
                  {L('Suggested Opening Script', 'جملة الافتتاح المقترحة')}
                </span>
                <Button
                  type='button'
                  variant='outline'
                  size='sm'
                  disabled={!ticket.suggested_script}
                  onClick={() => void handleCopyScript()}
                >
                  {copied ? <Check className='size-3.5' /> : <Copy className='size-3.5' />}
                  {copied ? L('Copied', 'تم النسخ') : L('Copy Script', 'نسخ')}
                </Button>
              </div>
              <p className='mt-2 rounded-md border bg-muted/40 p-3 text-base leading-relaxed' dir='rtl'>
                {ticket.suggested_script || '-'}
              </p>
            </div>
            <div className='border-t pt-3 text-xs text-muted-foreground'>
              <div><strong>{L('Priority rationale:', 'سبب الأولوية:')}</strong> {ticket.priority_reason || '-'}</div>
              <div className='mt-1'><strong>{L('Routing rationale:', 'سبب التوجيه:')}</strong> {ticket.route_reason || '-'}</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{L('Arabic Transcript (Whisper large-v3)', 'النص الصوتي (Whisper large-v3)')}</CardTitle>
            <CardDescription>{L('Local self-hosted speech recognition', 'تفريغ صوتي محلي بالكامل')}</CardDescription>
          </CardHeader>
          <CardContent className='space-y-3'>
            <p
              className='rounded-md border bg-muted/40 p-4 text-base leading-loose'
              dir={ticket.transcript ? 'rtl' : 'ltr'}
            >
              {ticket.transcript || L('No transcript available.', 'لا يوجد نص متاح.')}
            </p>
            {ticket.text_norm && ticket.text_norm !== ticket.transcript && (
              <div className='text-xs text-muted-foreground'>
                <span className='font-semibold'>text_norm:</span>{' '}
                <span dir='rtl'>{ticket.text_norm}</span>
              </div>
            )}
            {ticket.stt_v1_json && (
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <Button variant='ghost' size='sm' className='gap-1 px-2 text-xs'>
                    <ChevronDown className='size-3.5' />
                    {L('Whisper STT v1 Metadata (10 columns)', 'بيانات Whisper STT v1')}
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className='mt-2 rounded-md border p-3'>
                  <dl className='grid grid-cols-2 gap-x-4 gap-y-1 text-xs'>
                    {Object.entries(ticket.stt_v1_json).map(([k, v]) => (
                      <div key={k} className='contents'>
                        <dt className='font-mono text-muted-foreground'>{k}</dt>
                        <dd className='truncate font-mono'>{String(v ?? '-')}</dd>
                      </div>
                    ))}
                  </dl>
                </CollapsibleContent>
              </Collapsible>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 4 Independent MARBERTv2 Fields */}
      <Card className='mb-4'>
        <CardHeader>
          <CardTitle>{L('Four Independent MARBERTv2 Fields & Probabilities', 'الحقول الأربعة المصنفة والاحتمالات')}</CardTitle>
          <CardDescription>
            {L('Model:', 'النموذج:')} <span className='font-mono'>{ticket.model_version || 'pending'}</span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className='grid grid-cols-1 gap-4 md:grid-cols-2'>
            {FIELD_ORDER.map((fieldKey) => {
              const info = fieldMeta[fieldKey]
              const src = ticket.label_sources?.[fieldKey] || 'ai'
              const sorted = Object.entries(info.probs).sort((a, b) => b[1] - a[1])
              return (
                <div key={fieldKey} className='rounded-lg border p-4'>
                  <div className='flex items-center justify-between gap-2'>
                    <span className='text-xs font-semibold uppercase text-muted-foreground'>
                      {info.title}
                    </span>
                    <Badge variant={src === 'human' ? 'default' : 'secondary'} className='gap-1 text-[11px]'>
                      {src === 'human' ? <UserCheck className='size-3' /> : <Bot className='size-3' />}
                      {src === 'human' ? L('Human', 'بشري') : L('AI', 'آلي')}
                    </Badge>
                  </div>
                  <div className='mt-1 mb-3 text-base font-bold'>{info.value}</div>
                  {sorted.length === 0 ? (
                    <p className='text-xs text-muted-foreground'>
                      {L('No probabilities recorded.', 'لا توجد احتمالات مسجلة.')}
                    </p>
                  ) : (
                    <div className='space-y-1.5'>
                      {sorted.slice(0, 5).map(([cls, p], idx) => (
                        <div key={cls} className='grid grid-cols-[1fr_minmax(60px,120px)_48px] items-center gap-2 text-xs'>
                          <span className='truncate text-muted-foreground'>{cls}</span>
                          <div className='h-2 overflow-hidden rounded-full bg-muted'>
                            <div
                              className={`h-full ${idx === 0 ? 'bg-primary' : 'bg-muted-foreground/40'}`}
                              style={{ width: `${Math.max(2, Math.round(p * 100))}%` }}
                            />
                          </div>
                          <span className='text-end font-mono tabular-nums'>{formatPct(p, 1)}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Supervisor Label Correction & Reassignment */}
      {isSupervisorOrAdmin && (
        <div className='mb-4 grid grid-cols-1 gap-4 lg:grid-cols-2'>
          <Card>
            <CardHeader>
              <CardTitle>{L('Supervisor Label Correction', 'تصحيح التصنيفات (المشرف)')}</CardTitle>
              <CardDescription>
                {L('Preview priority and routing impact before committing', 'معاينة أثر التعديل قبل الحفظ')}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3'>
              <div className='grid grid-cols-1 gap-3 sm:grid-cols-2'>
                <div className='grid gap-1.5'>
                  <Label>{L('Category', 'الفئة')}</Label>
                  <Select value={editCat} onValueChange={setEditCat}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {COMPLAINT_CATEGORIES.map((c) => (
                        <SelectItem key={c} value={c}>{labelForCategory(c, locale)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className='grid gap-1.5'>
                  <Label>{L('Urgency', 'الاستعجال')}</Label>
                  <Select value={editUrg} onValueChange={setEditUrg}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {COMPLAINT_URGENCIES.map((u) => (
                        <SelectItem key={u} value={u}>{labelForUrgency(u, locale)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className='grid gap-1.5'>
                  <Label>{L('Customer State', 'حالة العميل')}</Label>
                  <Select value={editState} onValueChange={setEditState}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CUSTOMER_STATES.filter((st) => st !== 'unclear').map((st: string) => (
                        <SelectItem key={st} value={st}>{labelForState(st, locale)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className='grid gap-1.5'>
                  <Label>{L('Churn Risk', 'خطر الفقد')}</Label>
                  <Select value={editChurn} onValueChange={setEditChurn}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {CHURN_RISKS.map((ch) => (
                        <SelectItem key={ch} value={ch}>{labelForChurn(ch, locale)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className='grid gap-1.5'>
                <Label>{L('Supervisor Note', 'ملاحظة المشرف')}</Label>
                <Textarea
                  value={editNote}
                  onChange={(ev) => setEditNote(ev.target.value)}
                  placeholder={L('Optional audit note...', 'ملاحظة اختيارية لسجل التدقيق...')}
                />
              </div>

              {preview && (
                <Alert>
                  <AlertDescription className='space-y-1 text-xs'>
                    <div>
                      <strong>{L('Preview Priority:', 'الأولوية المتوقعة:')}</strong>{' '}
                      {preview.priority_score ?? '-'} ({preview.queue_priority || '-'})
                    </div>
                    <div>
                      <strong>{L('Recommended Agent:', 'الموظف المقترح:')}</strong>{' '}
                      {preview.recommended_agent_name || t.unassignedOption}
                    </div>
                    <div className='text-muted-foreground'>{preview.route_reason}</div>
                  </AlertDescription>
                </Alert>
              )}

              <div className='flex flex-wrap gap-2'>
                <Button type='button' variant='outline' disabled={busy} onClick={() => void handlePreview()}>
                  {L('Preview Priority & Route', 'معاينة الأولوية والتوجيه')}
                </Button>
                <Button type='button' disabled={busy} onClick={() => setConfirmOpen(true)}>
                  {L('Confirm & Save Correction', 'تأكيد وحفظ التصحيح')}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{L('Manual Agent Reassignment', 'إعادة التوجيه اليدوي')}</CardTitle>
              <CardDescription>
                {L('Assign directly or return to Unassigned', 'تعيين لموظف أو إعادة لبدون موظف')}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3'>
              <div className='grid gap-1.5'>
                <Label>{L('Target Agent', 'الموظف المستهدف')}</Label>
                <Select value={reassignAgentId} onValueChange={setReassignAgentId}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value='none'>{t.unassignedOption}</SelectItem>
                    {agents.map((a) => (
                      <SelectItem key={a.id} value={a.id}>
                        {a.name} ({a.current_load}/{a.capacity})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className='grid gap-1.5'>
                <Label>{L('Reassignment Reason', 'سبب التوجيه')}</Label>
                <Textarea
                  value={reassignNote}
                  onChange={(ev) => setReassignNote(ev.target.value)}
                  placeholder={L('Reason recorded in Audit Log...', 'سبب التوجيه لسجل التدقيق...')}
                />
              </div>

              <div className='flex flex-wrap gap-2'>
                <Button type='button' disabled={busy || reassignAgentId === 'none'} onClick={() => void handleReassign(false)}>
                  {L('Apply Reassignment', 'حفظ التوجيه')}
                </Button>
                <Button type='button' variant='outline' disabled={busy} onClick={() => void handleReassign(true)}>
                  {L('Unassign Ticket', 'إلغاء التعيين')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* AI Logs & Audit Timeline */}
      <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
        <Card>
          <CardHeader>
            <CardTitle>{L('AI Pipeline Interaction Log', 'سجل مراحل الذكاء الاصطناعي')}</CardTitle>
          </CardHeader>
          <CardContent className='overflow-x-auto'>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{L('Stage', 'المرحلة')}</TableHead>
                  <TableHead>{L('Status', 'الحالة')}</TableHead>
                  <TableHead className='text-end'>{L('Latency', 'الزمن')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ticket.ai_logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className='font-mono text-xs whitespace-nowrap'>{log.stage}</TableCell>
                    <TableCell className='max-w-[200px] truncate text-xs' title={log.model}>{log.model}</TableCell>
                    <TableCell className='text-end font-mono text-xs whitespace-nowrap tabular-nums'>
                      {log.latency_ms.toFixed(1)} ms
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{L('Ticket Audit Timeline', 'سجل تدقيق التذكرة')}</CardTitle>
          </CardHeader>
          <CardContent>
            {ticket.audit_events.length === 0 ? (
              <p className='text-sm text-muted-foreground'>{L('No audit events yet.', 'لا توجد أحداث بعد.')}</p>
            ) : (
              <ul className='divide-y text-xs'>
                {ticket.audit_events.map((ev) => (
                  <li key={ev.id} className='flex flex-col gap-1 py-2.5'>
                    <div className='flex items-center justify-between gap-2'>
                      <span className='font-semibold'>{ev.action}</span>
                      <span className='font-mono text-muted-foreground tabular-nums'>
                        {formatUtcTimestamp(ev.created_at, locale)}
                      </span>
                    </div>
                    <span className='text-muted-foreground'>{ev.actor}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {L('Confirm Label Correction?', 'تأكيد تصحيح التصنيفات؟')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {L(
                'Modified fields will be marked as human-verified, priority and routing will be recalculated, and an immutable audit event will be recorded.',
                'سيتم توثيق الحقول المعدلة كمصدر بشري وإعادة حساب الأولوية والتوجيه وتسجيل الحدث في سجل التدقيق.'
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{L('Cancel', 'إلغاء')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => void handleApplyCorrection()}>
              {L('Confirm & Save', 'تأكيد وحفظ')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Main>
  )
}
