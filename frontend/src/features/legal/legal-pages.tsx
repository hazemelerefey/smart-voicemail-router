import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { SvrBrandMark } from '@/components/svr-brand-mark'

export function PrivacyPage() {
  const { user, locale } = useSvr()
  const isAr = locale === 'ar'
  const backTo = !user ? '/login' : user.role === 'agent' ? '/my-tickets' : '/overview'

  return (
    <div className='container max-w-3xl py-10'>
      <div className='mb-6 flex items-center justify-between'>
        <div className='flex items-center gap-2.5'>
          <SvrBrandMark className='size-8' />
          <span className='font-bold'>SVR Operations</span>
        </div>
        <Button variant='outline' size='sm' asChild>
          <Link to={backTo}>
            <ArrowLeft className='size-4' />
            {isAr ? 'العودة' : 'Back'}
          </Link>
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{isAr ? 'إشعار الخصوصية وحماية البيانات' : 'Privacy Notice'}</CardTitle>
        </CardHeader>
        <CardContent className='space-y-3 text-sm text-muted-foreground leading-relaxed'>
          <p>
            {isAr
              ? 'يعمل نظام Smart Voicemail Router بالكامل على خوادم المشغل. لا يتم إرسال أي تسجيلات صوتية خام إلى أي خدمة ذكاء اصطناعي خارجية افتراضيا.'
              : 'Smart Voicemail Router (SVR) processes all subscriber voicemails on local operator infrastructure. Zero raw audio is transmitted to third-party AI services by default.'}
          </p>
          <p>
            {isAr
              ? 'يتم تشفير الملفات الصوتية والنصوص المفرغة باستخدام Fernet أثناء التخزين، وتنتهي جلسات المشغلين المحمية تلقائيا بعد 8 ساعات من عدم النشاط.'
              : 'Stored recordings and transcripts are encrypted at rest with Fernet, access is governed by strict role-based controls, and HttpOnly operator sessions expire after 8 hours of inactivity.'}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

export function TermsPage() {
  const { user, locale } = useSvr()
  const isAr = locale === 'ar'
  const backTo = !user ? '/login' : user.role === 'agent' ? '/my-tickets' : '/overview'

  return (
    <div className='container max-w-3xl py-10'>
      <div className='mb-6 flex items-center justify-between'>
        <div className='flex items-center gap-2.5'>
          <SvrBrandMark className='size-8' />
          <span className='font-bold'>SVR Operations</span>
        </div>
        <Button variant='outline' size='sm' asChild>
          <Link to={backTo}>
            <ArrowLeft className='size-4' />
            {isAr ? 'العودة' : 'Back'}
          </Link>
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{isAr ? 'شروط استخدام المشغلين' : 'Operator Terms of Use'}</CardTitle>
        </CardHeader>
        <CardContent className='space-y-3 text-sm text-muted-foreground leading-relaxed'>
          <p>
            {isAr
              ? 'يقتصر استخدام النظام على موظفي ومشرفي خدمة عملاء الاتصالات المصرح لهم لمتابعة شكاوى المشتركين.'
              : 'Access to SVR Operations is restricted to authorized telecom customer-care personnel for subscriber complaint triage, callback routing, and quality auditing.'}
          </p>
          <p>
            {isAr
              ? 'جميع تعديلات التصنيف وإعادة التوجيه والإعدادات تسجل بشكل دائم في سجل التدقيق.'
              : 'All label corrections, ticket reassignments, audio playback requests, and administrative configuration changes are permanently recorded in the audit log.'}
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
