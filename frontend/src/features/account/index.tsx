import { useEffect, useState } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  Activity,
  CheckCircle2,
  Languages,
  Laptop,
  LifeBuoy,
  LogOut,
  Moon,
  ShieldCheck,
  Sun,
  UserCheck,
  Wifi,
} from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { useTheme } from '@/context/theme-provider'
import { Main } from '@/components/layout/main'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api } from '@/lib/api'
import { labelForSkill } from '@/lib/i18n'
import { formatUtcTimestamp } from '@/lib/taxonomy'
import type { AgentResponse } from '@/lib/types'

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('')
}

export function AccountPage() {
  const { user, locale, setLocale, logout, wsStatus, reconnectWs } = useSvr()
  const { theme, setTheme } = useTheme()
  const navigate = useNavigate()
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [linkedAgent, setLinkedAgent] = useState<AgentResponse | null>(null)

  useEffect(() => {
    if (!user?.linked_agent_id) {
      setLinkedAgent(null)
      return
    }
    let cancelled = false
    api
      .listAgents()
      .then((list) => {
        if (cancelled) return
        const found = list.find((a) => a.id === user.linked_agent_id) ?? null
        setLinkedAgent(found)
      })
      .catch(() => {
        if (!cancelled) setLinkedAgent(null)
      })
    return () => {
      cancelled = true
    }
  }, [user?.linked_agent_id])

  if (!user) return null

  const handleSignOut = async () => {
    await logout()
    void navigate({ to: '/login', replace: true })
  }

  return (
    <Main>
      <div className='mb-6 flex flex-wrap items-center justify-between gap-4'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('Account & Profile', 'الحساب والملف الشخصي')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Operator identity, assigned telecom skills, workspace preferences, and active session security.',
              'هوية المشغّل، المهارات المعينة، تفضيلات مساحة العمل، وأمان الجلسة الحالية.'
            )}
          </p>
        </div>
      </div>

      <div className='grid gap-6 lg:grid-cols-2'>
        {/* Operator Identity Card */}
        <Card>
          <CardHeader>
            <CardTitle className='flex items-center gap-2 text-base'>
              <UserCheck className='size-4 text-primary' />
              <span>{L('Operator Identity', 'هوية المشغّل')}</span>
            </CardTitle>
            <CardDescription>
              {L('Managed by your organization administrator.', 'تدار بواسطة مسؤول المؤسسة.')}
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4'>
            <div className='flex items-center gap-4'>
              <Avatar className='h-14 w-14 rounded-xl'>
                <AvatarFallback className='rounded-xl bg-primary text-base font-bold text-primary-foreground'>
                  {initials(user.full_name)}
                </AvatarFallback>
              </Avatar>
              <div className='min-w-0 flex-1'>
                <div className='flex flex-wrap items-center gap-2'>
                  <h2 className='truncate text-lg font-semibold'>{user.full_name}</h2>
                  <Badge variant='secondary'>{user.role.toUpperCase()}</Badge>
                  <Badge variant={user.active ? 'outline' : 'destructive'}>
                    {user.active ? L('Active', 'نشط') : L('Inactive', 'غير نشط')}
                  </Badge>
                </div>
                <p className='truncate text-sm text-muted-foreground'>{user.email}</p>
              </div>
            </div>

            <div className='space-y-2.5 border-t border-border pt-4 text-sm'>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>{L('Organization ID', 'معرّف المؤسسة')}</span>
                <span className='font-mono text-xs'>{user.organization_id}</span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>{L('Account Created', 'تاريخ الإنشاء')}</span>
                <span className='font-mono text-xs'>{formatUtcTimestamp(user.created_at, locale)}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Workspace Preferences Card */}
        <Card>
          <CardHeader>
            <CardTitle className='flex items-center gap-2 text-base'>
              <Languages className='size-4 text-primary' />
              <span>{L('Workspace Preferences', 'تفضيلات مساحة العمل')}</span>
            </CardTitle>
            <CardDescription>
              {L(
                'Light Mode is the primary workspace theme; Dark Mode (OLED) is secondary.',
                'الوضع الفاتح هو المظهر الرئيسي؛ والوضع الداكن (OLED) ثانوي.'
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-5 text-sm'>
            <div className='space-y-2'>
              <span className='text-xs font-medium uppercase tracking-wider text-muted-foreground'>
                {L('Theme', 'المظهر')}
              </span>
              <div className='flex flex-wrap gap-2'>
                <Button
                  variant={theme === 'light' ? 'default' : 'outline'}
                  size='sm'
                  onClick={() => setTheme('light')}
                >
                  <Sun className='size-4' />
                  <span>{L('Light (Primary)', 'فاتح (رئيسي)')}</span>
                </Button>
                <Button
                  variant={theme === 'dark' ? 'default' : 'outline'}
                  size='sm'
                  onClick={() => setTheme('dark')}
                >
                  <Moon className='size-4' />
                  <span>{L('Dark (OLED)', 'داكن (OLED)')}</span>
                </Button>
                <Button
                  variant={theme === 'system' ? 'default' : 'outline'}
                  size='sm'
                  onClick={() => setTheme('system')}
                >
                  <Laptop className='size-4' />
                  <span>{L('System', 'النظام')}</span>
                </Button>
              </div>
            </div>

            <div className='space-y-2'>
              <span className='text-xs font-medium uppercase tracking-wider text-muted-foreground'>
                {L('Language & Direction', 'اللغة والاتجاه')}
              </span>
              <div className='flex flex-wrap gap-2'>
                <Button
                  variant={locale === 'en' ? 'default' : 'outline'}
                  size='sm'
                  onClick={() => setLocale('en')}
                >
                  English (LTR)
                </Button>
                <Button
                  variant={locale === 'ar' ? 'default' : 'outline'}
                  size='sm'
                  onClick={() => setLocale('ar')}
                >
                  العربية (RTL)
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Linked Agent Skills & Capacity Card (only if linked_agent_id exists) */}
        {linkedAgent && (
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Activity className='size-4 text-primary' />
                <span>{L('Telecom Skills & Shift Capacity', 'المهارات وسعة المناوبة')}</span>
              </CardTitle>
              <CardDescription>
                {L(
                  'Live skill routing profile linked to your operator account.',
                  'ملف التوجيه المهاري المرتبط بحسابك.'
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3 text-sm'>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>{L('Agent Queue Name', 'اسم الطابور')}</span>
                <span className='font-medium'>{linkedAgent.name}</span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>{L('Shift Availability', 'حالة المناوبة')}</span>
                <Badge variant={linkedAgent.available ? 'secondary' : 'outline'}>
                  {linkedAgent.available ? L('On Shift', 'في المناوبة') : L('Paused', 'متوقف مؤقتا')}
                </Badge>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>{L('Active Workload', 'الحمل الحالي')}</span>
                <span className='font-mono font-semibold'>
                  {linkedAgent.current_load} / {linkedAgent.capacity}
                </span>
              </div>
              <div className='flex flex-wrap items-center justify-between gap-2 pt-1'>
                <span className='text-muted-foreground'>{L('Assigned Skills', 'المهارات المعينة')}</span>
                <div className='flex flex-wrap gap-1.5'>
                  {linkedAgent.skills.map((sk) => (
                    <Badge key={sk} variant='outline'>
                      {labelForSkill(sk, locale)}
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Session & Security Card */}
        <Card className={linkedAgent ? undefined : 'lg:col-span-2'}>
          <CardHeader>
            <CardTitle className='flex items-center gap-2 text-base'>
              <ShieldCheck className='size-4 text-primary' />
              <span>{L('Session & Security', 'الجلسة والأمان')}</span>
            </CardTitle>
            <CardDescription>
              {L(
                'Transport, CSRF protection, and live WebSocket synchronization status.',
                'حالة الجلسة المشفرة، الحماية ضد التزوير، والمزامنة الفورية.'
              )}
            </CardDescription>
          </CardHeader>
          <CardContent className='space-y-4 text-sm'>
            <div className='grid gap-3 sm:grid-cols-2'>
              <div className='flex items-center justify-between rounded-lg border border-border px-3 py-2'>
                <span className='text-muted-foreground'>{L('Session Cookie', 'ملف الجلسة')}</span>
                <span className='inline-flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400'>
                  <CheckCircle2 className='size-3.5' />
                  HttpOnly + CSRF
                </span>
              </div>
              <div className='flex items-center justify-between rounded-lg border border-border px-3 py-2'>
                <span className='text-muted-foreground'>{L('WebSocket Sync', 'المزامنة الفورية')}</span>
                <div className='flex items-center gap-2'>
                  <span className='inline-flex items-center gap-1 font-mono text-xs'>
                    <Wifi className='size-3.5 text-primary' />
                    {wsStatus}
                  </span>
                  {wsStatus !== 'connected' && (
                    <Button variant='ghost' size='sm' className='h-6 px-2 text-xs' onClick={reconnectWs}>
                      {L('Retry', 'إعادة')}
                    </Button>
                  )}
                </div>
              </div>
            </div>

            <div className='flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4'>
              <div className='flex flex-wrap items-center gap-3 text-xs'>
                <Button variant='outline' size='sm' asChild>
                  <Link to='/support'>
                    <LifeBuoy className='size-3.5' />
                    <span>{L('Support Guide', 'دليل الدعم')}</span>
                  </Link>
                </Button>
                <Button variant='ghost' size='sm' asChild>
                  <Link to='/privacy'>{L('Privacy', 'الخصوصية')}</Link>
                </Button>
                <Button variant='ghost' size='sm' asChild>
                  <Link to='/terms'>{L('Terms', 'الشروط')}</Link>
                </Button>
              </div>
              <Button variant='destructive' size='sm' onClick={() => void handleSignOut()}>
                <LogOut className='size-4' />
                <span>{L('Sign out', 'تسجيل الخروج')}</span>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </Main>
  )
}
