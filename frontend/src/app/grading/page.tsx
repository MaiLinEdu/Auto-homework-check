"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useI18n } from "@/i18n/provider";
import api from "@/lib/api";

interface GradingItem {
  id: string;
  submission_id: string;
  student_name: string;
  assignment_title: string;
  submitted_at: string;
  status: string;
  total_score: number | null;
  total_possible: number | null;
}

export default function GradingPage() {
  const { t } = useI18n();
  const [items, setItems] = useState<GradingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api
      .get("/grading/queue")
      .then((res) => setItems(res.data))
      .catch(() => {
        // API may not exist yet — show empty state
        setItems([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const statusColor: Record<string, string> = {
    graded: "bg-green-100 text-green-700",
    ai_graded: "bg-blue-100 text-blue-700",
    teacher_reviewed: "bg-emerald-100 text-emerald-700",
    pending: "bg-yellow-100 text-yellow-700",
    grading: "bg-indigo-100 text-indigo-700",
  };

  const statusLabel: Record<string, string> = {
    ai_graded: t("grading.aiGraded"),
    teacher_reviewed: t("grading.reviewed"),
    graded: t("grading.aiGraded"),
    pending: t("grading.pendingReview"),
    grading: t("grading.grade"),
  };

  const filtered = items.filter((item) => {
    const matchesStatus =
      statusFilter === "all" || item.status === statusFilter;
    const matchesSearch =
      !search ||
      item.student_name?.toLowerCase().includes(search.toLowerCase()) ||
      item.assignment_title?.toLowerCase().includes(search.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{t("grading.title")}</h1>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input
          type="text"
          placeholder={t("grading.searchPlaceholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500 sm:w-72"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
        >
          <option value="all">{t("grading.allStatuses")}</option>
          <option value="ai_graded">{t("grading.aiGraded")}</option>
          <option value="teacher_reviewed">{t("grading.reviewed")}</option>
          <option value="pending">{t("grading.pendingReview")}</option>
        </select>
      </div>

      {loading ? (
        <p className="text-gray-500">{t("common.loading")}</p>
      ) : filtered.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p className="mt-4 text-sm text-gray-500">{t("grading.noItems")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("grading.student")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("grading.assignment")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("grading.submittedAt")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("grading.status")}
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  {t("grading.score")}
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {filtered.map((item) => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {item.student_name}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {item.assignment_title}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {new Date(item.submitted_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
                        statusColor[item.status] ?? "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {statusLabel[item.status] ?? item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-gray-900">
                    {item.total_score != null
                      ? `${item.total_score}/${item.total_possible ?? "?"}`
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-right text-sm">
                    <Link
                      href={`/grading/${item.submission_id ?? item.id}`}
                      className="rounded-md bg-primary-50 px-3 py-1 text-primary-700 hover:bg-primary-100"
                    >
                      {t("grading.review")}
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
