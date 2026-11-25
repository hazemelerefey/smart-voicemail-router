import { useEffect } from 'react'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useSvr } from '@/context/svr-provider'
import { UI_COPY } from '@/lib/i18n'

function HomeRedirect() {
  const { user, authLoading, locale } = useSvr()
  const navigate = useNavigate()
  const t = UI_COPY[locale]

  useEffect(() => {
    if (authLoading) return
    if (!user) {
      void navigate({ to: '/login', replace: true })
    } else if (user.role === 'agent') {
      void navigate({ to: '/my-tickets', replace: true })
    } else {
      void navigate({ to: '/overview', replace: true })
    }
  }, [authLoading, user, navigate])

  return (
    <div className='flex min-h-svh items-center justify-center text-sm text-muted-foreground'>
      {t.loading}
    </div>
  )
}

export const Route = createFileRoute('/')({
  component: HomeRedirect,
})
