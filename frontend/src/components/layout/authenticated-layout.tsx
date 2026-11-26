import { useEffect } from 'react'
import { Link, Outlet, useNavigate, useRouterState } from '@tanstack/react-router'
import { ShieldOff } from 'lucide-react'
import { getCookie } from '@/lib/cookies'
import { cn } from '@/lib/utils'
import { LayoutProvider } from '@/context/layout-provider'
import { SearchProvider } from '@/context/search-provider'
import { useSvr } from '@/context/svr-provider'
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar'
import { Button } from '@/components/ui/button'
import { AppSidebar } from '@/components/layout/app-sidebar'
import { SvrHeader } from '@/components/layout/svr-header'
import { SkipToMain } from '@/components/skip-to-main'
import { UI_COPY } from '@/lib/i18n'

type AuthenticatedLayoutProps = {
  children?: React.ReactNode
}

export function AuthenticatedLayout({ children }: AuthenticatedLayoutProps) {
  const defaultOpen = getCookie('sidebar_state') !== 'false'
  const { user, authLoading, settings, locale, reviewBadgeCount } = useSvr()
  const navigate = useNavigate()
  const pathname = useRouterState({ select: (s) => s.location.pathname })
  const t = UI_COPY[locale]

  useEffect(() => {
    let page = 'SVR System'
    if (pathname.startsWith('/overview')) page = locale === 'ar' ? 'نظرة عامة' : 'Overview'
    else if (pathname.startsWith('/dashboard')) page = locale === 'ar' ? 'طابور المعاودة' : 'Callback Queue'
    else if (pathname.startsWith('/review-queue')) {
      const count = typeof reviewBadgeCount === 'number' && reviewBadgeCount > 0 ? ` (${reviewBadgeCount})` : ''
      page = `${locale === 'ar' ? 'مراجعة التوجيه' : 'Human Routing Queue'}${count}`
    } else if (pathname.startsWith('/evaluation')) page = locale === 'ar' ? 'تقييم النماذج' : 'Model Evaluation'
    else if (pathname.startsWith('/audit-log')) page = locale === 'ar' ? 'سجل المراجعة' : 'Audit Log'
    else if (pathname.startsWith('/my-tickets')) page = locale === 'ar' ? 'تذاكري' : 'My Tickets'
    else if (pathname.startsWith('/tickets/')) page = locale === 'ar' ? 'تفاصيل التذكرة' : 'Ticket Detail'
    else if (pathname.startsWith('/admin/agents')) page = locale === 'ar' ? 'الوكلاء والمهارات' : 'Agents & Skills'
    else if (pathname.startsWith('/admin/settings')) page = locale === 'ar' ? 'إعدادات التوجيه' : 'Routing Settings'
    else if (pathname.startsWith('/account')) page = locale === 'ar' ? 'الحساب والملف الشخصي' : 'Account'
    document.title = `${page} | SVR System`
  }, [pathname, locale, reviewBadgeCount])

  useEffect(() => {
    if (!authLoading && !user) {
      void navigate({ to: '/login', replace: true })
    }
  }, [authLoading, user, navigate])

  if (authLoading) {
    return (
      <div className='flex min-h-svh items-center justify-center text-sm text-muted-foreground'>
        {t.loading}
      </div>
    )
  }

  if (!user) return null

  return (
    <SearchProvider>
      <LayoutProvider>
        <SidebarProvider defaultOpen={defaultOpen}>
          <SkipToMain />
          <AppSidebar />
          <SidebarInset
            className={cn(
              '@container/content',
              'has-data-[layout=fixed]:h-svh',
              'peer-data-[variant=inset]:has-data-[layout=fixed]:h-[calc(100svh-(var(--spacing)*4))]'
            )}
          >
            <SvrHeader />
            {settings && !settings.auto_routing_enabled && (
              <div
                role='alert'
                className='flex flex-wrap items-center justify-between gap-2 border-b border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm font-medium text-destructive'
              >
                <div className='flex items-center gap-2'>
                  <ShieldOff className='size-4 shrink-0' />
                  <span>{t.killSwitchBanner}</span>
                </div>
                {user.role === 'admin' && (
                  <Button variant='destructive' size='sm' asChild>
                    <Link to='/admin/settings'>{t.manageKillSwitch}</Link>
                  </Button>
                )}
              </div>
            )}
            <div id='main-workspace' className='flex-1'>
              {children ?? <Outlet />}
            </div>
          </SidebarInset>
        </SidebarProvider>
      </LayoutProvider>
    </SearchProvider>
  )
}
