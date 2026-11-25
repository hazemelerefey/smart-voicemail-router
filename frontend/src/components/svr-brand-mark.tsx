import { cn } from '@/lib/utils'

/* Official SVR System App Icon mark */
export function SvrBrandMark({ className = 'size-7' }: { className?: string }) {
  return (
    <img
      src='/brand/svr-app-icon-primary.png'
      alt='SVR System'
      draggable={false}
      className={cn('select-none object-contain', className)}
    />
  )
}
