import {
  AlertCircle,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  CheckCircle2,
  Clock,
  Lock,
  Play,
  UserX,
} from 'lucide-react'
import { labelForBucket, labelForStatus, type Locale } from '@/lib/i18n'
export { PriorityScoreAvatar } from '@/components/svr/priority-avatar'

const TAG_BASE =
  'inline-flex w-fit items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold leading-4 tracking-tight whitespace-nowrap'

export function TicketStatusText({ status, locale }: { status: string; locale: Locale }) {
  const label = labelForStatus(status, locale)
  switch (status) {
    case 'failed':
      return (
        <span className={`${TAG_BASE} border-transparent bg-destructive text-white dark:bg-destructive/85 dark:text-white`}>
          <AlertCircle className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'unassigned':
      return (
        <span className={`${TAG_BASE} border-amber-600/30 bg-amber-500/12 text-amber-800 dark:border-amber-500/35 dark:bg-amber-500/18 dark:text-amber-300`}>
          <UserX className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'processing':
    case 'received':
      return (
        <span className={`${TAG_BASE} border-indigo-600/25 bg-indigo-500/12 text-indigo-700 dark:border-indigo-400/30 dark:bg-indigo-500/18 dark:text-indigo-300`}>
          <Clock className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'in_progress':
      return (
        <span className={`${TAG_BASE} border-sky-600/25 bg-sky-500/12 text-sky-700 dark:border-sky-400/30 dark:bg-sky-500/18 dark:text-sky-300`}>
          <Play className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'ready':
      return (
        <span className={`${TAG_BASE} border-teal-600/25 bg-teal-500/12 text-teal-700 dark:border-teal-400/30 dark:bg-teal-500/18 dark:text-teal-300`}>
          <CheckCircle2 className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'resolved':
      return (
        <span className={`${TAG_BASE} border-emerald-600/25 bg-emerald-500/12 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/18 dark:text-emerald-300`}>
          <Check className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'closed':
      return (
        <span className={`${TAG_BASE} border-border bg-muted/70 text-muted-foreground`}>
          <Lock className='size-3 shrink-0' />
          {label}
        </span>
      )
    default:
      return (
        <span className={`${TAG_BASE} border-border bg-muted/70 text-muted-foreground`}>
          {label}
        </span>
      )
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
      <span className={`${TAG_BASE} border-transparent bg-destructive text-white dark:bg-destructive/85 dark:text-white`}>
        <AlertTriangle className='size-3 shrink-0' />
        {label}
      </span>
    )
  }
  if (bucket === 'high') {
    return (
      <span className={`${TAG_BASE} border-amber-600/30 bg-amber-500/15 text-amber-800 dark:border-amber-500/35 dark:bg-amber-500/20 dark:text-amber-300`}>
        <ArrowUp className='size-3 shrink-0' />
        {label}
      </span>
    )
  }
  if (bucket === 'normal') {
    return (
      <span className={`${TAG_BASE} border-blue-600/25 bg-blue-500/10 text-blue-700 dark:border-sky-400/30 dark:bg-sky-500/15 dark:text-sky-300`}>
        <span className='size-1.5 shrink-0 rounded-full bg-current' />
        {label}
      </span>
    )
  }
  return (
    <span className={`${TAG_BASE} border-border bg-muted/70 text-muted-foreground`}>
      <ArrowDown className='size-3 shrink-0' />
      {label}
    </span>
  )
}

export function scoreSquareClass(bucket: string | null | undefined): string {
  if (bucket === 'urgent') return 'bg-destructive text-white'
  if (bucket === 'high') return 'bg-amber-500/15 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300 border border-amber-500/30 dark:border-amber-500/35'
  if (bucket === 'normal') return 'bg-secondary text-foreground border border-border'
  return 'bg-muted text-muted-foreground border border-border'
}
