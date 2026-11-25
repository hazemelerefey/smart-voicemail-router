import { Link } from '@tanstack/react-router'
import { ShieldAlert } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Main } from '@/components/layout/main'
import type { UserRole } from '@/lib/types'

export function RoleGuard({
  allowedRoles,
  children,
}: {
  allowedRoles: UserRole[]
  children: React.ReactNode
}) {
  const { user, locale } = useSvr()
  if (!user) return null
  if (!allowedRoles.includes(user.role)) {
    const fallback = user.role === 'agent' ? '/my-tickets' : '/overview'
    return (
      <Main>
        <Card className='mx-auto mt-10 max-w-md'>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <ShieldAlert className='size-5 text-destructive' />
              {locale === 'ar' ? 'غير مصرح بالوصول' : 'Access Restricted'}
            </CardTitle>
            <CardDescription>
              {locale === 'ar'
                ? 'حسابك لا يمتلك صلاحية فتح هذه الصفحة.'
                : 'Your current operator role does not have permission to view this page.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to={fallback}>
                {locale === 'ar' ? 'الانتقال إلى صفحتك الرئيسية' : 'Go to Your Workspace'}
              </Link>
            </Button>
          </CardContent>
        </Card>
      </Main>
    )
  }
  return <>{children}</>
}
