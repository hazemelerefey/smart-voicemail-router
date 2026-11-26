import React, { useCallback, useEffect, useState } from 'react'
import { AlertCircle, RefreshCw, Save, ShieldCheck, ShieldOff } from 'lucide-react'
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
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Main } from '@/components/layout/main'
import { api, ApiError } from '@/lib/api'
import { UI_COPY, labelForCategory } from '@/lib/i18n'
import type { ScriptTemplateResponse } from '@/lib/types'

export function AdminSettingsPage() {
  const { locale, refreshSettings } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [confidenceThreshold, setConfidenceThreshold] = useState(0.5)
  const [retentionDays, setRetentionDays] = useState(90)
  const [weeklySampleRate, setWeeklySampleRate] = useState(0.05)
  const [autoRoutingEnabled, setAutoRoutingEnabled] = useState(true)
  const [templates, setTemplates] = useState<ScriptTemplateResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [killConfirmOpen, setKillConfirmOpen] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [s, tpls] = await Promise.all([api.getSettings(), api.getTemplates()])
      setConfidenceThreshold(s.confidence_threshold)
      setRetentionDays(s.retention_days)
      setWeeklySampleRate(s.weekly_sample_rate)
      setAutoRoutingEnabled(s.auto_routing_enabled)
      setTemplates(tpls)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load settings.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const handleSaveSettings = async (ev: React.FormEvent) => {
    ev.preventDefault()
    setBusy(true)
    try {
      await api.updateSettings({
        confidence_threshold: confidenceThreshold,
        retention_days: retentionDays,
        weekly_sample_rate: weeklySampleRate,
      })
      toast.success(
        L(
          'Settings saved. Updated thresholds apply to all incoming voicemails.',
          'تم حفظ الإعدادات. الحدود المحدثة تطبق على التذاكر الواردة الجديدة.'
        )
      )
      await refreshSettings()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to save settings.')
    } finally {
      setBusy(false)
    }
  }

  const handleToggleAutoRouting = async (nextState: boolean) => {
    setBusy(true)
    setKillConfirmOpen(false)
    try {
      const updated = await api.updateSettings({ auto_routing_enabled: nextState })
      setAutoRoutingEnabled(updated.auto_routing_enabled)
      toast.success(
        nextState
          ? L('Automatic routing restored.', 'تم تفعيل التوجيه الآلي.')
          : L('Automatic routing paused. Incoming voicemails will route to manual review.', 'تم إيقاف التوجيه التلقائي مؤقتا.')
      )
      await refreshSettings()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to update automatic routing setting.')
    } finally {
      setBusy(false)
    }
  }

  const handleSaveTemplate = async (tpl: ScriptTemplateResponse) => {
    setBusy(true)
    try {
      const updated = await api.updateTemplate(tpl.category, {
        template_ar: tpl.template_ar,
        template_en: tpl.template_en,
        customer_request_ar: tpl.customer_request_ar,
        customer_request_en: tpl.customer_request_en,
      })
      setTemplates((prev) => prev.map((x) => (x.category === tpl.category ? updated : x)))
      toast.success(L(`Saved template for ${tpl.category}.`, 'تم حفظ القالب.'))
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to update template.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('System Settings & Callback Templates', 'إعدادات النظام وقوالب الرد')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Configure review thresholds, automatic routing controls, and approved callback scripts.',
              'إعداد حدود المراجعة والتحكم في التوجيه التلقائي وقوالب معاودة الاتصال المعتمدة.'
            )}
          </p>
        </div>
        <Button variant='outline' onClick={() => void load()} disabled={loading}>
          <RefreshCw className='size-4' />
          {L('Refresh', 'تحديث')}
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
      ) : (
        <div className='space-y-6'>
          <div className='grid grid-cols-1 gap-4 lg:grid-cols-2'>
            <Card>
              <CardHeader>
                <CardTitle>{L('Pipeline Thresholds', 'حدود خط المعالجة')}</CardTitle>
                <CardDescription>
                  {L('Changes apply to new voicemails only; existing tickets retain their original settings.', 'التعديلات تطبق على التذاكر الجديدة فقط.')}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSaveSettings} className='space-y-4'>
                  <div className='grid gap-1.5'>
                    <Label htmlFor='cfg-thresh'>{L('Human Review Confidence Threshold (0..1)', 'حد الثقة للمراجعة البشرية')}</Label>
                    <Input
                      id='cfg-thresh'
                      type='number'
                      step='0.05'
                      min={0}
                      max={1}
                      value={confidenceThreshold}
                      onChange={(e) => setConfidenceThreshold(Number(e.target.value))}
                    />
                  </div>
                  <div className='grid grid-cols-2 gap-3'>
                    <div className='grid gap-1.5'>
                      <Label htmlFor='cfg-ret'>{L('Retention Days', 'أيام الاحتفاظ بالبيانات')}</Label>
                      <Input
                        id='cfg-ret'
                        type='number'
                        min={1}
                        max={3650}
                        value={retentionDays}
                        onChange={(e) => setRetentionDays(Number(e.target.value))}
                      />
                    </div>
                    <div className='grid gap-1.5'>
                      <Label htmlFor='cfg-sample'>{L('Weekly Quality Sample Rate', 'نسبة عينة الجودة')}</Label>
                      <Input
                        id='cfg-sample'
                        type='number'
                        step='0.01'
                        min={0}
                        max={1}
                        value={weeklySampleRate}
                        onChange={(e) => setWeeklySampleRate(Number(e.target.value))}
                      />
                    </div>
                  </div>
                  <Button type='submit' disabled={busy}>
                    <Save className='size-4' />
                    {L('Save Settings', 'حفظ الإعدادات')}
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className={!autoRoutingEnabled ? 'border-destructive' : ''}>
              <CardHeader>
                <CardTitle className='flex items-center gap-2'>
                  {autoRoutingEnabled ? (
                    <ShieldCheck className='size-5 text-[#00C853]' />
                  ) : (
                    <ShieldOff className='size-5 text-destructive' />
                  )}
                  {L('Automatic Routing Control', 'التحكم في التوجيه التلقائي')}
                </CardTitle>
                <CardDescription>
                  {L(
                    'When disabled, incoming voicemails remain unassigned and route to the Human Routing Queue for manual assignment.',
                    'عند الإيقاف تبقى كل التذاكر بدون موظف وتحول لقائمة المراجعة البشرية.'
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent className='space-y-4'>
                <div className='flex items-center justify-between rounded-md border p-4'>
                  <div>
                    <div className='text-sm font-semibold'>
                      {autoRoutingEnabled
                        ? L('Automatic Routing Enabled', 'التوجيه الآلي: مفعل')
                        : L('Automatic Routing Paused', 'التوجيه الآلي: متوقف')}
                    </div>
                    <div className='text-xs text-muted-foreground'>
                      {L('Applies immediately to all incoming voicemails.', 'يطبق فورا على التذاكر الواردة.')}
                    </div>
                  </div>
                  <Switch
                    checked={autoRoutingEnabled}
                    disabled={busy}
                    onCheckedChange={(checked) => {
                      if (!checked) setKillConfirmOpen(true)
                      else void handleToggleAutoRouting(true)
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>{L('11-Category Callback Script Templates', 'قوالب معاودة الاتصال المعتمدة (11 فئة)')}</CardTitle>
              <CardDescription>
                {L('Approved opening scripts tailored for each telecom complaint category.', 'جمل افتتاحية معتمدة لكل فئة شكوى.')}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-4'>
              {templates.map((tpl) => (
                <div key={tpl.category} className='space-y-3 rounded-lg border p-4'>
                  <div className='flex items-center justify-between gap-2'>
                    <div>
                      <span className='font-semibold'>{labelForCategory(tpl.category, locale)}</span>{' '}
                      <span className='font-mono text-xs text-muted-foreground'>
                        ({tpl.category} · v{tpl.version})
                      </span>
                    </div>
                    <Button size='sm' variant='outline' disabled={busy} onClick={() => void handleSaveTemplate(tpl)}>
                      <Save className='size-3.5' />
                      {L('Save', 'حفظ')}
                    </Button>
                  </div>
                  <div className='grid grid-cols-1 gap-3 md:grid-cols-2'>
                    <div className='grid gap-1'>
                      <Label className='text-xs'>Arabic Opening Script</Label>
                      <Textarea
                        dir='rtl'
                        value={tpl.template_ar}
                        onChange={(e) =>
                          setTemplates((prev) =>
                            prev.map((x) => (x.category === tpl.category ? { ...x, template_ar: e.target.value } : x))
                          )
                        }
                      />
                    </div>
                    <div className='grid gap-1'>
                      <Label className='text-xs'>English Opening Script</Label>
                      <Textarea
                        value={tpl.template_en}
                        onChange={(e) =>
                          setTemplates((prev) =>
                            prev.map((x) => (x.category === tpl.category ? { ...x, template_en: e.target.value } : x))
                          )
                        }
                      />
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}

      <AlertDialog open={killConfirmOpen} onOpenChange={setKillConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {L('Pause Automatic Routing?', 'تأكيد إيقاف التوجيه الآلي؟')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {L(
                'Incoming voicemails will remain unassigned and route directly to the Human Routing Queue until automatic routing is re-enabled.',
                'ستبقى كل الرسائل الصوتية الجديدة بدون موظف وتحول للمراجعة البشرية لحين إعادة التفعيل.'
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{L('Cancel', 'إلغاء')}</AlertDialogCancel>
            <AlertDialogAction onClick={() => void handleToggleAutoRouting(false)}>
              {L('Pause Automatic Routing', 'إيقاف التوجيه الآلي')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Main>
  )
}
