import { Link } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { SvrBrandMark } from '@/components/svr-brand-mark'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  const { user, locale } = useSvr()
  const isAr = locale === 'ar'
  const homePath = !user ? '/login' : user.role === 'agent' ? '/my-tickets' : '/overview'

  return (
    <div
      dir={isAr ? 'rtl' : 'ltr'}
      className='flex min-h-svh flex-col items-center justify-center bg-background px-4 text-center text-foreground'
    >
      <div className='flex flex-col items-center gap-4 max-w-md'>
        <SvrBrandMark className='size-14' />
        <p className='font-mono text-xs font-semibold uppercase tracking-widest text-muted-foreground'>
          404
        </p>
        <h1 className='text-2xl font-bold tracking-tight sm:text-3xl'>
          {isAr ? 'الصفحة غير موجودة' : 'Page not found'}
        </h1>
        <p className='text-sm text-muted-foreground'>
          {isAr
            ? 'الرابط الذي طلبته غير متاح أو تم نقله. يمكنك العودة إلى مساحة العمل الرئيسية.'
            : 'The requested page does not exist or may have been moved. Return to your primary workspace.'}
        </p>
        <div className='mt-2 flex items-center gap-3'>
          <Button asChild>
            <Link to={homePath}>
              <ArrowLeft className='size-4' />
              <span>{isAr ? 'العودة للرئيسية' : 'Back to Workspace'}</span>
            </Link>
          </Button>
          <Button variant='outline' asChild>
            <Link to='/support'>{isAr ? 'الدعم' : 'Support'}</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
