import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { AlertCircle, CheckCircle2, Mic, Square, Upload } from 'lucide-react'
import { toast } from 'sonner'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { VoicemailAudioPlayer } from '@/components/svr/voicemail-audio-player'
import { api, ApiError } from '@/lib/api'
import type { Locale } from '@/lib/i18n'
import { formatDuration } from '@/lib/taxonomy'
import { BrowserWavRecorder, MicrophoneError } from '@/lib/wavRecorder'

interface VoicemailIntakeSheetProps {
  open: boolean
  locale: Locale
  onOpenChange: (open: boolean) => void
  onSubmitted: () => void
}

const ACCEPTED_EXT = /\.(wav|mp3|m4a)$/i
const MAX_BYTES = 25 * 1024 * 1024

export function VoicemailIntakeSheet({
  open,
  locale,
  onOpenChange,
  onSubmitted,
}: VoicemailIntakeSheetProps) {
  const navigate = useNavigate()
  const { refreshReviewBadge } = useSvr()
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)
  const [recSeconds, setRecSeconds] = useState(0)
  const [audioLevel, setAudioLevel] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resultMsg, setResultMsg] = useState<string | null>(null)
  const [createdTicketId, setCreatedTicketId] = useState<string | null>(null)

  const recorderRef = useRef<BrowserWavRecorder | null>(null)
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
      if (timerRef.current !== null) window.clearInterval(timerRef.current)
      recorderRef.current?.abort()
    }
  }, [previewUrl])

  const setSelectedFile = (f: File | null) => {
    setError(null)
    setResultMsg(null)
    setCreatedTicketId(null)
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    if (!f) {
      setFile(null)
      setPreviewUrl(null)
      return
    }
    if (!ACCEPTED_EXT.test(f.name) && !f.type.startsWith('audio/')) {
      setError(
        L(
          'Unsupported format. Please select a WAV, MP3, or M4A voicemail.',
          'صيغة غير مدعومة. يرجى اختيار ملف صوتي WAV أو MP3 أو M4A.'
        )
      )
      return
    }
    if (f.size > MAX_BYTES) {
      setError(
        L(
          'File exceeds the 25 MB limit. Please upload a shorter voicemail (up to 60 seconds).',
          'حجم الملف يتجاوز 25 ميجابايت. الحد الأقصى 60 ثانية.'
        )
      )
      return
    }
    setFile(f)
    setPreviewUrl(URL.createObjectURL(f))
  }

  const startRecording = async () => {
    setError(null)
    setResultMsg(null)
    setCreatedTicketId(null)
    setAudioLevel(0)
    try {
      const rec = new BrowserWavRecorder()
      await rec.start({
        onLevel: (rms) => setAudioLevel(Math.min(100, Math.round(rms * 350))),
      })
      recorderRef.current = rec
      setRecording(true)
      setRecSeconds(0)
      timerRef.current = window.setInterval(() => {
        setRecSeconds((s) => {
          if (s >= 59) {
            void stopRecording()
            return 60
          }
          return s + 1
        })
      }, 1000)
    } catch (err) {
      setAudioLevel(0)
      const code = err instanceof MicrophoneError ? err.code : 'audio_graph_error'
      const msgMap: Record<string, string> = {
        insecure_context: L(
          'Microphone access requires localhost (127.0.0.1) or HTTPS. You can still upload a WAV/MP3/M4A file.',
          'يتطلب تسجيل الميكروفون تشغيل الموقع على localhost أو HTTPS. يمكنك رفع ملف صوتي بدلا من ذلك.'
        ),
        unsupported: L(
          'This browser or embedded pane does not expose microphone APIs. Use Chrome/Edge tab or upload a WAV/MP3/M4A file.',
          'هذا المتصفح لا يدعم واجهة الميكروفون. استخدم نافذة Chrome أو ارفع ملفا صوتيا.'
        ),
        permission_denied: L(
          'Microphone permission was blocked. Allow microphone access in the browser address bar or upload a WAV/MP3/M4A file.',
          'تم حظر إذن الميكروفون. اسمح بالوصول من شريط العنوان أو ارفع ملفا صوتيا.'
        ),
        no_device: L(
          'No active microphone device was detected on this machine. Connect a mic or upload a WAV/MP3/M4A file.',
          'لم يتم العثور على ميكروفون متصل بهذا الجهاز. يمكنك رفع ملف صوتي بدلا من ذلك.'
        ),
        device_in_use: L(
          'The microphone is currently in use by another application. Close the other app or upload a WAV/MP3/M4A file.',
          'الميكروفون مستخدم حاليا في تطبيق آخر. يمكنك رفع ملف صوتي بدلا من ذلك.'
        ),
        audio_graph_error: L(
          'Microphone audio capture could not start in this browser context. You can upload a WAV/MP3/M4A file directly.',
          'تعذر تشغيل التقاط الصوت في المتصفح. يمكنك رفع ملف WAV/MP3/M4A مباشرة.'
        ),
      }
      setError(msgMap[code] || msgMap.audio_graph_error)
    }
  }

  const stopRecording = async () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    setRecording(false)
    setAudioLevel(0)
    if (!recorderRef.current) return
    try {
      const result = await recorderRef.current.stop()
      recorderRef.current = null
      setSelectedFile(result.file)
    } catch {
      setError(L('Could not finalize browser recording.', 'تعذر إنهاء التسجيل الصوتي.'))
    }
  }

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!file) {
      setError(
        L(
          'Select an audio file or record a voicemail first.',
          'اختر ملفا صوتيا أو سجل رسالة صوتية أولا.'
        )
      )
      return
    }
    setSubmitting(true)
    setError(null)
    setResultMsg(null)
    try {
      const res = await api.uploadVoicemail(file)
      setCreatedTicketId(res.ticket_id)
      const msg = res.deduplicated
        ? L(
            `Duplicate audio detected. Linked existing ticket #${res.ticket_id.slice(0, 8)}.`,
            `ملف مكرر. تم ربط التذكرة الحالية #${res.ticket_id.slice(0, 8)}.`
          )
        : L(
            `Voicemail queued (Ticket #${res.ticket_id.slice(0, 8)}). VoiceGate Orchestrator started local Arabic ASR, VoiceGate verification, and MARBERTv2 classification.`,
            `تم استلام الرسالة الصوتية (تذكرة #${res.ticket_id.slice(0, 8)}) وبدأ VoiceGate Orchestrator مراحل التفريغ والتحقق والتصنيف.`
          )
      setResultMsg(msg)
      toast.success(msg)
      void refreshReviewBadge()
      onSubmitted()
    } catch (err) {
      const detail =
        err instanceof ApiError
          ? err.detail
          : L('Voicemail upload failed.', 'فشل رفع الرسالة الصوتية.')
      setError(detail)
      toast.error(detail)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className='flex w-full flex-col gap-5 overflow-y-auto sm:max-w-lg'>
        <SheetHeader>
          <SheetTitle>{L('Subscriber Voicemail Intake', 'استلام رسالة صوتية جديدة')}</SheetTitle>
          <SheetDescription>
            {L(
              'Upload a WAV, MP3, or M4A voicemail (up to 25 MB / 60s) or record directly. Audio stays local.',
              'ارفع ملف WAV أو MP3 أو M4A (حتى 25 ميجابايت / 60 ثانية) أو سجل مباشرة. الصوت يبقى محليا بالكامل.'
            )}
          </SheetDescription>
        </SheetHeader>

        <form onSubmit={handleSubmit} className='flex flex-col gap-5'>
          <div className='flex flex-col gap-2 rounded-lg border bg-muted/40 p-4'>
            <div className='text-sm font-medium'>
              {L('Browser Microphone (16 kHz Mono WAV)', 'تسجيل مباشر من المتصفح (16 kHz WAV)')}
            </div>
            <div className='flex flex-wrap items-center gap-3'>
              {!recording ? (
                <Button
                  type='button'
                  variant='outline'
                  onClick={() => void startRecording()}
                  disabled={submitting}
                >
                  <Mic className='size-4' />
                  {L('Start Recording', 'بدء التسجيل')}
                </Button>
              ) : (
                <Button type='button' variant='destructive' onClick={() => void stopRecording()}>
                  <Square className='size-4' />
                  {L('Stop Recording', 'إيقاف التسجيل')} ({formatDuration(recSeconds)})
                </Button>
              )}
              {recording && (
                <div className='flex items-center gap-2'>
                  <span className='inline-block size-2 animate-pulse rounded-full bg-destructive' />
                  <span className='text-xs font-medium text-destructive'>
                    {L('Recording (max 60s)...', 'جاري التسجيل (حد أقصى 60 ثانية)...')}
                  </span>
                  <div className='h-2 w-24 overflow-hidden rounded-full bg-muted'>
                    <div
                      className='h-full bg-emerald-500 transition-all duration-75'
                      style={{ width: `${Math.max(8, audioLevel)}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className='flex flex-col gap-2'>
            <Label htmlFor='voicemail-file-input'>
              {L('Or select audio file (WAV, MP3, M4A)', 'أو اختر ملفا صوتيا (WAV, MP3, M4A)')}
            </Label>
            <Input
              id='voicemail-file-input'
              type='file'
              accept='.wav,.mp3,.m4a,audio/wav,audio/mpeg,audio/mp4'
              disabled={submitting || recording}
              onChange={(ev) => setSelectedFile(ev.target.files?.[0] || null)}
            />
          </div>

          {file && previewUrl && (
            <div className='flex flex-col gap-2 rounded-lg border bg-muted/30 p-3'>
              <div className='flex items-center justify-between gap-2 text-xs'>
                <span className='truncate font-mono font-medium'>{file.name}</span>
                <span className='tabular-nums text-muted-foreground'>
                  {(file.size / 1024).toFixed(1)} KB
                </span>
              </div>
              <VoicemailAudioPlayer src={previewUrl} className='w-full' />
            </div>
          )}

          {error && (
            <Alert variant='destructive'>
              <AlertCircle className='size-4' />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {resultMsg && (
            <Alert>
              <CheckCircle2 className='size-4 text-emerald-600' />
              <AlertDescription className='flex flex-col gap-2'>
                <span>{resultMsg}</span>
                {createdTicketId && (
                  <Button
                    type='button'
                    variant='outline'
                    size='sm'
                    className='w-fit'
                    onClick={() => {
                      onOpenChange(false)
                      void navigate({ to: '/tickets/$id', params: { id: createdTicketId } })
                    }}
                  >
                    {L('Open Ticket Detail', 'فتح تفاصيل التذكرة')}
                  </Button>
                )}
              </AlertDescription>
            </Alert>
          )}

          <div className='flex items-center justify-end gap-2 pt-2'>
            <Button
              type='button'
              variant='outline'
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              {L('Close', 'إغلاق')}
            </Button>
            <Button type='submit' disabled={!file || submitting || recording}>
              <Upload className='size-4' />
              {submitting
                ? L('Uploading...', 'جاري الرفع...')
                : L('Upload & Run Pipeline', 'رفع وتشغيل التحليل')}
            </Button>
          </div>
        </form>
      </SheetContent>
    </Sheet>
  )
}
