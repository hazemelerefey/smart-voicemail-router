import React from 'react'
import { useNavigate } from '@tanstack/react-router'
import { ArrowRight, Languages, Laptop, Moon, Sun } from 'lucide-react'
import { useSearch } from '@/context/search-provider'
import { useSvr } from '@/context/svr-provider'
import { useTheme } from '@/context/theme-provider'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { buildSvrNavGroups } from './layout/svr-nav'
import { ScrollArea } from './ui/scroll-area'

export function CommandMenu() {
  const navigate = useNavigate()
  const { setTheme } = useTheme()
  const { open, setOpen } = useSearch()
  const { user, locale, setLocale, reviewBadgeCount } = useSvr()

  const runCommand = React.useCallback(
    (command: () => unknown) => {
      setOpen(false)
      command()
    },
    [setOpen]
  )

  const navGroups = user ? buildSvrNavGroups(user.role, locale, reviewBadgeCount) : []

  return (
    <CommandDialog modal open={open} onOpenChange={setOpen}>
      <CommandInput placeholder={locale === 'ar' ? 'ابحث أو اختر صفحة...' : 'Type a command or search...'} />
      <CommandList>
        <ScrollArea type='hover' className='h-72 pe-1'>
          <CommandEmpty>No results found.</CommandEmpty>
          {navGroups.map((group) => (
            <CommandGroup key={group.title} heading={group.title}>
              {group.items.map((navItem, i) =>
                navItem.url ? (
                  <CommandItem
                    key={`${navItem.url}-${i}`}
                    value={navItem.title}
                    onSelect={() => runCommand(() => navigate({ to: navItem.url as string }))}
                  >
                    <div className='flex size-4 items-center justify-center'>
                      <ArrowRight className='size-3 text-muted-foreground/80' />
                    </div>
                    {navItem.title}
                  </CommandItem>
                ) : null
              )}
            </CommandGroup>
          ))}
          <CommandSeparator />
          <CommandGroup heading={locale === 'ar' ? 'اللغة' : 'Language'}>
            <CommandItem onSelect={() => runCommand(() => setLocale('en'))}>
              <Languages /> <span>English (LTR)</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setLocale('ar'))}>
              <Languages /> <span>العربية (RTL)</span>
            </CommandItem>
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading='Theme'>
            <CommandItem onSelect={() => runCommand(() => setTheme('light'))}>
              <Sun /> <span>Light</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('dark'))}>
              <Moon className='scale-90' />
              <span>Dark</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('system'))}>
              <Laptop />
              <span>System</span>
            </CommandItem>
          </CommandGroup>
        </ScrollArea>
      </CommandList>
    </CommandDialog>
  )
}
