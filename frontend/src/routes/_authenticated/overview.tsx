import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { OverviewPage } from '@/features/overview'

export const Route = createFileRoute('/_authenticated/overview')({
  component: () => (
    <RoleGuard allowedRoles={['supervisor', 'admin']}>
      <OverviewPage />
    </RoleGuard>
  ),
})
