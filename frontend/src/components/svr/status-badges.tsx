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
  'inline-flex w-fit items-center gap-1 rounded-md border-0 px-2 py-0.5 text-[11px] font-semibold leading-4 tracking-tight whitespace-nowrap text-white shadow-sm'

export function TicketStatusText({ status, locale }: { status: string; locale: Locale }) {
  const label = labelForStatus(status, locale)
  switch (status) {
    case 'failed':
      return (
        <span className={`${TAG_BASE} bg-[#FF1744]`}>
          <AlertCircle className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'unassigned':
      return (
        <span className={`${TAG_BASE} bg-[#E64A19]`}>
          <UserX className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'processing':
    case 'received':
      return (
        <span className={`${TAG_BASE} bg-[#536DFE]`}>
          <Clock className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'in_progress':
      return (
        <span className={`${TAG_BASE} bg-[#0288D1]`}>
          <Play className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'ready':
      return (
        <span className={`${TAG_BASE} bg-[#00BFA5]`}>
          <CheckCircle2 className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'resolved':
      return (
        <span className={`${TAG_BASE} bg-[#00C853]`}>
          <Check className='size-3 shrink-0' />
          {label}
        </span>
      )
    case 'closed':
      return (
        <span className={`${TAG_BASE} bg-[#616161]`}>
          <Lock className='size-3 shrink-0' />
          {label}
        </span>
      )
    default:
      return (
        <span className={`${TAG_BASE} bg-[#616161]`}>
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
      <span className={`${TAG_BASE} bg-[#FF1744]`}>
        <AlertTriangle className='size-3 shrink-0' />
        {label}
      </span>
    )
  }
  if (bucket === 'high') {
    return (
      <span className={`${TAG_BASE} bg-[#EF6C00]`}>
        <ArrowUp className='size-3 shrink-0' />
        {label}
      </span>
    )
  }
  if (bucket === 'normal') {
    return (
      <span className={`${TAG_BASE} bg-[#2979FF]`}>        {label}
      </span>
    )
  }
  return (
    <span className={`${TAG_BASE} bg-[#616161]`}>
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
