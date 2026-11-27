import { useEffect } from 'react'
import { Link } from '@tanstack/react-router'
import {
  ArrowLeft,
  Clock,
  Keyboard,
  Languages,
  LifeBuoy,
  Mic,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { SvrBrandMark } from '@/components/svr-brand-mark'
import { ThemeSwitch } from '@/components/theme-switch'
import { Badge } from '@/components/ui/badge'
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

export function SupportPage() {
  const { user, locale, setLocale } = useSvr()
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)
  const backTo = !user ? '/login' : user.role === 'agent' ? '/my-tickets' : '/overview'

  useEffect(() => {
    const prev = document.title
    document.title = isAr
      ? 'SVR System | الدعم ودليل التشغيل'
      : 'SVR System | Support & Operations Guide'
    return () => {
      document.title = prev
    }
  }, [isAr])

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
              <Button variant='ghost' size='sm' asChild>
                <Link to='/privacy'>{L('Privacy', 'الخصوصية')}</Link>
              </Button>
              <Button variant='ghost' size='sm' asChild>
                <Link to='/terms'>{L('Terms', 'الشروط')}</Link>
              </Button>
              <Button variant='secondary' size='sm' asChild>
                <Link to='/support'>{L('Support', 'الدعم')}</Link>
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
                <span>{L('Back', 'العودة')}</span>
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main className='mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:py-12'>
        <div className='border-b border-border pb-8'>
          <div className='mb-3 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground'>
            <LifeBuoy className='size-3.5 text-primary' />
            <span>{L('Operations & Help Center', 'مركز الدعم والتشغيل')}</span>
          </div>
          <h1 className='text-3xl font-bold tracking-tight sm:text-4xl'>
            {L('Support & Operations Guide', 'الدعم الفني ودليل التشغيل')}
          </h1>
          <p className='mt-3 max-w-3xl text-sm leading-relaxed text-muted-foreground sm:text-base'>
            {L(
              'Reference standards for Smart Voicemail Router (SVR) operators, supervisors, and system administrators: callback SLA targets, audio intake rules, role permissions, and escalation contacts.',
              'المرجع التشغيلي لمشغلي ومشرفي ومسؤولي نظام موجّه البريد الصوتي الذكي (SVR): مستهدفات مهلة المعاودة، معايير استقبال الصوت، صلاحيات الأدوار، وقنوات التصعيد.'
            )}
          </p>
        </div>

        <div className='mt-8 grid gap-6 md:grid-cols-2'>
          {/* 1. Callback SLA Targets */}
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Clock className='size-4 text-primary' />
                <span>{L('Callback SLA Targets', 'مستهدفات مهلة المعاودة (SLA)')}</span>
              </CardTitle>
              <CardDescription>
                {L(
                  'Deterministic priority buckets (Score 1 to 6) govern target callback windows.',
                  'تحدد درجات الأولوية الحتمية (من 1 إلى 6) المهلة المستهدفة لمعاودة الاتصال بالمشترك.'
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3 text-sm'>
              <div className='flex items-center justify-between rounded-lg border border-border px-3 py-2'>
                <div className='flex items-center gap-2'>
                  <Badge variant='destructive'>{L('Urgent', 'عاجل جدا')}</Badge>
                  <span className='text-muted-foreground'>{L('Score 5 - 6', 'الدرجة 5 - 6')}</span>
                </div>
                <span className='font-mono font-semibold'>15 min</span>
              </div>
              <div className='flex items-center justify-between rounded-lg border border-border px-3 py-2'>
                <div className='flex items-center gap-2'>
                  <Badge variant='secondary'>{L('High', 'مرتفع')}</Badge>
                  <span className='text-muted-foreground'>{L('Score 4', 'الدرجة 4')}</span>
                </div>
                <span className='font-mono font-semibold'>1 hour</span>
              </div>
              <div className='flex items-center justify-between rounded-lg border border-border px-3 py-2'>
                <div className='flex items-center gap-2'>
                  <Badge variant='outline'>{L('Normal', 'عادي')}</Badge>
                  <span className='text-muted-foreground'>{L('Score 3', 'الدرجة 3')}</span>
                </div>
                <span className='font-mono font-semibold'>4 hours</span>
              </div>
              <div className='flex items-center justify-between rounded-lg border border-border px-3 py-2'>
                <div className='flex items-center gap-2'>
                  <Badge variant='outline'>{L('Low', 'منخفض')}</Badge>
                  <span className='text-muted-foreground'>{L('Score 1 - 2', 'الدرجة 1 - 2')}</span>
                </div>
                <span className='font-mono font-semibold'>24 hours</span>
              </div>
            </CardContent>
          </Card>

          {/* 2. Audio Intake & Security Standards */}
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Mic className='size-4 text-primary' />
                <span>{L('Audio Intake & Security Standards', 'معايير استقبال الصوت والأمان')}</span>
              </CardTitle>
              <CardDescription>
                {L(
                  'Self-hosted Arabic ASR (Cohere Arabic / Whisper fallback) and Fernet vault requirements with zero third-party egress.',
                  'متطلبات الاستقبال المحلي والتشفير دون إرسال أي بيانات صوتية لجهات خارجية.'
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3 text-sm'>
              <div className='flex items-center justify-between border-b border-border pb-2'>
                <span className='text-muted-foreground'>{L('Supported Formats', 'الصيغ المدعومة')}</span>
                <span className='font-mono font-medium'>WAV, MP3, M4A</span>
              </div>
              <div className='flex items-center justify-between border-b border-border pb-2'>
                <span className='text-muted-foreground'>{L('Max Duration & Size', 'الحد الأقصى للمدة والحجم')}</span>
                <span className='font-mono font-medium'>&lt;= 60s / &lt;= 25 MB</span>
              </div>
              <div className='flex items-center justify-between border-b border-border pb-2'>
                <span className='text-muted-foreground'>{L('Normalization & Dedup', 'التهيئة ومنع التكرار')}</span>
                <span className='font-mono font-medium'>16 kHz Mono · SHA-256</span>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>{L('Encryption at Rest', 'التشفير أثناء التخزين')}</span>
                <span className='font-mono font-medium'>Fernet AES-128-CBC + HMAC</span>
              </div>
            </CardContent>
          </Card>

          {/* 3. Role Access Matrix */}
          <Card className='md:col-span-2'>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Users className='size-4 text-primary' />
                <span>{L('Role Access Matrix', 'مصفوفة صلاحيات الأدوار')}</span>
              </CardTitle>
              <CardDescription>
                {L(
                  'Strict 3-tier RBAC scoping enforced across API endpoints and console routes.',
                  'تقييد صارم للصلاحيات عبر ثلاث مستويات على مستوى الواجهة وواجهات البرمجة.'
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{L('Role', 'الدور')}</TableHead>
                    <TableHead>{L('Primary Workspace', 'مساحة العمل الرئيسية')}</TableHead>
                    <TableHead>{L('Permissions', 'الصلاحيات')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell className='font-semibold'>Admin</TableCell>
                    <TableCell className='font-mono text-xs'>/overview</TableCell>
                    <TableCell className='text-muted-foreground'>
                      {L(
                        'Full platform access: operations, overrides, evaluation, audit log, agents & skills, and routing settings.',
                        'وصول كامل للنظام: العمليات، التعديلات اليدوية، التقييم، سجل المراجعة، إدارة الوكلاء وإعدادات التوجيه.'
                      )}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className='font-semibold'>Supervisor</TableCell>
                    <TableCell className='font-mono text-xs'>/overview</TableCell>
                    <TableCell className='text-muted-foreground'>
                      {L(
                        'Operations overview, full callback queue, human routing overrides, model evaluation, and audit log.',
                        'نظرة عامة على العمليات، طابور المعاودة الكامل، مراجعة التوجيه البشري، تقييم النماذج، وسجل المراجعة.'
                      )}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className='font-semibold'>Agent</TableCell>
                    <TableCell className='font-mono text-xs'>/my-tickets</TableCell>
                    <TableCell className='text-muted-foreground'>
                      {L(
                        'Assigned callback tickets, encrypted audio playback, grounded bilingual scripts, and status updates.',
                        'تذاكر المعاودة المعينة فقط، تشغيل التسجيل المشفر، نص المكالمة المقترح، وتحديث حالة التنفيذ.'
                      )}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* 4. Keyboard Shortcuts & Escalation Desk */}
          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <Keyboard className='size-4 text-primary' />
                <span>{L('Keyboard Shortcuts', 'اختصارات لوحة المفاتيح')}</span>
              </CardTitle>
              <CardDescription>
                {L(
                  'Quick navigation and command triggers inside the authenticated console.',
                  'تنقل سريع وأوامر فورية داخل لوحة التحكم.'
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3 text-sm'>
              <div className='flex items-center justify-between border-b border-border pb-2'>
                <span className='text-muted-foreground'>
                  {L('Open Global Command & Ticket Search', 'فتح البحث الشامل والتذاكر')}
                </span>
                <kbd className='rounded border border-border bg-muted px-2 py-0.5 font-mono text-xs'>
                  Ctrl + K / Cmd + K
                </kbd>
              </div>
              <div className='flex items-center justify-between border-b border-border pb-2'>
                <span className='text-muted-foreground'>
                  {L('Toggle Navigation Sidebar', 'طي أو فتح القائمة الجانبية')}
                </span>
                <kbd className='rounded border border-border bg-muted px-2 py-0.5 font-mono text-xs'>
                  Ctrl + B / Cmd + B
                </kbd>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>
                  {L('Close Active Dialog or Sheet', 'إغلاق النافذة الحالية')}
                </span>
                <kbd className='rounded border border-border bg-muted px-2 py-0.5 font-mono text-xs'>
                  Esc
                </kbd>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className='flex items-center gap-2 text-base'>
                <ShieldCheck className='size-4 text-primary' />
                <span>{L('Escalation & Support Desk', 'مكتب الدعم والتصعيد')}</span>
              </CardTitle>
              <CardDescription>
                {L(
                  'Direct contacts for access provisioning, password resets, and data protection.',
                  'قنوات التواصل المباشر لطلبات الصلاحيات وإعادة تعيين كلمات المرور وحماية البيانات.'
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className='space-y-3 text-sm'>
              <div className='flex items-center justify-between border-b border-border pb-2'>
                <span className='text-muted-foreground'>{L('Platform Administrator', 'مسؤول النظام')}</span>
                <a href='mailto:admin@telecom.local' className='font-mono text-primary hover:underline'>
                  admin@telecom.local
                </a>
              </div>
              <div className='flex items-center justify-between border-b border-border pb-2'>
                <span className='text-muted-foreground'>{L('Data Protection Officer', 'مسؤول حماية البيانات')}</span>
                <a href='mailto:dpo@telecom.local' className='font-mono text-primary hover:underline'>
                  dpo@telecom.local
                </a>
              </div>
              <div className='flex items-center justify-between'>
                <span className='text-muted-foreground'>{L('Compliance Policies', 'سياسات الامتثال')}</span>
                <div className='flex items-center gap-3'>
                  <Link to='/privacy' className='text-primary hover:underline'>
                    {L('Privacy', 'الخصوصية')}
                  </Link>
                  <Link to='/terms' className='text-primary hover:underline'>
                    {L('Terms', 'الشروط')}
                  </Link>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
