import React, { useCallback, useEffect, useState } from 'react'
import { AlertCircle, Plus, RefreshCw, Save } from 'lucide-react'
import { toast } from 'sonner'
import { useSvr } from '@/context/svr-provider'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Main } from '@/components/layout/main'
import { api, ApiError } from '@/lib/api'
import { UI_COPY, labelForCategory } from '@/lib/i18n'
import type { AgentResponse, SkillMappingItem } from '@/lib/types'

const SKILL_OPTIONS = ['Network', 'Billing', 'General'] as const

export function AdminAgentsPage() {
  const { locale } = useSvr()
  const t = UI_COPY[locale]
  const isAr = locale === 'ar'
  const L = (en: string, ar: string) => (isAr ? ar : en)

  const [agents, setAgents] = useState<AgentResponse[]>([])
  const [mappings, setMappings] = useState<SkillMappingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<AgentResponse | null>(null)
  const [name, setName] = useState('')
  const [skills, setSkills] = useState<string[]>(['General'])
  const [capacity, setCapacity] = useState(5)
  const [seedOrder, setSeedOrder] = useState(4)
  const [available, setAvailable] = useState(true)

  const load = useCallback(async () => {
    setError(null)
    try {
      const [ag, mp] = await Promise.all([api.listAgents(), api.getSkillMappings()])
      setAgents(ag)
      setMappings(mp.mappings)
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Failed to load agents & skill mapping.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setName('')
    setSkills(['General'])
    setCapacity(5)
    setSeedOrder(agents.length + 1)
    setAvailable(true)
    setDialogOpen(true)
  }

  const openEdit = (a: AgentResponse) => {
    setEditing(a)
    setName(a.name)
    setSkills(a.skills)
    setCapacity(a.capacity)
    setSeedOrder(a.seed_order)
    setAvailable(a.available)
    setDialogOpen(true)
  }

  const toggleSkill = (sk: string) => {
    setSkills((prev) => (prev.includes(sk) ? prev.filter((x) => x !== sk) : [...prev, sk]))
  }

  const handleSaveAgent = async (ev: React.FormEvent) => {
    ev.preventDefault()
    if (!name.trim() || skills.length === 0) {
      toast.error(L('Name and at least one skill are required.', 'الاسم ومهارة واحدة على الأقل مطلوبان.'))
      return
    }
    setBusy(true)
    try {
      if (editing) {
        await api.updateAgent(editing.id, {
          name: name.trim(),
          skills,
          capacity,
          seed_order: seedOrder,
          available,
        })
        toast.success(L('Agent updated.', 'تم تحديث الموظف.'))
      } else {
        await api.createAgent({
          name: name.trim(),
          skills,
          capacity,
          seed_order: seedOrder,
          available,
        })
        toast.success(L('Agent created.', 'تم إضافة الموظف.'))
      }
      setDialogOpen(false)
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to save agent.')
    } finally {
      setBusy(false)
    }
  }

  const handleToggleAvailable = async (a: AgentResponse) => {
    setBusy(true)
    try {
      await api.updateAgent(a.id, { available: !a.available })
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to update availability.')
    } finally {
      setBusy(false)
    }
  }

  const handleSaveMappings = async () => {
    setBusy(true)
    try {
      await api.updateSkillMappings(Object.fromEntries(mappings.map((m) => [m.category, m.skill_name])))
      toast.success(L('11-category FR20 skill mapping saved.', 'تم حفظ ربط الـ 11 فئة بالمهارات.'))
      await load()
    } catch (err) {
      toast.error(err instanceof ApiError ? err.detail : 'Failed to save skill mappings.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Main>
      <div className='mb-4 flex flex-wrap items-center justify-between gap-3'>
        <div>
          <h1 className='text-2xl font-bold tracking-tight'>
            {L('Agents & Telecom Skill Mapping', 'الموظفون وربط المهارات')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {L(
              'Manage telecom care specialists, shift availability, capacity, and the FR20 11-category routing table.',
              'إدارة موظفي خدمة العملاء وتوافرهم وسعتهم وجدول ربط الـ 11 فئة بالمهارات (FR20).'
            )}
          </p>
        </div>
        <div className='flex items-center gap-2'>
          <Button variant='outline' onClick={() => void load()} disabled={loading}>
            <RefreshCw className='size-4' />
            {L('Refresh', 'تحديث')}
          </Button>
          <Button onClick={openCreate}>
            <Plus className='size-4' />
            {L('Add Agent', 'إضافة موظف')}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant='destructive' className='mb-4'>
          <AlertCircle className='size-4' />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <p className='py-8 text-sm text-muted-foreground'>{t.loading}</p>
      ) : (
        <div className='space-y-6'>
          <Card>
            <CardHeader>
              <CardTitle>{L('Telecom Care Roster (Seed Order)', 'قائمة الموظفين')}</CardTitle>
              <CardDescription>
                {L('First eligible active agent in seed order receives each ticket.', 'أول موظف مؤهل حسب ترتيب البذرة يستلم التذكرة.')}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Order</TableHead>
                    <TableHead>{L('Name', 'الاسم')}</TableHead>
                    <TableHead>{L('Skills', 'المهارات')}</TableHead>
                    <TableHead className='text-end'>{L('Load / Cap', 'الحمل / السعة')}</TableHead>
                    <TableHead>{L('On Shift', 'متاح')}</TableHead>
                    <TableHead className='text-end'>{L('Actions', 'إجراءات')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agents.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className='font-mono'>{a.seed_order}</TableCell>
                      <TableCell className='font-medium'>{a.name}</TableCell>
                      <TableCell>
                        <div className='flex flex-wrap gap-1'>
                          {a.skills.map((s) => (
                            <Badge key={s} variant='secondary'>{s}</Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className='text-end font-mono tabular-nums'>
                        {a.current_load} / {a.capacity}
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={a.available}
                          disabled={busy}
                          onCheckedChange={() => void handleToggleAvailable(a)}
                          aria-label={`Toggle availability for ${a.name}`}
                        />
                      </TableCell>
                      <TableCell className='text-end'>
                        <Button variant='outline' size='sm' onClick={() => openEdit(a)}>
                          {L('Edit', 'تعديل')}
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className='flex flex-row items-center justify-between'>
              <div>
                <CardTitle>{L('FR20 11-Category Skill Mapping', 'ربط الـ 11 فئة بالمهارات')}</CardTitle>
                <CardDescription>
                  {L('All 11 fixed telecom complaint categories must map to a skill.', 'يجب ربط جميع الفئات الـ 11 بمهارة.')}
                </CardDescription>
              </div>
              <Button disabled={busy} onClick={() => void handleSaveMappings()}>
                <Save className='size-4' />
                {L('Save Mapping', 'حفظ الربط')}
              </Button>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{L('Complaint Category', 'فئة الشكوى')}</TableHead>
                    <TableHead>{L('Required Skill', 'المهارة المطلوبة')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mappings.map((m) => (
                    <TableRow key={m.category}>
                      <TableCell>
                        <div className='font-medium'>{labelForCategory(m.category, locale)}</div>
                        <div className='font-mono text-xs text-muted-foreground'>{m.category}</div>
                      </TableCell>
                      <TableCell>
                        <Select
                          value={m.skill_name}
                          onValueChange={(val) =>
                            setMappings((prev) =>
                              prev.map((x) => (x.category === m.category ? { ...x, skill_name: val } : x))
                            )
                          }
                        >
                          <SelectTrigger className='w-48'><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {SKILL_OPTIONS.map((sk) => (
                              <SelectItem key={sk} value={sk}>{sk}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? L('Edit Agent', 'تعديل موظف') : L('New Agent', 'إضافة موظف')}</DialogTitle>
            <DialogDescription>
              {L('Configure telecom skills, capacity, and seed order.', 'تحديد المهارات والسعة والترتيب.')}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSaveAgent} className='space-y-4'>
            <div className='grid gap-1.5'>
              <Label htmlFor='agent-name'>{L('Agent Name', 'الاسم')}</Label>
              <Input id='agent-name' value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div className='grid gap-2'>
              <Label>{L('Skills', 'المهارات')}</Label>
              <div className='flex flex-wrap gap-4'>
                {SKILL_OPTIONS.map((sk) => (
                  <label key={sk} className='flex items-center gap-2 text-sm'>
                    <Checkbox checked={skills.includes(sk)} onCheckedChange={() => toggleSkill(sk)} />
                    {sk}
                  </label>
                ))}
              </div>
            </div>
            <div className='grid grid-cols-2 gap-3'>
              <div className='grid gap-1.5'>
                <Label htmlFor='agent-cap'>{L('Capacity', 'السعة')}</Label>
                <Input
                  id='agent-cap'
                  type='number'
                  min={1}
                  max={100}
                  value={capacity}
                  onChange={(e) => setCapacity(Number(e.target.value))}
                />
              </div>
              <div className='grid gap-1.5'>
                <Label htmlFor='agent-order'>{L('Seed Order', 'الترتيب')}</Label>
                <Input
                  id='agent-order'
                  type='number'
                  min={1}
                  value={seedOrder}
                  onChange={(e) => setSeedOrder(Number(e.target.value))}
                />
              </div>
            </div>
            <div className='flex items-center gap-2'>
              <Switch checked={available} onCheckedChange={setAvailable} id='agent-avail' />
              <Label htmlFor='agent-avail'>{L('Available on shift', 'متاح في الوردية')}</Label>
            </div>
            <DialogFooter>
              <Button type='button' variant='outline' onClick={() => setDialogOpen(false)}>
                {L('Cancel', 'إلغاء')}
              </Button>
              <Button type='submit' disabled={busy}>{L('Save', 'حفظ')}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Main>
  )
}
