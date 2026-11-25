import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { AlertCircle, Languages, Lock } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SvrBrandMark } from '@/components/svr-brand-mark'
import { ThemeSwitch } from '@/components/theme-switch'
import { ApiError } from '@/lib/api'
import { UI_COPY } from '@/lib/i18n'

const AUTH_STEPS = {
  en: {
    headline: 'Egyptian Arabic voicemail in. A prioritized, routed callback ticket out.',
    steps: [
      { title: 'Transcribe', desc: 'Whisper large-v3 runs locally on your server. Audio never leaves it.' },
      { title: 'Classify', desc: 'MARBERTv2 reads four fields: category, urgency, customer state, churn risk.' },
      { title: 'Prioritize', desc: 'Deterministic priority score from 1 to 6 with full rationale.' },
      { title: 'Route', desc: 'First eligible agent by skill, availability, and capacity.' },
    ],
  },
  ar: {
    headline: 'رسالة صوتية بالعامية المصرية تدخل، وتذكرة معاودة اتصال مرتبة ومحددة الموظف تخرج.',
    steps: [
      { title: 'تفريغ الصوت', desc: 'Whisper large-v3 يعمل محليا على السيرفر والصوت لا يغادره.' },
      { title: 'التصنيف', desc: 'MARBERTv2 يقرأ أربعة حقول: نوع الشكوى، الاستعجال، حالة العميل، وChurn Risk.' },
      { title: 'ترتيب الأولوية', desc: 'درجة أولوية ثابتة من 1 إلى 6 مع سبب واضح.' },
      { title: 'التوجيه', desc: 'أول موظف مؤهل حسب المهارة والتوفر والسعة.' },
    ],
  },
} as const

export function LoginPage() {
  const { user, authLoading, login, locale, setLocale } = useSvr()
  const navigate = useNavigate()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const aside = AUTH_STEPS[locale]

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!authLoading && user) {
      void navigate({ to: user.role === 'agent' ? '/my-tickets' : '/overview', replace: true })
    }
  }, [authLoading, user, navigate])

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault()
    setError(null)
    if (!email.trim() || !password) {
      setError(
        isAr
          ? 'يرجى إدخال البريد الإلكتروني وكلمة المرور.'
          : 'Please enter both your email address and password.'
      )
      return
    }
    setSubmitting(true)
    try {
      const me = await login(email.trim(), password)
      if (me) {
        void navigate({ to: me.role === 'agent' ? '/my-tickets' : '/overview', replace: true })
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError(
          isAr
            ? 'تعذر الاتصال بخادم المصادقة. حاول مرة أخرى.'
            : 'Could not reach the authentication server. Please try again.'
        )
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className='relative container grid min-h-svh flex-col items-center justify-center lg:max-w-none lg:grid-cols-2 lg:px-0'>
      <div className='relative hidden h-full flex-col justify-between bg-zinc-900 p-10 text-white lg:flex dark:border-e'>
        <div className='flex items-center gap-3'>
          <SvrBrandMark className='size-9' />
          <div className='flex flex-col leading-tight'>
            <span className='text-lg font-bold tracking-tight'>{t.appName}</span>
            <span className='text-xs text-zinc-400'>{t.orgName}</span>
          </div>
        </div>

        <div className='my-auto max-w-lg space-y-6'>
          <h2 className='text-3xl font-bold tracking-tight leading-tight'>{aside.headline}</h2>
          <ol className='divide-y divide-zinc-800 border-t border-zinc-800'>
            {aside.steps.map((s, idx) => (
              <li key={s.title} className='grid grid-cols-[2.25rem_1fr] gap-x-3 py-4'>
                <span className='row-span-2 font-mono text-sm font-bold text-red-400'>
                  {String(idx + 1).padStart(2, '0')}
                </span>
                <span className='text-sm font-semibold'>{s.title}</span>
                <span className='text-xs text-zinc-400'>{s.desc}</span>
              </li>
            ))}
          </ol>
        </div>

        <p className='text-xs text-zinc-400'>
          {isAr
            ? 'منظومة توجيه البريد الصوتي الذكي لخدمة عملاء الاتصالات.'
            : 'Smart Voicemail Router for telecom customer-care operations.'}
        </p>
      </div>

      <div className='flex flex-col justify-center p-6 sm:p-10'>
        <div className='mx-auto flex w-full max-w-sm flex-col gap-6'>
          <div className='flex items-center justify-between gap-2'>
            <div className='flex items-center gap-2.5 lg:invisible'>
              <SvrBrandMark className='size-8' />
              <div className='flex flex-col leading-tight'>
                <span className='text-sm font-bold'>{t.appName}</span>
                <span className='text-xs text-muted-foreground'>{t.orgName}</span>
              </div>
            </div>
            <div className='flex items-center gap-1'>
              <Button
                type='button'
                variant='ghost'
                size='sm'
                onClick={() => setLocale(locale === 'en' ? 'ar' : 'en')}
                aria-label={locale === 'en' ? 'Switch to Arabic' : 'Switch to English'}
              >
                <Languages className='size-4' />
                <span>{locale === 'en' ? 'العربية' : 'EN'}</span>
              </Button>
              <ThemeSwitch />
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className='text-2xl'>
                {isAr ? 'تسجيل دخول المشغل' : 'Operator Sign In'}
              </CardTitle>
              <CardDescription>
                {isAr
                  ? 'أدخل بيانات حسابك للوصول إلى قائمة معاودة الاتصال وإدارة الرسائل الصوتية.'
                  : 'Sign in with your telecom care operator account to access subscriber voicemail queues.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {error && (
                <Alert variant='destructive' className='mb-4'>
                  <AlertCircle className='size-4' />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <form onSubmit={handleSubmit} noValidate className='grid gap-4'>
                <div className='grid gap-2'>
                  <Label htmlFor='login-email'>{isAr ? 'البريد الإلكتروني' : 'Email'}</Label>
                  <Input
                    id='login-email'
                    name='email'
                    type='email'
                    autoComplete='username'
                    required
                    value={email}
                    onChange={(ev) => setEmail(ev.target.value)}
                    placeholder='supervisor@telecom.local'
                    disabled={submitting}
                  />
                </div>

                <div className='grid gap-2'>
                  <Label htmlFor='login-password'>{isAr ? 'كلمة المرور' : 'Password'}</Label>
                  <Input
                    id='login-password'
                    name='password'
                    type='password'
                    autoComplete='current-password'
                    required
                    value={password}
                    onChange={(ev) => setPassword(ev.target.value)}
                    disabled={submitting}
                  />
                </div>

                <Button type='submit' className='w-full' disabled={submitting}>
                  <Lock className='size-4' />
                  {submitting
                    ? isAr
                      ? 'جاري التحقق...'
                      : 'Signing in...'
                    : isAr
                      ? 'تسجيل الدخول'
                      : 'Sign In'}
                </Button>
              </form>

              <div className='mt-5 flex flex-wrap items-center justify-between gap-2 border-t pt-4 text-xs text-muted-foreground'>
                <span>
                  {isAr ? 'جلسة محمية لمدة 8 ساعات.' : 'HttpOnly session expires after 8h.'}
                </span>
                <div className='flex items-center gap-3'>
                  <Link to='/privacy' className='underline-offset-4 hover:underline'>
                    {t.privacy}
                  </Link>
                  <Link to='/terms' className='underline-offset-4 hover:underline'>
                    {t.terms}
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
