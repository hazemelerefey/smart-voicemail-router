import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { AdminAgentsPage } from '@/features/admin/agents-page'

export const Route = createFileRoute('/_authenticated/admin/agents')({
  component: () => (
    <RoleGuard allowedRoles={['admin']}>
      <AdminAgentsPage />
    </RoleGuard>
  ),
})
