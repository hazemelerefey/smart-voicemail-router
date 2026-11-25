import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { AdminSettingsPage } from '@/features/admin/settings-page'

export const Route = createFileRoute('/_authenticated/admin/settings')({
  component: () => (
    <RoleGuard allowedRoles={['admin']}>
      <AdminSettingsPage />
    </RoleGuard>
  ),
})
