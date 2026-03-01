"use client";

import { createContext, useContext, useState, useCallback, useEffect } from "react";
import type { Locale } from "./config";
import { defaultLocale, locales } from "./config";

type Messages = Record<string, Record<string, string>>;

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string>) => string;
  messages: Messages;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const messageCache: Partial<Record<Locale, Messages>> = {};

async function loadMessages(locale: Locale): Promise<Messages> {
  if (messageCache[locale]) return messageCache[locale]!;
  const mod = await import(`../../messages/${locale}.json`);
  messageCache[locale] = mod.default;
  return mod.default;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("gradeai-locale");
      if (saved && locales.includes(saved as Locale)) return saved as Locale;
    }
    return defaultLocale;
  });
  const [messages, setMessages] = useState<Messages>({});

  useEffect(() => {
    loadMessages(locale).then(setMessages);
  }, [locale]);

  const setLocale = useCallback((newLocale: Locale) => {
    setLocaleState(newLocale);
    localStorage.setItem("gradeai-locale", newLocale);
    document.documentElement.lang = newLocale;
  }, []);

  const t = useCallback(
    (key: string, params?: Record<string, string>): string => {
      const parts = key.split(".");
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let value: any = messages;
      for (const part of parts) {
        value = value?.[part];
      }
      if (typeof value !== "string") return key;
      if (params) {
        return value.replace(/\{(\w+)\}/g, (_, k) => params[k] ?? `{${k}}`);
      }
      return value;
    },
    [messages]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, messages }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within I18nProvider");
  return ctx;
}
