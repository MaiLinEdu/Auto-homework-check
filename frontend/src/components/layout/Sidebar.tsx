"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { useI18n } from "@/i18n/provider";
import { cn } from "@/lib/utils";

const teacherNav = [
  { labelKey: "sidebar.dashboard", href: "/dashboard" },
  { labelKey: "sidebar.assignments", href: "/assignments" },
  { labelKey: "sidebar.grading", href: "/grading" },
];

const studentNav = [
  { labelKey: "sidebar.dashboard", href: "/dashboard" },
  { labelKey: "sidebar.mySubmissions", href: "/submissions" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const { t } = useI18n();

  const navItems =
    user?.role === "student" ? studentNav : teacherNav;

  return (
    <aside className="flex h-screen w-60 flex-col border-r border-gray-200 bg-white">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-lg font-bold text-primary-700">
          {t("common.appName")}
        </span>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "block rounded-md px-3 py-2 text-sm font-medium",
              pathname.startsWith(item.href)
                ? "bg-primary-50 text-primary-700"
                : "text-gray-700 hover:bg-gray-100"
            )}
          >
            {t(item.labelKey)}
          </Link>
        ))}
      </nav>

      <div className="border-t p-3">
        <p className="truncate text-sm font-medium text-gray-800">
          {user?.full_name}
        </p>
        <p className="truncate text-xs text-gray-500">{user?.email}</p>
        <button
          onClick={logout}
          className="mt-2 w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100"
        >
          {t("common.signOut")}
        </button>
      </div>
    </aside>
  );
}
