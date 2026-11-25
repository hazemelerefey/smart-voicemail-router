import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Lock,
  Play,
  UserX,
} from 'lucide-react'
import { labelForBucket, labelForStatus, type Locale } from '@/lib/i18n'
export { PriorityScoreAvatar } from '@/components/svr/priority-avatar'

export function TicketStatusText({ status, locale }: { status: string; locale: Locale }) {
  const label = labelForStatus(status, locale)
  switch (status) {
    case 'failed':
      return (
        <span className='inline-flex items-center gap-1.5 text-xs font-semibold text-destructive'>
          <AlertCircle className='size-3.5 shrink-0' />
          {label}
        </span>
      )
    case 'unassigned':
      return (
        <span className='inline-flex items-center gap-1.5 text-xs font-semibold text-amber-600 dark:text-amber-400'>
          <UserX className='size-3.5 shrink-0' />
          {label}
        </span>
      )
    case 'processing':
    case 'received':
      return (
        <span className='inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 dark:text-sky-400'>
          <Clock className='size-3.5 shrink-0' />
          {label}
        </span>
      )
    case 'in_progress':
      return (
        <span className='inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 dark:text-sky-400'>
          <Play className='size-3.5 shrink-0' />
          {label}
        </span>
      )
    case 'ready':
      return (
        <span className='inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400'>
          <CheckCircle2 className='size-3.5 shrink-0' />
          {label}
        </span>
      )
    case 'resolved':
      return (
        <span className='inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-600 dark:text-emerald-400'>
          <Check className='size-3.5 shrink-0' />
          {label}
        </span>
      )
    case 'closed':
      return (
        <span className='inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground'>
          <Lock className='size-3.5 shrink-0' />
          {label}
        </span>
      )
    default:
      return <span className='text-xs font-medium text-muted-foreground'>{label}</span>
  }
}

export function BucketText({
  bucket,
  locale,
}: {
  bucket: string | null | undefined
  locale: Locale
}) {
  if (!bucket) return <span className='text-xs text-muted-foreground'>-</span>
  const label = labelForBucket(bucket, locale)
  if (bucket === 'urgent') {
    return (
      <span className='inline-flex items-center gap-1 text-xs font-bold text-destructive'>
        <AlertTriangle className='size-3.5 shrink-0' />
        {label}
      </span>
    )
  }
  if (bucket === 'high') {
    return (
      <span className='text-xs font-semibold text-amber-600 dark:text-amber-400'>
        {label}
      </span>
    )
  }
  if (bucket === 'normal') {
    return (
      <span className='text-xs font-medium text-blue-600 dark:text-sky-400'>
        {label}
      </span>
    )
  }
  return <span className='text-xs text-muted-foreground'>{label}</span>
}

export function scoreSquareClass(bucket: string | null | undefined): string {
  if (bucket === 'urgent') return 'bg-destructive text-white'
  if (bucket === 'high') return 'bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300 border border-amber-500/30 dark:border-amber-500/35'
  if (bucket === 'normal') return 'bg-secondary text-foreground border border-border'
  return 'bg-muted text-muted-foreground border border-border'
}
