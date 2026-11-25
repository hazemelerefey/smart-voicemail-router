import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { AuditLogPage } from '@/features/audit-log'

export const Route = createFileRoute('/_authenticated/audit-log')({
  component: () => (
    <RoleGuard allowedRoles={['supervisor', 'admin']}>
      <AuditLogPage />
    </RoleGuard>
  ),
})
