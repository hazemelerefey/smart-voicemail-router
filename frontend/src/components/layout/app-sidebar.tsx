import { Link } from '@tanstack/react-router'
import { useLayout } from '@/context/layout-provider'
import { useSvr } from '@/context/svr-provider'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
} from '@/components/ui/sidebar'
import { SvrBrandMark } from '@/components/svr-brand-mark'
import { UI_COPY } from '@/lib/i18n'
import { NavGroup } from './nav-group'
import { NavUser } from './nav-user'
import { buildSvrNavGroups } from './svr-nav'

export function AppSidebar() {
  const { collapsible, variant } = useLayout()
  const { user, locale, reviewBadgeCount } = useSvr()
  const t = UI_COPY[locale]

  if (!user) return null

  const navGroups = buildSvrNavGroups(user.role, locale, reviewBadgeCount)
  const homePath = user.role === 'agent' ? '/my-tickets' : '/overview'

  return (
    <Sidebar collapsible={collapsible} variant={variant}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size='lg' asChild>
              <Link to={homePath}>
                <div className='flex aspect-square size-8 items-center justify-center rounded-lg'>
                  <SvrBrandMark className='size-7' />
                </div>
                <div className='grid flex-1 text-start text-sm leading-tight'>
                  <span className='truncate font-bold'>{t.appName}</span>
                  <span className='truncate text-xs text-muted-foreground'>{t.orgName}</span>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {navGroups.map((props) => (
          <NavGroup key={props.title} {...props} />
        ))}
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
