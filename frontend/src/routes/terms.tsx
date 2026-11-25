import { createFileRoute } from '@tanstack/react-router'
import { TermsPage } from '@/features/legal/legal-pages'

export const Route = createFileRoute('/terms')({
  component: TermsPage,
})
