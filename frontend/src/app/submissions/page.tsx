"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import api from "@/lib/api";
import type { Submission } from "@/types";

export default function SubmissionsPage() {
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Submission[]>("/submissions/")
      .then((res) => setSubmissions(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const statusColor: Record<string, string> = {
    uploaded: "bg-gray-100 text-gray-700",
    processing: "bg-blue-100 text-blue-700",
    ocr_complete: "bg-indigo-100 text-indigo-700",
    grading: "bg-yellow-100 text-yellow-700",
    graded: "bg-green-100 text-green-700",
    reviewed: "bg-emerald-100 text-emerald-700",
    error: "bg-red-100 text-red-700",
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">My Submissions</h1>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : submissions.length === 0 ? (
        <p className="text-gray-500">No submissions yet.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Submitted
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium uppercase text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {submissions.map((s) => (
                <tr key={s.id}>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    {new Date(s.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
                        statusColor[s.status] ?? "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {s.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-sm">
                    {(s.status === "graded" || s.status === "reviewed") && (
                      <Link
                        href={`/grading/${s.id}`}
                        className="text-primary-600 hover:underline"
                      >
                        View Feedback
                      </Link>
                    )}
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
