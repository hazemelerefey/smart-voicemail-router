import { useCallback, useEffect, useState } from 'react'
import { AlertCircle, Download, RefreshCw } from 'lucide-react'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Main } from '@/components/layout/main'
import { api, apiUrl, ApiError } from '@/lib/api'
import { UI_COPY } from '@/lib/i18n'
import { formatUtcTimestamp } from '@/lib/taxonomy'
import type { AuditEventResponse } from '@/lib/types'

export function AuditLogPage() {
  const { locale } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [events, setEvents] = useState<AuditEventResponse[]>([])
  const [total, setTotal] = useState(0)
  const [actionFilter, setActionFilter] = useState('all')
  const [actorFilter, setActorFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setError(null)
    try {
      const res = await api.listAuditLogs({
        action: actionFilter === 'all' ? undefined : actionFilter,
        actor: actorFilter.trim() || undefined,
        limit: 50,
      })
      setEvents(res.items)
      setTotal(res.total)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load audit log.')
    } finally {
      setLoading(false)
    }
  }, [actionFilter, actorFilter])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>{L('Audit Log', 'سجل التدقيق')}</h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Immutable compliance trail of logins, uploads, corrections, reassignments, and configuration changes.',
              'سجل غير قابل للتعديل لكل عمليات الدخول والرفع والتصحيح وإعادة التوجيه وتغيير الإعدادات.'
            )}
          </p>
        </div>
        <div className='flex flex-wrap items-center gap-2'>
          <Button variant='outline' size='sm' asChild>
            <a href={apiUrl('/api/audit-logs/export?format=csv')} download>
              <Download className='size-4' />
              CSV
            </a>
          </Button>
          <Button variant='outline' size='sm' asChild>
            <a href={apiUrl('/api/audit-logs/export?format=json')} download>
              <Download className='size-4' />
              JSON
            </a>
          </Button>
          <Button variant='outline' size='sm' onClick={() => void load()} disabled={loading}>
            <RefreshCw className='size-4' />
            {L('Refresh', 'تحديث')}
          </Button>
        </div>
      </div>

      <Card className='mb-4'>
        <CardContent className='flex flex-wrap items-center gap-3 pt-4'>
          <Select value={actionFilter} onValueChange={setActionFilter}>
            <SelectTrigger className='w-56'>
              <SelectValue placeholder={L('Action', 'الحدث')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='all'>{t.allOption}</SelectItem>
              <SelectItem value='auth.login_success'>auth.login_success</SelectItem>
              <SelectItem value='voicemail.uploaded'>voicemail.uploaded</SelectItem>
              <SelectItem value='corrected'>corrected</SelectItem>
              <SelectItem value='reassigned'>reassigned</SelectItem>
              <SelectItem value='settings.updated'>settings.updated</SelectItem>
              <SelectItem value='agent.created'>agent.created</SelectItem>
              <SelectItem value='agent.updated'>agent.updated</SelectItem>
            </SelectContent>
          </Select>

          <Input
            value={actorFilter}
            onChange={(ev) => setActorFilter(ev.target.value)}
            placeholder={L('Filter by actor email or ID...', 'تصفية باسم الفاعل...')}
            className='max-w-xs'
          />

          <span className='ms-auto text-xs text-muted-foreground tabular-nums'>
            {total} {L('events', 'حدث')}
          </span>
        </CardContent>
      </Card>

      {error && (
        <Alert variant='destructive' className='mb-4'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      ) : (
        <div className='rounded-md border bg-card'>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{L('Timestamp', 'الوقت')}</TableHead>
                <TableHead>{L('Action', 'الحدث')}</TableHead>
                <TableHead>{L('Actor', 'الفاعل')}</TableHead>
                <TableHead>{L('Target', 'الهدف')}</TableHead>
                <TableHead>{L('Details', 'التفاصيل')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.map((ev) => (
                <TableRow key={ev.id}>
                  <TableCell className='font-mono text-xs tabular-nums'>
                    {formatUtcTimestamp(ev.created_at, locale)}
                  </TableCell>
                  <TableCell className='font-mono text-xs font-semibold'>{ev.action}</TableCell>
                  <TableCell className='text-xs'>{ev.actor}</TableCell>
                  <TableCell className='font-mono text-xs'>
                    {ev.entity_type} #{ev.entity_id.slice(0, 8)}
                  </TableCell>
                  <TableCell className='max-w-xs truncate font-mono text-xs text-muted-foreground'>
                    {ev.new_value ? JSON.stringify(ev.new_value) : '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </Main>
  )
}
