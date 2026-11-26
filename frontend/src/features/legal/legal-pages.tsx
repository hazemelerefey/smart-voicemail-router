import { useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import { ArrowLeft, Languages, Printer, ShieldCheck } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { SvrBrandMark } from '@/components/svr-brand-mark'
import { ThemeSwitch } from '@/components/theme-switch'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { PRIVACY_DOC, TERMS_DOC, type LegalDoc } from './legal-content'

function LegalDocumentShell({
  doc,
  kind,
}: {
  doc: LegalDoc
  kind: 'privacy' | 'terms'
}) {
  const { user, locale, setLocale } = useSvr()
  const isAr = locale === 'ar'
  const backTo = !user ? '/login' : user.role === 'agent' ? '/my-tickets' : '/overview'
  const siblingTo = kind === 'privacy' ? '/terms' : '/privacy'
  const siblingLabel =
    kind === 'privacy'
      ? isAr
        ? 'شروط الاستخدام'
        : 'Terms of Use'
      : isAr
        ? 'سياسة الخصوصية'
        : 'Privacy Policy'

  useEffect(() => {
    const prev = document.title
    document.title = `SVR System | ${doc.title}`
    return () => {
      document.title = prev
    }
  }, [doc.title])

  return (
    <div dir={isAr ? 'rtl' : 'ltr'} className='min-h-svh bg-background text-foreground'>
      <header className='sticky top-0 z-30 border-b border-border bg-background/90 backdrop-blur print:hidden'>
        <div className='mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-4 sm:px-6'>
          <div className='flex items-center gap-3'>
            <Link to={backTo} className='flex items-center gap-2.5'>
              <SvrBrandMark className='size-7' />
              <span className='font-bold tracking-tight'>SVR System</span>
            </Link>
            <span className='hidden text-border sm:inline'>|</span>
            <nav className='hidden items-center gap-1 sm:flex'>
              <Button
                variant={kind === 'privacy' ? 'secondary' : 'ghost'}
                size='sm'
                asChild
              >
                <Link to='/privacy'>{isAr ? 'الخصوصية' : 'Privacy'}</Link>
              </Button>
              <Button
                variant={kind === 'terms' ? 'secondary' : 'ghost'}
                size='sm'
                asChild
              >
                <Link to='/terms'>{isAr ? 'الشروط' : 'Terms'}</Link>
              </Button>
              <Button variant='ghost' size='sm' asChild>
                <Link to='/support'>{isAr ? 'الدعم' : 'Support'}</Link>
              </Button>
            </nav>
          </div>

          <div className='flex items-center gap-1.5'>
            <Button
              type='button'
              variant='ghost'
              size='sm'
              onClick={() => setLocale(isAr ? 'en' : 'ar')}
            >
              <Languages className='size-4' />
              <span>{isAr ? 'EN' : 'العربية'}</span>
            </Button>
            <ThemeSwitch />
            <Button variant='outline' size='sm' asChild>
              <Link to={backTo}>
                <ArrowLeft className='size-4' />
                <span>{isAr ? 'العودة' : 'Back'}</span>
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <div className='mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:py-12'>
        {/* Document Hero & Metadata */}
        <div className='border-b border-border pb-8'>
          <div className='mb-3 flex flex-wrap items-center gap-2'>
            <Badge variant='outline' className='gap-1.5 font-mono text-[11px]'>
              <ShieldCheck className='size-3.5 text-primary' />
              <span>{doc.docId}</span>
            </Badge>
            <span className='text-xs font-medium tracking-wide text-muted-foreground uppercase'>
              {doc.eyebrow}
            </span>
          </div>

          <h1 className='text-3xl font-bold tracking-tight sm:text-4xl'>{doc.title}</h1>
          <p className='mt-3 max-w-3xl text-sm leading-relaxed text-muted-foreground sm:text-base'>
            {doc.subtitle}
          </p>

          <dl className='mt-6 grid grid-cols-2 gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-4'>
            <div>
              <dt className='text-[11px] font-medium tracking-wide text-muted-foreground uppercase'>
                {isAr ? 'الإصدار' : 'Version'}
              </dt>
              <dd className='mt-1 font-mono text-sm font-semibold'>{doc.version}</dd>
            </div>
            <div>
              <dt className='text-[11px] font-medium tracking-wide text-muted-foreground uppercase'>
                {isAr ? 'تاريخ السريان' : 'Effective Date'}
              </dt>
              <dd className='mt-1 text-sm font-semibold'>{doc.effectiveDate}</dd>
            </div>
            <div>
              <dt className='text-[11px] font-medium tracking-wide text-muted-foreground uppercase'>
                {isAr ? 'الإطار التنظيمي' : 'Framework'}
              </dt>
              <dd className='mt-1 text-sm font-semibold'>{doc.framework}</dd>
            </div>
            <div>
              <dt className='text-[11px] font-medium tracking-wide text-muted-foreground uppercase'>
                {isAr ? 'نطاق التشغيل' : 'Deployment'}
              </dt>
              <dd className='mt-1 text-sm font-semibold'>{doc.deployment}</dd>
            </div>
          </dl>

          <div className='mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4'>
            {doc.highlights.map((h) => (
              <div
                key={h.label}
                className='rounded-md border border-border bg-muted/30 px-3.5 py-2.5'
              >
                <div className='text-[11px] text-muted-foreground'>{h.label}</div>
                <div className='mt-0.5 text-sm font-semibold tracking-tight'>{h.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Sticky TOC + Full Legal Body */}
        <div className='mt-8 grid grid-cols-1 gap-10 lg:grid-cols-[240px_1fr]'>
          <aside className='lg:sticky lg:top-20 lg:self-start print:hidden'>
            <div className='rounded-lg border border-border bg-card p-4'>
              <p className='text-xs font-semibold tracking-wide text-muted-foreground uppercase'>
                {isAr ? 'محتويات الوثيقة' : 'On this page'}
              </p>
              <nav aria-label='Table of contents' className='mt-3 space-y-1.5'>
                {doc.sections.map((sec, idx) => (
                  <a
                    key={sec.id}
                    href={`#${sec.id}`}
                    className='flex items-start gap-2 rounded px-1.5 py-1 text-xs leading-snug text-muted-foreground transition-colors hover:bg-muted hover:text-foreground'
                  >
                    <span className='font-mono text-[11px] text-muted-foreground/70'>
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                    <span>{sec.title}</span>
                  </a>
                ))}
              </nav>

              <div className='mt-4 space-y-2 border-t border-border pt-4'>
                <Button
                  type='button'
                  variant='outline'
                  size='sm'
                  className='w-full justify-start'
                  onClick={() => window.print()}
                >
                  <Printer className='size-3.5' />
                  <span>{isAr ? 'طباعة أو حفظ PDF' : 'Print / Save PDF'}</span>
                </Button>
                <Button variant='ghost' size='sm' className='w-full justify-start' asChild>
                  <Link to={siblingTo}>
                    {isAr ? `الانتقال إلى ${siblingLabel}` : `Read ${siblingLabel}`}
                  </Link>
                </Button>
              </div>
            </div>
          </aside>

          <main className='min-w-0 space-y-10'>
            {doc.sections.map((sec, idx) => (
              <section
                key={sec.id}
                id={sec.id}
                className='scroll-mt-24 border-b border-border/60 pb-8 last:border-b-0 last:pb-0'
              >
                <div className='flex items-baseline gap-3'>
                  <span className='font-mono text-xs font-semibold text-muted-foreground'>
                    {String(idx + 1).padStart(2, '0')}.
                  </span>
                  <h2 className='text-xl font-semibold tracking-tight'>{sec.title}</h2>
                </div>

                <div className='mt-3 space-y-3 text-sm leading-7 text-muted-foreground'>
                  {sec.paragraphs.map((p, pIdx) => (
                    <p key={pIdx}>{p}</p>
                  ))}
                </div>

                {sec.bullets && sec.bullets.length > 0 && (
                  <ul className='mt-4 space-y-2 border-s-2 border-border ps-4 text-sm leading-6 text-muted-foreground'>
                    {sec.bullets.map((b, bIdx) => (
                      <li key={bIdx}>{b}</li>
                    ))}
                  </ul>
                )}

                {sec.table && (
                  <div className='mt-5 overflow-x-auto rounded-lg border border-border'>
                    <table className='w-full border-collapse text-start text-xs sm:text-sm'>
                      <thead className='bg-muted/50 text-foreground'>
                        <tr>
                          {sec.table.headers.map((h) => (
                            <th
                              key={h}
                              className='border-b border-border px-3.5 py-2.5 text-start font-semibold'
                            >
                              {h}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className='divide-y divide-border text-muted-foreground'>
                        {sec.table.rows.map((row, rIdx) => (
                          <tr key={rIdx} className='hover:bg-muted/25'>
                            {row.map((cell, cIdx) => (
                              <td
                                key={cIdx}
                                className={
                                  cIdx === 0
                                    ? 'px-3.5 py-2.5 font-medium text-foreground align-top'
                                    : 'px-3.5 py-2.5 align-top'
                                }
                              >
                                {cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            ))}

            <footer className='flex flex-wrap items-center justify-between gap-4 border-t border-border pt-6 text-xs text-muted-foreground'>
              <div>© 2026 SVR System · {doc.docId} ({doc.version})</div>
              <div className='flex items-center gap-4'>
                <Link to={siblingTo} className='hover:text-foreground hover:underline'>
                  {siblingLabel}
                </Link>
                <Link to={backTo} className='hover:text-foreground hover:underline'>
                  {isAr ? 'العودة إلى النظام' : 'Return to SVR System'}
                </Link>
              </div>
            </footer>
          </main>
        </div>
      </div>
    </div>
  )
}

export function PrivacyPage() {
  const { locale } = useSvr()
  return <LegalDocumentShell doc={PRIVACY_DOC[locale]} kind='privacy' />
}

export function TermsPage() {
  const { locale } = useSvr()
  return <LegalDocumentShell doc={TERMS_DOC[locale]} kind='terms' />
}
