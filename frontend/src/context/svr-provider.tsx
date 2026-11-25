import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useDirection } from '@/context/direction-provider'
import { api, queueWsUrl } from '@/lib/api'
import type { Locale } from '@/lib/i18n'
import type { QueueWsEvent, SettingsResponse, UserResponse } from '@/lib/types'

export type WsStatus = 'connecting' | 'connected' | 'reconnecting' | 'offline'

export interface WsFeedItem {
  id: string
  receivedAt: string
  event: QueueWsEvent
}

interface SvrContextValue {
  user: UserResponse | null
  authLoading: boolean
  refreshAuth: () => Promise<UserResponse | null>
  login: (email: string, password: string) => Promise<UserResponse | null>
  logout: () => Promise<void>
  locale: Locale
  setLocale: (loc: Locale) => void
  settings: SettingsResponse | null
  refreshSettings: () => Promise<void>
  wsStatus: WsStatus
  wsVersion: number
  lastWsEvent: QueueWsEvent | null
  wsConnectedAt: string | null
  lastWsEventAt: string | null
  wsFeed: WsFeedItem[]
  wsUnreadCount: number
  markWsFeedRead: () => void
  clearWsFeed: () => void
  reconnectWs: () => void
  reviewBadgeCount: number | undefined
  refreshReviewBadge: () => Promise<void>
}

const SvrContext = createContext<SvrContextValue | null>(null)

export function SvrProvider({ children }: { children: React.ReactNode }) {
  const { setDir } = useDirection()
  const [user, setUser] = useState<UserResponse | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [locale, setLocaleState] = useState<Locale>('en')
  const [settings, setSettings] = useState<SettingsResponse | null>(null)
  const [wsStatus, setWsStatus] = useState<WsStatus>('offline')
  const [wsVersion, setWsVersion] = useState(0)
  const [lastWsEvent, setLastWsEvent] = useState<QueueWsEvent | null>(null)
  const [wsConnectedAt, setWsConnectedAt] = useState<string | null>(null)
  const [lastWsEventAt, setLastWsEventAt] = useState<string | null>(null)
  const [wsFeed, setWsFeed] = useState<WsFeedItem[]>([])
  const [wsUnreadCount, setWsUnreadCount] = useState(0)
  const [wsReconnectSeq, setWsReconnectSeq] = useState(0)
  const [reviewBadgeCount, setReviewBadgeCount] = useState<number | undefined>(undefined)

  const markWsFeedRead = useCallback(() => {
    setWsUnreadCount(0)
  }, [])

  const clearWsFeed = useCallback(() => {
    setWsFeed([])
    setWsUnreadCount(0)
  }, [])

  const reconnectWs = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setWsReconnectSeq((n) => n + 1)
  }, [])

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)

  const setLocale = useCallback(
    (loc: Locale) => {
      setLocaleState(loc)
      setDir(loc === 'ar' ? 'rtl' : 'ltr')
      document.documentElement.lang = loc
      document.documentElement.dir = loc === 'ar' ? 'rtl' : 'ltr'
    },
    [setDir]
  )

  const refreshSettings = useCallback(async () => {
    try {
      const s = await api.getSettings()
      setSettings(s)
    } catch {
      // Unauthenticated or non-admin/supervisor fallback handled by auth state
    }
  }, [])

  const refreshReviewBadge = useCallback(async () => {
    try {
      const res = await api.listTickets({ limit: 1 })
      setReviewBadgeCount(res.human_review_count)
    } catch {
      // Ignore for agent role or unauthenticated state
    }
  }, [])

  const refreshAuth = useCallback(async (): Promise<UserResponse | null> => {
    try {
      const me = await api.me()
      setUser(me)
      const [s] = await Promise.all([
        api.getSettings().catch(() => null),
        me.role === 'admin' || me.role === 'supervisor'
          ? api
              .listTickets({ limit: 1 })
              .then((r) => setReviewBadgeCount(r.human_review_count))
              .catch(() => null)
          : Promise.resolve(null),
      ])
      if (s) setSettings(s)
      return me
    } catch {
      setUser(null)
      setSettings(null)
      setReviewBadgeCount(undefined)
      return null
    } finally {
      setAuthLoading(false)
    }
  }, [])

  const login = useCallback(
    async (email: string, password: string): Promise<UserResponse | null> => {
      await api.login(email, password)
      return refreshAuth()
    },
    [refreshAuth]
  )

  const logout = useCallback(async () => {
    try {
      await api.logout()
    } catch {
      // Always clear client session state
    } finally {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      setUser(null)
      setSettings(null)
      setReviewBadgeCount(undefined)
      setWsStatus('offline')
      setWsConnectedAt(null)
      setLastWsEventAt(null)
      setWsFeed([])
      setWsUnreadCount(0)
    }
  }, [])

  useEffect(() => {
    void refreshAuth()
  }, [refreshAuth])

  useEffect(() => {
    if (!user) {
      setWsStatus('offline')
      return
    }
    let cancelled = false
    let attempt = 0

    const connect = () => {
      if (cancelled) return
      setWsStatus(attempt === 0 ? 'connecting' : 'reconnecting')
      let socket: WebSocket
      try {
        socket = new WebSocket(queueWsUrl())
      } catch {
        setWsStatus('offline')
        return
      }
      wsRef.current = socket

      socket.onopen = () => {
        if (cancelled) return
        attempt = 0
        setWsConnectedAt(new Date().toISOString())
        setWsStatus('connected')
      }

      socket.onmessage = (ev) => {
        if (cancelled) return
        const nowIso = new Date().toISOString()
        setLastWsEventAt(nowIso)
        try {
          const parsed = JSON.parse(String(ev.data)) as QueueWsEvent
          setLastWsEvent(parsed)
          setWsVersion((v) => v + 1)
          if (parsed.type !== 'queue_snapshot') {
            setWsFeed((prev) => [
              {
                id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
                receivedAt: nowIso,
                event: parsed,
              },
              ...prev.slice(0, 11),
            ])
            setWsUnreadCount((n) => n + 1)
          }
          if (parsed.type === 'settings_updated' || parsed.type === 'settings.updated') {
            void refreshSettings()
          }
          if (user.role === 'admin' || user.role === 'supervisor') {
            void refreshReviewBadge()
          }
        } catch {
          setWsVersion((v) => v + 1)
        }
      }

      socket.onclose = () => {
        if (cancelled) return
        wsRef.current = null
        attempt += 1
        setWsConnectedAt(null)
        setWsStatus('reconnecting')
        const delayMs = Math.min(15000, 1500 * attempt)
        reconnectTimerRef.current = window.setTimeout(connect, delayMs)
      }

      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [user, wsReconnectSeq, refreshSettings, refreshReviewBadge])

  return (
    <SvrContext.Provider
      value={{
        user,
        authLoading,
        refreshAuth,
        login,
        logout,
        locale,
        setLocale,
        settings,
        refreshSettings,
        wsStatus,
        wsVersion,
        lastWsEvent,
        wsConnectedAt,
        lastWsEventAt,
        wsFeed,
        wsUnreadCount,
        markWsFeedRead,
        clearWsFeed,
        reconnectWs,
        reviewBadgeCount,
        refreshReviewBadge,
      }}
    >
      {children}
    </SvrContext.Provider>
  )
}

export function useSvr(): SvrContextValue {
  const ctx = useContext(SvrContext)
  if (!ctx) throw new Error('useSvr must be used inside SvrProvider')
  return ctx
}
