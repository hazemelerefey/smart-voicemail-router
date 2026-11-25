import { Languages, Plug, PlugZap, RefreshCw } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Button } from '@/components/ui/button'
import { Header } from '@/components/layout/header'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
import { UI_COPY } from '@/lib/i18n'

export function SvrHeader() {
  const { locale, setLocale, wsStatus } = useSvr()
  const t = UI_COPY[locale]

  return (
    <Header fixed>
      <Search />
      <div className='ms-auto flex items-center gap-2'>
        <span
          className='hidden items-center gap-1.5 text-xs font-medium md:inline-flex'
          title={
            wsStatus === 'connected'
              ? t.wsConnected
              : wsStatus === 'reconnecting'
                ? t.wsReconnecting
                : t.wsOffline
          }
        >
          {wsStatus === 'connected' ? (
            <>
              <PlugZap className='size-3.5 text-blue-600 dark:text-sky-400' />
              <span className='text-blue-600 dark:text-sky-400'>{t.wsConnected}</span>
            </>
          ) : wsStatus === 'reconnecting' ? (
            <>
              <RefreshCw className='size-3.5 text-amber-600 dark:text-amber-400' />
              <span className='text-amber-700 dark:text-amber-400'>{t.wsReconnecting}</span>
            </>
          ) : (
            <>
              <Plug className='size-3.5 text-muted-foreground' />
              <span className='text-muted-foreground'>{t.wsOffline}</span>
            </>
          )}
        </span>

        <Button
          variant='ghost'
          size='sm'
          onClick={() => setLocale(locale === 'en' ? 'ar' : 'en')}
          aria-label={locale === 'en' ? 'Switch to Arabic' : 'Switch to English'}
        >
          <Languages className='size-4' />
          <span className='hidden sm:inline'>{locale === 'en' ? 'العربية' : 'EN'}</span>
        </Button>

        <ThemeSwitch />
        <ProfileDropdown />
      </div>
    </Header>
  )
}
