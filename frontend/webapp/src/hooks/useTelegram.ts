import { useEffect, useState } from 'react';
import type { TelegramUser, TelegramWebApp } from '@/types';

export function useTelegram() {
  const [webApp, setWebApp] = useState<TelegramWebApp | null>(null);
  const [user, setUser] = useState<TelegramUser | null>(null);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) return;
    tg.ready();
    tg.expand();
    setWebApp(tg);
    if (tg.initDataUnsafe?.user) {
      setUser(tg.initDataUnsafe.user);
    }
  }, []);

  const setMainButton = (text: string, onClick: () => void) => {
    if (!webApp) return;
    webApp.MainButton.setText(text);
    webApp.MainButton.onClick(onClick);
    webApp.MainButton.show();
    return () => {
      webApp.MainButton.offClick(onClick);
      webApp.MainButton.hide();
    };
  };

  return { webApp, user, setMainButton };
}
