import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { CallbackQueuePage } from '@/features/queue'

export const Route = createFileRoute('/_authenticated/dashboard')({
  component: () => (
    <RoleGuard allowedRoles={['supervisor', 'admin']}>
      <CallbackQueuePage />
    </RoleGuard>
  ),
})
