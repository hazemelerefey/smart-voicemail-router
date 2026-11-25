import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { EvaluationPage } from '@/features/evaluation'

export const Route = createFileRoute('/_authenticated/evaluation')({
  component: () => (
    <RoleGuard allowedRoles={['supervisor', 'admin']}>
      <EvaluationPage />
    </RoleGuard>
  ),
})
