import { cn } from '@/lib/utils'
import { useTheme } from '@/context/theme-provider'

/* Official SVR System App Icon mark (Light primary, Black OLED Glass secondary) */
export function SvrBrandMark({ className = 'size-7' }: { className?: string }) {
  const { resolvedTheme } = useTheme()

  return (
    <img
      src={resolvedTheme === 'dark' ? '/icon.svg' : '/images/favicon_light.svg'}
      alt='SVR System'
      draggable={false}
      className={cn('select-none object-contain', className)}
    />
  )
}
