import { createFileRoute } from '@tanstack/react-router'
import { RoleGuard } from '@/components/svr/role-guard'
import { ReviewQueuePage } from '@/features/review-queue'

export const Route = createFileRoute('/_authenticated/review-queue')({
  component: () => (
    <RoleGuard allowedRoles={['supervisor', 'admin']}>
      <ReviewQueuePage />
    </RoleGuard>
  ),
})
