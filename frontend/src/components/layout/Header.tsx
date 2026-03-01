"use client";

import { useI18n } from "@/i18n/provider";
import LanguageToggle from "./LanguageToggle";

export default function Header() {
  const { t } = useI18n();

  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
      <div />
      <div className="flex items-center gap-4">
        <span className="text-xs text-gray-500">{t("common.language")}</span>
        <LanguageToggle />
      </div>
    </header>
  );
}
