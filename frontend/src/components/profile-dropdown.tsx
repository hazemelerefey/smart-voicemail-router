import { Link, useNavigate } from '@tanstack/react-router'
import { FileText, LogOut, ShieldCheck } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { UI_COPY } from '@/lib/i18n'

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('')
}

export function ProfileDropdown() {
  const { user, logout, locale } = useSvr()
  const navigate = useNavigate()
  const t = UI_COPY[locale]

  if (!user) return null

  const handleSignOut = async () => {
    await logout()
    void navigate({ to: '/login', replace: true })
  }

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <Button variant='ghost' className='relative h-8 w-8 rounded-full' aria-label={user.full_name}>
          <Avatar className='h-8 w-8'>
            <AvatarFallback className='bg-primary text-primary-foreground text-xs font-semibold'>
              {initials(user.full_name)}
            </AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className='w-56' align='end' forceMount>
        <DropdownMenuLabel className='font-normal'>
          <div className='flex flex-col gap-1.5'>
            <p className='text-sm leading-none font-medium'>{user.full_name}</p>
            <p className='text-xs leading-none text-muted-foreground'>
              {user.role.toUpperCase()} · {user.email}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem asChild>
            <Link to='/privacy'>
              <ShieldCheck className='me-2 size-4' />
              {t.privacy}
            </Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link to='/terms'>
              <FileText className='me-2 size-4' />
              {t.terms}
            </Link>
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant='destructive' onClick={() => void handleSignOut()}>
          <LogOut className='me-2 size-4' />
          {t.signOut}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
