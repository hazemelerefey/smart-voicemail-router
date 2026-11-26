import { createRootRoute, Outlet } from '@tanstack/react-router'
import { NotFoundPage } from '@/components/svr/not-found-page'
import { Toaster } from '@/components/ui/sonner'

export const Route = createRootRoute({
  component: () => (
    <>
      <Outlet />
      <Toaster duration={4000} />
    </>
  ),
  notFoundComponent: NotFoundPage,
})
