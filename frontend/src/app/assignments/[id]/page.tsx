"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { getAssignment } from "@/lib/api";
import { useI18n } from "@/i18n/provider";
import FileUploadZone from "@/components/assignments/FileUploadZone";
import type { Assignment } from "@/types";

export default function AssignmentDetailPage() {
  const params = useParams();
  const { t } = useI18n();
  const [assignment, setAssignment] = useState<Assignment | null>(null);

  const load = useCallback(() => {
    if (params.id) {
      getAssignment(params.id as string).then(setAssignment).catch(() => {});
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  if (!assignment)
    return <p className="text-gray-500">{t("common.loading")}</p>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">{assignment.title}</h1>
      <div className="flex gap-2 text-sm text-gray-500">
        <span className="capitalize">{assignment.status}</span>
        {assignment.due_date && (
          <>
            <span>&middot;</span>
            <span>
              {t("assignments.dueDate")}{" "}
              {new Date(assignment.due_date).toLocaleDateString()}
            </span>
          </>
        )}
      </div>

      <section className="rounded-lg border bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">
          {t("assignments.submitAssignment")}
        </h2>
        <FileUploadZone assignmentId={assignment.id} />
      </section>
    </div>
  );
}
