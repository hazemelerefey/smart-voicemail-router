import {
  Activity,
  AlertTriangle,
  BarChart3,
  History,
  Inbox,
  LayoutDashboard,
  PhoneCall,
  Settings,
  Users,
} from 'lucide-react'
import { type Locale, UI_COPY } from '@/lib/i18n'
import type { UserRole } from '@/lib/types'
import type { NavGroup } from './types'

export function buildSvrNavGroups(
  role: UserRole,
  locale: Locale,
  reviewBadgeCount?: number
): NavGroup[] {
  const t = UI_COPY[locale]
  const isSupervisorOrAdmin = role === 'supervisor' || role === 'admin'
  const isAdmin = role === 'admin'

  const opsItems: NavGroup['items'] = []

  if (isSupervisorOrAdmin) {
    opsItems.push(
      {
        title: locale === 'ar' ? 'نظرة عامة' : 'Overview',
        url: '/overview',
        icon: LayoutDashboard,
      },
      {
        title: t.navQueue,
        url: '/dashboard',
        icon: Inbox,
      },
      {
        title: t.navReviewQueue,
        url: '/review-queue',
        icon: AlertTriangle,
        badge:
          typeof reviewBadgeCount === 'number' && reviewBadgeCount > 0
            ? String(reviewBadgeCount)
            : undefined,
      },
      {
        title: t.navEvaluation,
        url: '/evaluation',
        icon: BarChart3,
      },
      {
        title: t.navAuditLog,
        url: '/audit-log',
        icon: History,
      }
    )
  }

  if (role === 'agent') {
    opsItems.push({
      title: t.navMyTickets,
      url: '/my-tickets',
      icon: PhoneCall,
    })
  }

  const groups: NavGroup[] = [{ title: t.navSectionOps, items: opsItems }]

  if (isAdmin) {
    groups.push({
      title: t.navSectionAdmin,
      items: [
        {
          title: t.navAgents,
          url: '/admin/agents',
          icon: Users,
        },
        {
          title: t.navSettings,
          url: '/admin/settings',
          icon: Settings,
        },
      ],
    })
  }

  return groups
}

export { Activity }
