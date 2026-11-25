import { cn } from '@/lib/utils'

interface PriorityScoreAvatarProps {
  score: number | null | undefined
  bucket: string | null | undefined
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const SIZE_CLASSES: Record<'sm' | 'md' | 'lg', string> = {
  sm: 'size-9 rounded-md',
  md: 'size-10 rounded-md',
  lg: 'size-12 rounded-lg',
}

interface PaletteSpec {
  container: string
  motif: string
  activeBar: string
  inactiveBar: string
  numeral: string
}

function getPalette(bucket: string | null | undefined): PaletteSpec {
  switch (bucket) {
    case 'urgent':
      return {
        container:
          'border-[#f87171]/40 bg-gradient-to-b from-[#dc2626] to-[#991b1b] text-white',
        motif: 'stroke-white/20',
        activeBar: 'fill-white',
        inactiveBar: 'fill-white/25',
        numeral: 'fill-white',
      }
    case 'high':
      return {
        container:
          'border-amber-500/45 bg-gradient-to-b from-amber-50 to-amber-100/90 text-amber-950 dark:border-amber-500/40 dark:from-[#451a03] dark:to-[#78350f] dark:text-amber-200',
        motif: 'stroke-amber-700/20 dark:stroke-amber-300/20',
        activeBar: 'fill-amber-600 dark:fill-amber-400',
        inactiveBar: 'fill-amber-900/15 dark:fill-amber-200/20',
        numeral: 'fill-amber-950 dark:fill-amber-200',
      }
    case 'normal':
      return {
        container:
          'border-blue-500/35 bg-gradient-to-b from-blue-50 to-blue-100/90 text-blue-950 dark:border-sky-400/35 dark:from-[#0c1e38] dark:to-[#172554] dark:text-sky-200',
        motif: 'stroke-blue-700/15 dark:stroke-sky-300/20',
        activeBar: 'fill-blue-600 dark:fill-sky-400',
        inactiveBar: 'fill-blue-900/15 dark:fill-sky-200/20',
        numeral: 'fill-blue-950 dark:fill-sky-100',
      }
    case 'low':
      return {
        container:
          'border-zinc-400/40 bg-gradient-to-b from-zinc-100 to-zinc-200/80 text-zinc-800 dark:border-zinc-600/45 dark:from-[#1f1f24] dark:to-[#121215] dark:text-zinc-200',
        motif: 'stroke-zinc-600/15 dark:stroke-zinc-400/15',
        activeBar: 'fill-zinc-700 dark:fill-zinc-300',
        inactiveBar: 'fill-zinc-900/15 dark:fill-zinc-500/25',
        numeral: 'fill-zinc-800 dark:fill-zinc-200',
      }
    default:
      return {
        container:
          'border-dashed border-border bg-muted/60 text-muted-foreground',
        motif: 'stroke-foreground/10',
        activeBar: 'fill-muted-foreground/50',
        inactiveBar: 'fill-foreground/10',
        numeral: 'fill-muted-foreground',
      }
  }
}

/**
 * Custom vector illustration tile for priority scores (1..6 or unscored),
 * combining geometric diagonal hatch motif, 6-segment intensity meter, and crisp numeral.
 */
export function PriorityScoreAvatar({
  score,
  bucket,
  size = 'sm',
  className,
}: PriorityScoreAvatarProps) {
  const pal = getPalette(bucket)
  const clamped =
    typeof score === 'number' && Number.isFinite(score)
      ? Math.max(0, Math.min(6, Math.round(score)))
      : 0
  const labelText = score !== null && score !== undefined ? String(score) : '-'

  return (
    <div
      className={cn(
        'relative flex shrink-0 items-center justify-center overflow-hidden border select-none',
        SIZE_CLASSES[size],
        pal.container,
        className
      )}
      role='img'
      aria-label={`Priority score ${labelText}${bucket ? ` (${bucket})` : ''}`}
      title={`Priority ${labelText}${bucket ? ` - ${bucket}` : ''}`}
    >
      <svg viewBox='0 0 44 44' className='size-full' aria-hidden='true'>
        {/* Precision corner geometric hatch motif */}
        <g className={pal.motif} strokeWidth='1.1' strokeLinecap='round'>
          <path d='M-2 12 L12 -2 M-2 20 L20 -2 M24 46 L46 24 M32 46 L46 32' />
        </g>

        {/* Top acoustic bracket accent for urgent/high */}
        {(bucket === 'urgent' || bucket === 'high') && (
          <path
            d='M14 7.5 L22 4.5 L30 7.5'
            fill='none'
            className={pal.motif}
            strokeWidth='1.6'
            strokeLinecap='round'
            strokeLinejoin='round'
          />
        )}

        {/* Sculpted vector numeral */}
        <text
          x='22'
          y='25.5'
          textAnchor='middle'
          fontFamily='Inter, system-ui, -apple-system, sans-serif'
          fontSize='19'
          fontWeight='800'
          className={pal.numeral}
        >
          {labelText}
        </text>

        {/* 6-segment priority intensity meter along bottom */}
        <g transform='translate(6, 35)'>
          {[0, 1, 2, 3, 4, 5].map((idx) => (
            <rect
              key={idx}
              x={idx * 5.5}
              y='0'
              width='4'
              height='3'
              rx='1'
              className={idx < clamped ? pal.activeBar : pal.inactiveBar}
            />
          ))}
        </g>
      </svg>
    </div>
  )
}
