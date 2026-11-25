import { Languages } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Button } from '@/components/ui/button'
import { Header } from '@/components/layout/header'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { QueueStreamStatus } from '@/components/svr/queue-stream-status'
import { ThemeSwitch } from '@/components/theme-switch'

export function SvrHeader() {
  const { locale, setLocale } = useSvr()

  return (
    <Header fixed>
      <Search />
      <div className='ms-auto flex items-center gap-2'>
        <QueueStreamStatus />

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
