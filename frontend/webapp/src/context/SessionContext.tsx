import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { WidgetSession } from '@/types';

interface SessionContextValue {
  session: WidgetSession | null;
  setSession: (s: WidgetSession | null) => void;
  clearSession: () => void;
}

const SessionContext = createContext<SessionContextValue>({
  session: null,
  setSession: () => {},
  clearSession: () => {},
});

function storageKey(tenant: string) {
  return `rb_session_${tenant}`;
}

export function SessionProvider({ tenant, children }: { tenant: string; children: React.ReactNode }) {
  const [session, setSessionState] = useState<WidgetSession | null>(() => {
    try {
      const raw = localStorage.getItem(storageKey(tenant));
      if (raw) return JSON.parse(raw) as WidgetSession;
    } catch {
      // ignore
    }
    return null;
  });

  const setSession = useCallback(
    (s: WidgetSession | null) => {
      setSessionState(s);
      if (s) {
        localStorage.setItem(storageKey(tenant), JSON.stringify(s));
        localStorage.setItem('rb_access_token', s.access_token);
      } else {
        localStorage.removeItem(storageKey(tenant));
        localStorage.removeItem('rb_access_token');
      }
    },
    [tenant]
  );

  const clearSession = useCallback(() => {
    setSessionState(null);
    localStorage.removeItem(storageKey(tenant));
    localStorage.removeItem('rb_access_token');
  }, [tenant]);

  useEffect(() => {
    if (session) {
      localStorage.setItem('rb_access_token', session.access_token);
    }
  }, [session]);

  const value = useMemo(() => ({ session, setSession, clearSession }), [session, setSession, clearSession]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  return useContext(SessionContext);
}
