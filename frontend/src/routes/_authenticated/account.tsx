import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { AccountPage } from '@/features/account'

export const Route = createFileRoute('/_authenticated/account')({
  component: () => (
    <RoleGuard allowedRoles={['admin', 'supervisor', 'agent']}>
      <AccountPage />
    </RoleGuard>
  ),
})
