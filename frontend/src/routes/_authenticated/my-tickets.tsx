import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { MyTicketsPage } from '@/features/my-tickets'

export const Route = createFileRoute('/_authenticated/my-tickets')({
  component: () => (
    <RoleGuard allowedRoles={['agent']}>
      <MyTicketsPage />
    </RoleGuard>
  ),
})
