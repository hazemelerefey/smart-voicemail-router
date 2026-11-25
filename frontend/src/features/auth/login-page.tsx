import React, { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import { useSvr } from '@/context/svr-provider'
import { useTheme } from '@/context/theme-provider'
import { ApiError } from '@/lib/api'
import './login-page.css'

const COPY = {
  en: {
    product: 'Smart Voicemail Router',
    title: 'Operator sign in',
    lead: 'Use your telecom care operator account to access subscriber voicemail queues.',
    email: 'Email address',
    pass: 'Password',
    caps: 'CAPS LOCK',
    keep: 'Remember my email',
    forgot: 'Forgot password?',
    btn: 'Sign in',
    done: 'Signed in',
    note: 'Accounts are managed by your administrator. Contact them if you need access or a password reset.',
    privacy: 'Privacy',
    terms: 'Terms',
    support: 'Support',
    eEm: 'Enter a valid email address.',
    ePw: 'Enter your password.',
    show: 'Show password',
    hide: 'Hide password',
    toLight: 'Switch to light mode',
    toDark: 'Switch to dark mode',
  },
  ar: {
    product: 'موجّه البريد الصوتي الذكي',
    title: 'تسجيل دخول المشغّل',
    lead: 'استخدم حساب مشغّل خدمة العملاء للوصول إلى طوابير البريد الصوتي للمشتركين.',
    email: 'البريد الإلكتروني',
    pass: 'كلمة المرور',
    caps: 'CAPS LOCK',
    keep: 'تذكّر بريدي الإلكتروني',
    forgot: 'نسيت كلمة المرور؟',
    btn: 'تسجيل الدخول',
    done: 'تم تسجيل الدخول',
    note: 'الحسابات يديرها المسؤول. تواصل معه إذا احتجت إلى وصول أو إعادة تعيين كلمة المرور.',
    privacy: 'الخصوصية',
    terms: 'الشروط',
    support: 'الدعم',
    eEm: 'أدخل بريدًا إلكترونيًا صحيحًا.',
    ePw: 'أدخل كلمة المرور.',
    show: 'إظهار كلمة المرور',
    hide: 'إخفاء كلمة المرور',
    toLight: 'التبديل إلى الوضع الفاتح',
    toDark: 'التبديل إلى الوضع الداكن',
  },
} as const

function isValidEmail(v: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
}

export function LoginPage() {
  const { user, authLoading, login, locale, setLocale } = useSvr()
  const { resolvedTheme, setTheme } = useTheme()
  const navigate = useNavigate()
  const t = COPY[locale]

  const rootRef = useRef<HTMLDivElement>(null)
  const heroRef = useRef<HTMLElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const emailRef = useRef<HTMLInputElement>(null)
  const passRef = useRef<HTMLInputElement>(null)
  const eyeRef = useRef<HTMLButtonElement>(null)
  const goRef = useRef<HTMLButtonElement>(null)

  const [email, setEmail] = useState<string>(() => {
    try {
      return localStorage.getItem('svr-email') ?? ''
    } catch {
      return ''
    }
  })
  const [remember, setRemember] = useState<boolean>(() => {
    try {
      return Boolean(localStorage.getItem('svr-email'))
    } catch {
      return false
    }
  })
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [capsOn, setCapsOn] = useState(false)
  const [emailError, setEmailError] = useState('')
  const [passError, setPassError] = useState('')
  const [status, setStatus] = useState<'idle' | 'busy' | 'done'>('idle')
  const [switching, setSwitching] = useState(false)
  const [noteHighlight, setNoteHighlight] = useState(false)

  const colRef = useRef({ stroke: '229,234,240', hi: '0,209,209', sa: 0.24 })
  const drawStillRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!authLoading && user && status !== 'done') {
      void navigate({ to: user.role === 'agent' ? '/my-tickets' : '/overview', replace: true })
    }
  }, [authLoading, user, status, navigate])

  useEffect(() => {
    const prevTitle = document.title
    document.title = 'SVR System | Sign in'
    return () => {
      document.title = prevTitle
    }
  }, [])

  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const cs = getComputedStyle(root)
    colRef.current = {
      stroke: cs.getPropertyValue('--stroke').trim() || '229,234,240',
      hi: cs.getPropertyValue('--hi').trim() || '0,209,209',
      sa: parseFloat(cs.getPropertyValue('--sa')) || 0.24,
    }
    drawStillRef.current?.()
  }, [resolvedTheme])

  useEffect(() => {
    const hero = heroRef.current
    const cv = canvasRef.current
    if (!hero || !cv) return
    const ctx = cv.getContext('2d')
    if (!ctx) return

    let W = 0
    let H = 0
    let mx = 0
    let my = 0
    let tx = 0
    let ty = 0
    let act = 0
    let rafId = 0
    const S = 24
    const t0 = performance.now()
    const rm = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    const draw = (now: number) => {
      const t = (now - t0) / 1000
      mx += (tx - mx) * 0.16
      my += (ty - my) * 0.16
      ctx.clearRect(0, 0, W, H)
      ctx.lineCap = 'round'
      const { stroke, hi, sa } = colRef.current

      for (let y = S / 2; y < H; y += S) {
        for (let x = S / 2; x < W; x += S) {
          const dx = mx - x
          const dy = my - y
          const q = Math.sqrt(dx * dx + dy * dy)
          let k = act ? Math.max(0, 1 - q / 200) : 0
          k = k * k * (3 - 2 * k)
          const b = (Math.sin(x * 0.011 + t * 0.5) + Math.cos(y * 0.013 - t * 0.4)) * 0.9
          const g = Math.atan2(dy, dx)
          const ax = Math.cos(b) * (1 - k) + Math.cos(g) * k
          const ay = Math.sin(b) * (1 - k) + Math.sin(g) * k
          const a = Math.atan2(ay, ax)
          const l = (6.5 + k * 14) / 2
          ctx.strokeStyle =
            k > 0.04 ? `rgba(${hi},${Math.min(1, sa + k * 0.72).toFixed(3)})` : `rgba(${stroke},${sa})`
          ctx.lineWidth = 1.25 + k * 1.1
          ctx.beginPath()
          ctx.moveTo(x - Math.cos(a) * l, y - Math.sin(a) * l)
          ctx.lineTo(x + Math.cos(a) * l, y + Math.sin(a) * l)
          ctx.stroke()
        }
      }
      if (!rm) {
        rafId = window.requestAnimationFrame(draw)
      }
    }

    const resize = () => {
      const d = Math.min(window.devicePixelRatio || 1, 2)
      const r = hero.getBoundingClientRect()
      W = r.width
      H = r.height
      cv.width = W * d
      cv.height = H * d
      cv.style.width = `${W}px`
      cv.style.height = `${H}px`
      ctx.setTransform(d, 0, 0, d, 0, 0)
      mx = tx = W * 0.5
      my = ty = H * 0.4
      if (rm) draw(t0)
    }

    const onMove = (e: PointerEvent) => {
      const r = hero.getBoundingClientRect()
      tx = e.clientX - r.left
      ty = e.clientY - r.top
      act = 1
    }

    const onLeave = () => {
      act = 0
    }

    drawStillRef.current = () => {
      if (rm) draw(t0)
    }

    resize()
    hero.addEventListener('pointermove', onMove)
    hero.addEventListener('pointerleave', onLeave)
    window.addEventListener('resize', resize)
    if (!rm) {
      rafId = window.requestAnimationFrame(draw)
    }

    return () => {
      drawStillRef.current = null
      if (rafId) window.cancelAnimationFrame(rafId)
      hero.removeEventListener('pointermove', onMove)
      hero.removeEventListener('pointerleave', onLeave)
      window.removeEventListener('resize', resize)
    }
  }, [])

  const triggerShake = () => {
    const g = goRef.current
    if (!g) return
    g.classList.remove('shake')
    void g.offsetWidth
    g.classList.add('shake')
  }

  const handleLangSwitch = (next: 'en' | 'ar') => {
    if (next === locale) return
    setSwitching(true)
    window.setTimeout(() => {
      setLocale(next)
      setEmailError('')
      setPassError('')
      setSwitching(false)
    }, 160)
  }

  const handleToggleEye = () => {
    setShowPass((prev) => !prev)
    const el = eyeRef.current
    if (el) {
      el.classList.remove('blink')
      void el.offsetWidth
      el.classList.add('blink')
    }
    passRef.current?.focus()
  }

  const handleCaps = (e: React.KeyboardEvent<HTMLInputElement>) => {
    setCapsOn(Boolean(e.getModifierState && e.getModifierState('CapsLock')))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const em = email.trim()
    const emOk = isValidEmail(em)
    setEmailError(emOk ? '' : t.eEm)
    setPassError(password ? '' : t.ePw)

    if (!emOk || !password) {
      triggerShake()
      if (!emOk) emailRef.current?.focus()
      else passRef.current?.focus()
      return
    }

    try {
      if (remember) localStorage.setItem('svr-email', em)
      else localStorage.removeItem('svr-email')
    } catch {
      /* ignore storage errors */
    }

    setStatus('busy')
    try {
      const me = await login(em, password)
      if (me) {
        setStatus('done')
        window.setTimeout(() => {
          void navigate({ to: me.role === 'agent' ? '/my-tickets' : '/overview', replace: true })
        }, 450)
      } else {
        setStatus('idle')
      }
    } catch (err) {
      setStatus('idle')
      if (err instanceof ApiError) {
        setPassError(err.detail)
      } else {
        setPassError(
          locale === 'ar'
            ? 'تعذر الاتصال بخادم المصادقة. حاول مرة أخرى.'
            : 'Could not reach the authentication server. Please try again.'
        )
      }
      triggerShake()
    }
  }

  const emailValid = isValidEmail(email.trim())
  const locked = status !== 'idle'
  const eyeLabel = showPass ? t.hide : t.show
  const themeLabel = resolvedTheme === 'dark' ? t.toLight : t.toDark

  return (
    <div
      ref={rootRef}
      className='svr-login'
      data-theme={resolvedTheme}
      dir={locale === 'ar' ? 'rtl' : 'ltr'}
    >
      <section className='hero' ref={heroRef}>
        <div className='bg' aria-hidden='true'>
          <canvas ref={canvasRef} className='svr-login-canvas' />
        </div>
        <div className={`chip${switching ? ' sw' : ''}`} aria-label='SVR System'>
          <svg viewBox='210 257 331 236' aria-hidden='true'>
            <g fill='#00D1D1'>
              <rect x='210.2' y='344' width='39.6' height='65.5' rx='19.8' opacity='.45' />
              <rect x='271.2' y='306' width='39.6' height='140.5' rx='19.8' opacity='.7' />
              <rect x='334.2' y='257' width='39.6' height='236.5' rx='19.8' />
              <path d='M393,326 A20,20 0 0 1 433,326 L433,356 L411,375.5 Q405,381 399,378 Q393,375 393,368 Z' />
              <path d='M393,457 L393,428 Q393,422 397.5,418.5 L418,406 Q421.5,404 425,404 Q433,404 433,412 L433,457 A20,20 0 0 1 393,457 Z' />
            </g>
            <path
              d='M453,376 H528 M502,349 L528,376 L502,403'
              fill='none'
              stroke='#00D1D1'
              strokeWidth='26'
              strokeLinecap='round'
              strokeLinejoin='round'
            />
          </svg>
          <b>SVR System</b>
          <span>{t.product}</span>
        </div>
      </section>

      <main className='side'>
        <div className='top'>
          <div className='lang' role='group' aria-label='Language'>
            <button
              type='button'
              aria-pressed={locale === 'en'}
              onClick={() => handleLangSwitch('en')}
            >
              EN
            </button>
            <button
              type='button'
              aria-pressed={locale === 'ar'}
              onClick={() => handleLangSwitch('ar')}
            >
              عربي
            </button>
          </div>
          <button
            className='th'
            type='button'
            aria-label={themeLabel}
            onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
          >
            <svg className='moon' viewBox='0 0 24 24'>
              <path d='M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z' />
            </svg>
            <svg className='sun' viewBox='0 0 24 24'>
              <circle cx='12' cy='12' r='4' />
              <path d='M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6' />
            </svg>
          </button>
        </div>

        <div className='center'>
          <form className={`card${switching ? ' sw' : ''}`} onSubmit={handleSubmit} noValidate>
            <h1>{t.title}</h1>
            <p className='lead'>{t.lead}</p>

            <div className={`fld${emailError ? ' bad' : ''}${emailValid ? ' valid' : ''}`}>
              <input
                ref={emailRef}
                id='em'
                type='email'
                inputMode='email'
                enterKeyHint='next'
                autoCapitalize='off'
                placeholder=' '
                autoComplete='username'
                spellCheck={false}
                dir='auto'
                autoFocus
                readOnly={locked}
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  if (emailError) setEmailError('')
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && isValidEmail(email.trim()) && !password) {
                    e.preventDefault()
                    passRef.current?.focus()
                  }
                }}
              />
              <label htmlFor='em'>{t.email}</label>
              <span className='ok' aria-hidden='true'>
                <svg viewBox='0 0 24 24'>
                  <path pathLength={1} d='M5 12.5l4.5 4.5L19 7.5' />
                </svg>
              </span>
            </div>
            <div className='hint' role='alert'>
              {emailError}
            </div>

            <div className={`fld${passError ? ' bad' : ''}`}>
              <input
                ref={passRef}
                id='pw'
                type={showPass ? 'text' : 'password'}
                enterKeyHint='go'
                placeholder=' '
                autoComplete='current-password'
                dir='auto'
                readOnly={locked}
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (passError) setPassError('')
                }}
                onKeyDown={handleCaps}
                onKeyUp={handleCaps}
                onBlur={() => setCapsOn(false)}
              />
              <label htmlFor='pw'>{t.pass}</label>
              <span className={`caps${capsOn ? ' on' : ''}`}>{t.caps}</span>
              <button
                ref={eyeRef}
                type='button'
                className='eye'
                aria-pressed={showPass}
                aria-label={eyeLabel}
                data-tip={eyeLabel}
                onClick={handleToggleEye}
              >
                <svg viewBox='0 0 24 24' aria-hidden='true'>
                  <path className='lid' d='M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z' />
                  <circle className='pup' cx='12' cy='12' r='3' />
                  <path className='sl' pathLength={1} d='M4 20L20 4' />
                </svg>
              </button>
            </div>
            <div className='hint' role='alert'>
              {passError}
            </div>

            <div className='row'>
              <label className='chk'>
                <input
                  type='checkbox'
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                <span>{t.keep}</span>
              </label>
              <a
                href='#admin-note'
                onClick={(e) => {
                  e.preventDefault()
                  setNoteHighlight(true)
                  window.setTimeout(() => setNoteHighlight(false), 1800)
                }}
              >
                {t.forgot}
              </a>
            </div>

            <button
              ref={goRef}
              className={`go${status === 'busy' ? ' busy' : ''}${status === 'done' ? ' done' : ''}`}
              type='submit'
            >
              <span className='spin' aria-hidden='true' />
              <span>{status === 'done' ? t.done : t.btn}</span>
              <svg
                className='ar'
                width='18'
                height='18'
                viewBox='0 0 24 24'
                fill='none'
                stroke='currentColor'
                strokeWidth='2.2'
                strokeLinecap='round'
                strokeLinejoin='round'
              >
                <path d='M5 12h14M13 6l6 6-6 6' />
              </svg>
              <svg
                className='tick'
                width='18'
                height='18'
                viewBox='0 0 24 24'
                fill='none'
                strokeWidth='2.4'
                strokeLinecap='round'
                strokeLinejoin='round'
              >
                <path pathLength={1} d='M5 12.5l4.5 4.5L19 7.5' />
              </svg>
              <i className='bar' />
            </button>

            <div id='admin-note' className={`note${noteHighlight ? ' highlight' : ''}`}>
              <svg
                width='16'
                height='16'
                viewBox='0 0 24 24'
                fill='none'
                stroke='currentColor'
                strokeWidth='1.8'
                strokeLinecap='round'
                strokeLinejoin='round'
              >
                <rect x='4' y='11' width='16' height='10' rx='2' />
                <path d='M8 11V7a4 4 0 018 0v4' />
              </svg>
              <span>{t.note}</span>
            </div>
          </form>
        </div>

        <div className='foot'>
          <div>
            <Link to='/privacy'>{t.privacy}</Link>
            <Link to='/terms'>{t.terms}</Link>
            <a href='mailto:admin@telecom.local'>{t.support}</a>
          </div>
          <div>© 2026 SVR System</div>
        </div>
      </main>
    </div>
  )
}
