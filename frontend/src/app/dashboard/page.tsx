"use client";

import { useAuthStore } from "@/lib/store";

export default function DashboardPage() {
  const { user } = useAuthStore();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">
        Welcome, {user?.full_name}
      </h1>
      <p className="text-gray-600">
        Role: <span className="capitalize">{user?.role?.replace("_", " ")}</span>
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard title="Assignments" value="--" />
        <StatCard title="Pending Grading" value="--" />
        <StatCard title="Completed" value="--" />
      </div>
    </div>
  );
}

function StatCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-lg border bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-gray-500">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
    </div>
  );
}
