"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { getGradingResult, submitTeacherReview } from "@/lib/api";
import type { GradingResult, QuestionFeedback } from "@/types";

export default function GradingReviewPage() {
  const params = useParams();
  const [result, setResult] = useState<GradingResult | null>(null);
  const [edits, setEdits] = useState<
    Record<string, { score?: number; feedback?: string }>
  >({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    if (params.id) {
      getGradingResult(params.id as string).then(setResult).catch(() => {});
    }
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSaveReview = async () => {
    if (!result) return;
    setSaving(true);
    const reviews = Object.entries(edits).map(([qn, v]) => ({
      question_number: qn,
      teacher_score: v.score,
      teacher_feedback: v.feedback,
    }));
    try {
      await submitTeacherReview(result.id, reviews);
      load();
    } catch {
      /* show error toast */
    } finally {
      setSaving(false);
    }
  };

  if (!result) return <p className="text-gray-500">Loading grading results...</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Grading Review</h1>
        <div className="text-sm text-gray-500">
          Confidence: {((result.confidence_score ?? 0) * 100).toFixed(0)}%
          {result.needs_review && (
            <span className="ml-2 rounded bg-yellow-100 px-2 py-0.5 text-yellow-800">
              Needs Review
            </span>
          )}
        </div>
      </div>

      <div className="rounded-lg border bg-white p-5 shadow-sm">
        <p className="text-lg font-semibold">
          Total: {result.total_score ?? 0}/{result.total_possible ?? 0}
        </p>
        <p className="mt-1 text-sm text-gray-600">{result.overall_feedback}</p>
      </div>

      <div className="space-y-4">
        {result.question_feedbacks.map((qf) => (
          <QuestionCard
            key={qf.id}
            qf={qf}
            edit={edits[qf.question_number]}
            onEdit={(v) =>
              setEdits({ ...edits, [qf.question_number]: { ...edits[qf.question_number], ...v } })
            }
          />
        ))}
      </div>

      {Object.keys(edits).length > 0 && (
        <button
          onClick={handleSaveReview}
          disabled={saving}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save Review"}
        </button>
      )}
    </div>
  );
}

function QuestionCard({
  qf,
  edit,
  onEdit,
}: {
  qf: QuestionFeedback;
  edit?: { score?: number; feedback?: string };
  onEdit: (v: { score?: number; feedback?: string }) => void;
}) {
  return (
    <div className="rounded-lg border bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <h3 className="font-semibold">Q{qf.question_number}</h3>
        <span className="text-sm font-medium">
          {qf.teacher_score ?? qf.score ?? 0}/{qf.max_score ?? 0}
        </span>
      </div>

      {qf.student_answer && (
        <div className="mt-2 rounded bg-gray-50 p-3 text-sm text-gray-700">
          <p className="text-xs font-medium text-gray-500">Student Answer</p>
          {qf.student_answer}
        </div>
      )}

      <div className="mt-3 space-y-2 text-sm">
        {qf.scoring_rationale && (
          <p>
            <span className="font-medium text-gray-600">Rationale:</span>{" "}
            {qf.scoring_rationale}
          </p>
        )}
        {qf.error_analysis && (
          <p>
            <span className="font-medium text-red-600">Error:</span>{" "}
            {qf.error_analysis}
          </p>
        )}
        {qf.improvement_suggestions && (
          <p>
            <span className="font-medium text-blue-600">Suggestion:</span>{" "}
            {qf.improvement_suggestions}
          </p>
        )}
      </div>

      <div className="mt-4 flex gap-4">
        <div>
          <label className="text-xs font-medium text-gray-500">Override Score</label>
          <input
            type="number"
            step="0.5"
            min={0}
            max={qf.max_score ?? 100}
            placeholder={String(qf.score ?? "")}
            value={edit?.score ?? ""}
            onChange={(e) => onEdit({ score: e.target.value ? parseFloat(e.target.value) : undefined })}
            className="mt-1 block w-20 rounded border px-2 py-1 text-sm"
          />
        </div>
        <div className="flex-1">
          <label className="text-xs font-medium text-gray-500">Teacher Feedback</label>
          <input
            type="text"
            placeholder="Add feedback..."
            value={edit?.feedback ?? ""}
            onChange={(e) => onEdit({ feedback: e.target.value || undefined })}
            className="mt-1 block w-full rounded border px-2 py-1 text-sm"
          />
        </div>
      </div>
    </div>
  );
}
