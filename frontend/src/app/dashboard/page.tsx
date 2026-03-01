"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/lib/store";
import { useI18n } from "@/i18n/provider";
import { getDashboardStats } from "@/lib/api";
import type { DashboardStats } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Legend,
} from "recharts";

const HEATMAP_COLORS = [
  "#fde68a",
  "#fbbf24",
  "#f59e0b",
  "#d97706",
  "#b45309",
];

export default function DashboardPage() {
  const { user } = useAuthStore();
  const { t } = useI18n();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(() => {
        // API not available — will show placeholder
        setStats(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const hasData = stats && (stats.total_assignments > 0 || stats.grade_distribution.length > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">
          {t("dashboard.welcome", { name: user?.full_name ?? "" })}
        </h1>
        <p className="text-gray-600">
          {t("dashboard.role")}:{" "}
          <span className="capitalize">
            {user?.role?.replace("_", " ")}
          </span>
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title={t("dashboard.assignments")}
          value={stats?.total_assignments ?? "--"}
          loading={loading}
        />
        <StatCard
          title={t("dashboard.pendingGrading")}
          value={stats?.pending_grading ?? "--"}
          loading={loading}
          accent={stats?.pending_grading ? "yellow" : undefined}
        />
        <StatCard
          title={t("dashboard.completed")}
          value={stats?.completed ?? "--"}
          loading={loading}
          accent={stats?.completed ? "green" : undefined}
        />
        <StatCard
          title={t("dashboard.avgScore")}
          value={stats?.avg_score != null ? `${stats.avg_score.toFixed(1)}%` : "--"}
          loading={loading}
        />
      </div>

      {!loading && !hasData && (
        <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
          <p className="text-sm text-gray-500">
            {t("dashboard.noStatsYet")}
          </p>
        </div>
      )}

      {hasData && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Grade Distribution Chart */}
          {stats!.grade_distribution.length > 0 && (
            <div className="rounded-lg border bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold text-gray-700">
                {t("dashboard.gradeDistribution")}
              </h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={stats!.grade_distribution}
                  margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="range"
                    tick={{ fontSize: 11 }}
                    label={{
                      value: t("dashboard.scoreRange"),
                      position: "insideBottomRight",
                      offset: -5,
                      fontSize: 11,
                    }}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    label={{
                      value: t("dashboard.frequency"),
                      angle: -90,
                      position: "insideLeft",
                      fontSize: 11,
                    }}
                  />
                  <Tooltip />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {stats!.grade_distribution.map((_, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={
                          index < 2
                            ? "#ef4444"
                            : index < 4
                            ? "#f59e0b"
                            : index < 6
                            ? "#3b82f6"
                            : "#22c55e"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Knowledge Point Heatmap */}
          {stats!.knowledge_heatmap.length > 0 && (
            <div className="rounded-lg border bg-white p-5 shadow-sm">
              <h2 className="mb-4 text-sm font-semibold text-gray-700">
                {t("dashboard.topErrors")}
              </h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={stats!.knowledge_heatmap.slice(0, 5)}
                  layout="vertical"
                  margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    label={{
                      value: t("dashboard.errorCount"),
                      position: "insideBottomRight",
                      offset: -5,
                      fontSize: 11,
                    }}
                  />
                  <YAxis
                    type="category"
                    dataKey="topic"
                    width={140}
                    tick={{ fontSize: 10 }}
                  />
                  <Tooltip />
                  <Bar dataKey="error_count" radius={[0, 4, 4, 0]}>
                    {stats!.knowledge_heatmap.slice(0, 5).map((_, index) => (
                      <Cell
                        key={`hm-${index}`}
                        fill={HEATMAP_COLORS[index % HEATMAP_COLORS.length]}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Monthly Progress Tracking */}
          {stats!.monthly_progress.length > 0 && (
            <div className="rounded-lg border bg-white p-5 shadow-sm lg:col-span-2">
              <h2 className="mb-4 text-sm font-semibold text-gray-700">
                {t("dashboard.progressTracking")}
              </h2>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart
                  data={stats!.monthly_progress}
                  margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 11 }}
                    label={{
                      value: t("dashboard.month"),
                      position: "insideBottomRight",
                      offset: -5,
                      fontSize: 11,
                    }}
                  />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar
                    dataKey="graded"
                    name={t("dashboard.graded")}
                    fill="#22c55e"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey="pending"
                    name={t("dashboard.pending")}
                    fill="#f59e0b"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({
  title,
  value,
  loading,
  accent,
}: {
  title: string;
  value: string | number;
  loading?: boolean;
  accent?: "green" | "yellow" | "red";
}) {
  const accentClasses = {
    green: "border-l-4 border-l-green-500",
    yellow: "border-l-4 border-l-yellow-500",
    red: "border-l-4 border-l-red-500",
  };

  return (
    <div
      className={`rounded-lg border bg-white p-5 shadow-sm ${
        accent ? accentClasses[accent] : ""
      }`}
    >
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">
        {loading ? (
          <span className="inline-block h-7 w-16 animate-pulse rounded bg-gray-200" />
        ) : (
          value
        )}
      </p>
    </div>
  );
}
