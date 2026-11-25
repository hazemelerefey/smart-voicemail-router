import { createFileRoute } from '@tanstack/react-router'
import { TicketDetailPage } from '@/features/tickets/ticket-detail'

export const Route = createFileRoute('/_authenticated/tickets/$id')({
  component: function TicketDetailRoute() {
    const { id } = Route.useParams()
    return <TicketDetailPage ticketId={id} />
  },
})
