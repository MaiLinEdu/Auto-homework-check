"use client";

import { useI18n } from "@/i18n/provider";
import { locales, localeNames } from "@/i18n/config";
import type { Locale } from "@/i18n/config";

export default function LanguageToggle() {
  const { locale, setLocale } = useI18n();

  return (
    <div className="flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 p-0.5">
      {locales.map((loc) => (
        <button
          key={loc}
          onClick={() => setLocale(loc as Locale)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
            locale === loc
              ? "bg-primary-600 text-white shadow-sm"
              : "text-gray-600 hover:text-gray-900"
          }`}
        >
          {localeNames[loc]}
        </button>
      ))}
    </div>
  );
}
