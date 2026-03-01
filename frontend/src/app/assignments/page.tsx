"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getAssignments } from "@/lib/api";
import { useI18n } from "@/i18n/provider";
import type { Assignment } from "@/types";

export default function AssignmentsPage() {
  const { t } = useI18n();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAssignments()
      .then(setAssignments)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          {t("assignments.title")}
        </h1>
        <Link
          href="/assignments/new"
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
        >
          {t("assignments.newAssignment")}
        </Link>
      </div>

      {loading ? (
        <p className="text-gray-500">{t("common.loading")}</p>
      ) : assignments.length === 0 ? (
        <p className="text-gray-500">{t("assignments.noAssignments")}</p>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("assignments.title")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("assignments.status")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("assignments.dueDate")}
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {assignments.map((a) => (
                <tr key={a.id}>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {a.title}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium capitalize text-gray-700">
                      {a.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {a.due_date
                      ? new Date(a.due_date).toLocaleDateString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-sm">
                    <Link
                      href={`/assignments/${a.id}`}
                      className="text-primary-600 hover:underline"
                    >
                      {t("assignments.view")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
