import { createFileRoute } from '@tanstack/react-router'
import { PrivacyPage } from '@/features/legal/legal-pages'

export const Route = createFileRoute('/privacy')({
  component: PrivacyPage,
})
