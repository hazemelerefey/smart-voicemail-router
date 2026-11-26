import React, { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { ArrowRight, Languages, Laptop, LifeBuoy, Moon, Sun, Ticket, User } from 'lucide-react'
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
import { api } from '@/lib/api'
import { labelForCategory } from '@/lib/i18n'
import type { TicketSummary } from '@/lib/types'
import { buildSvrNavGroups } from './layout/svr-nav'
import { ScrollArea } from './ui/scroll-area'

export function CommandMenu() {
  const navigate = useNavigate()
  const { setTheme } = useTheme()
  const { open, setOpen } = useSearch()
  const { user, locale, setLocale, reviewBadgeCount } = useSvr()
  const isAr = locale === 'ar'

  const [query, setQuery] = useState('')
  const [ticketHits, setTicketHits] = useState<TicketSummary[]>([])

  useEffect(() => {
    if (!open) {
      setQuery('')
      setTicketHits([])
      return
    }
  }, [open])

  useEffect(() => {
    const trimmed = query.trim()
    if (!open || !user || trimmed.length < 2) {
      setTicketHits([])
      return
    }
    let cancelled = false
    const timer = window.setTimeout(() => {
      api
        .listTickets({ q: trimmed, limit: 5 })
        .then((res) => {
          if (!cancelled) setTicketHits(res.items)
        })
        .catch(() => {
          if (!cancelled) setTicketHits([])
        })
    }, 220)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [query, open, user])

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
      <CommandInput
        value={query}
        onValueChange={setQuery}
        placeholder={isAr ? 'ابحث في التذاكر أو اختر صفحة...' : 'Search tickets or type a command...'}
      />
      <CommandList>
        <ScrollArea type='hover' className='h-80 pe-1'>
          <CommandEmpty>{isAr ? 'لا توجد نتائج.' : 'No results found.'}</CommandEmpty>

          {ticketHits.length > 0 && (
            <>
              <CommandGroup heading={isAr ? 'التذاكر' : 'Tickets'}>
                {ticketHits.map((tk) => (
                  <CommandItem
                    key={tk.id}
                    value={`ticket ${tk.id} ${tk.summary ?? ''} ${tk.customer_request ?? ''}`}
                    onSelect={() =>
                      runCommand(() => navigate({ to: '/tickets/$id', params: { id: tk.id } }))
                    }
                  >
                    <Ticket className='size-4 text-primary' />
                    <span className='font-mono text-xs text-muted-foreground'>
                      #{tk.id.slice(0, 8)}
                    </span>
                    <span className='font-medium'>
                      {labelForCategory(tk.complaint_category, locale)}
                    </span>
                    <span className='truncate text-xs text-muted-foreground' dir='auto'>
                      {tk.summary || tk.customer_request || ''}
                    </span>
                  </CommandItem>
                ))}
              </CommandGroup>
              <CommandSeparator />
            </>
          )}

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
          <CommandGroup heading={isAr ? 'الحساب والدعم' : 'Account & Support'}>
            <CommandItem onSelect={() => runCommand(() => navigate({ to: '/account' }))}>
              <User /> <span>{isAr ? 'الحساب والملف الشخصي' : 'Account & Profile'}</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => navigate({ to: '/support' }))}>
              <LifeBuoy /> <span>{isAr ? 'الدعم ودليل التشغيل' : 'Support & Guide'}</span>
            </CommandItem>
          </CommandGroup>

          <CommandSeparator />
          <CommandGroup heading={isAr ? 'اللغة' : 'Language'}>
            <CommandItem onSelect={() => runCommand(() => setLocale('en'))}>
              <Languages /> <span>English (LTR)</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setLocale('ar'))}>
              <Languages /> <span>العربية (RTL)</span>
            </CommandItem>
          </CommandGroup>

          <CommandSeparator />
          <CommandGroup heading={isAr ? 'المظهر' : 'Theme'}>
            <CommandItem onSelect={() => runCommand(() => setTheme('light'))}>
              <Sun /> <span>{isAr ? 'فاتح (رئيسي)' : 'Light'}</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('dark'))}>
              <Moon className='scale-90' />
              <span>{isAr ? 'داكن (OLED)' : 'Dark'}</span>
            </CommandItem>
            <CommandItem onSelect={() => runCommand(() => setTheme('system'))}>
              <Laptop />
              <span>{isAr ? 'النظام' : 'System'}</span>
            </CommandItem>
          </CommandGroup>
        </ScrollArea>
      </CommandList>
    </CommandDialog>
  )
}
