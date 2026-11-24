"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api, ApiError, queueWsUrl, readCookie } from "@/lib/api";
import type { Locale } from "@/lib/i18n";
import type { QueueWsEvent, SettingsResponse, UserResponse } from "@/lib/types";

export type Theme = "light" | "dark";
export type WsStatus = "connected" | "reconnecting" | "offline";

interface AppContextValue {
  user: UserResponse | null;
  authLoading: boolean;
  refreshAuth: () => Promise<UserResponse | null>;
  logout: () => Promise<void>;
  locale: Locale;
  setLocale: (next: Locale) => void;
  theme: Theme;
  setTheme: (next: Theme) => void;
  settings: SettingsResponse | null;
  refreshSettings: () => Promise<void>;
  wsStatus: WsStatus;
  lastWsEvent: QueueWsEvent | null;
  wsVersion: number;
}

const AppContext = createContext<AppContextValue | null>(null);

function writeUiCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=31536000; SameSite=Lax`;
}

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [locale, setLocaleState] = useState<Locale>("en");
  const [theme, setThemeState] = useState<Theme>("light");
  const [settings, setSettings] = useState<SettingsResponse | null>(null);
  const [wsStatus, setWsStatus] = useState<WsStatus>("offline");
  const [lastWsEvent, setLastWsEvent] = useState<QueueWsEvent | null>(null);
  const [wsVersion, setWsVersion] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Restore non-secret UI theme & locale from cookie
  useEffect(() => {
    const savedTheme = readCookie("svr_ui_theme");
    if (savedTheme === "dark" || savedTheme === "light") {
      setThemeState(savedTheme);
    }
    const savedLocale = readCookie("svr_ui_locale");
    if (savedLocale === "ar" || savedLocale === "en") {
      setLocaleState(savedLocale);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    writeUiCookie("svr_ui_theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute("lang", locale);
    document.documentElement.setAttribute("dir", locale === "ar" ? "rtl" : "ltr");
    writeUiCookie("svr_ui_locale", locale);
  }, [locale]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
  }, []);

  const refreshSettings = useCallback(async () => {
    try {
      const s = await api.getSettings();
      setSettings(s);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setSettings(null);
        return;
      }
      console.warn("Unable to refresh system settings:", err);
    }
  }, []);

  const refreshAuth = useCallback(async (): Promise<UserResponse | null> => {
    setAuthLoading(true);
    try {
      const me = await api.me();
      setUser(me);
      if (me.role === "admin" || me.role === "supervisor") {
        try {
          const s = await api.getSettings();
          setSettings(s);
        } catch (settingsErr) {
          console.warn("Could not load settings after auth:", settingsErr);
        }
      } else {
        setSettings(null);
      }
      return me;
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        console.warn("Session verification failed:", err);
      }
      setUser(null);
      setSettings(null);
      return null;
    } finally {
      setAuthLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshAuth();
  }, [refreshAuth]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch (err) {
      console.warn("Logout request error:", err);
    } finally {
      setUser(null);
      setSettings(null);
      setWsStatus("offline");
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    }
  }, []);

  // Authenticated real-time WebSocket subscription (/ws/queue)
  useEffect(() => {
    if (!user) {
      setWsStatus("offline");
      return;
    }

    let disposed = false;

    const connect = () => {
      if (disposed) return;
      try {
        const socket = new WebSocket(queueWsUrl());
        wsRef.current = socket;

        socket.onopen = () => {
          if (!disposed) setWsStatus("connected");
        };

        socket.onmessage = (msg) => {
          if (disposed) return;
          try {
            const payload = JSON.parse(msg.data) as QueueWsEvent;
            setLastWsEvent(payload);
            setWsVersion((v) => v + 1);
            if (payload.type === "settings_updated" && typeof payload.auto_routing_enabled === "boolean") {
              setSettings((prev) =>
                prev
                  ? { ...prev, auto_routing_enabled: payload.auto_routing_enabled as boolean }
                  : prev
              );
            }
          } catch (parseErr) {
            console.warn("Malformed WebSocket message:", parseErr);
          }
        };

        socket.onerror = () => {
          if (!disposed) setWsStatus("reconnecting");
        };

        socket.onclose = () => {
          if (disposed) return;
          setWsStatus("reconnecting");
          reconnectTimerRef.current = setTimeout(connect, 3500);
        };
      } catch (err) {
        console.warn("WebSocket initialization error:", err);
        setWsStatus("offline");
      }
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [user]);

  const value = useMemo<AppContextValue>(
    () => ({
      user,
      authLoading,
      refreshAuth,
      logout,
      locale,
      setLocale,
      theme,
      setTheme,
      settings,
      refreshSettings,
      wsStatus,
      lastWsEvent,
      wsVersion,
    }),
    [
      user,
      authLoading,
      refreshAuth,
      logout,
      locale,
      setLocale,
      theme,
      setTheme,
      settings,
      refreshSettings,
      wsStatus,
      lastWsEvent,
      wsVersion,
    ]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) {
    throw new Error("useApp must be used inside AppProvider");
  }
  return ctx;
}
