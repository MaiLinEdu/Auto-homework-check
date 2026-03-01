"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import {
  getGradingResult,
  submitTeacherReview,
  generateParentReport,
} from "@/lib/api";
import type { ParentReport } from "@/lib/api";
import { useI18n } from "@/i18n/provider";
import NormalDistributionChart from "@/components/grading/NormalDistributionChart";
import type { GradingResult, QuestionFeedback } from "@/types";

export default function GradingReviewPage() {
  const params = useParams();
  const { t } = useI18n();
  const [result, setResult] = useState<GradingResult | null>(null);
  const [edits, setEdits] = useState<
    Record<string, { score?: number; feedback?: string }>
  >({});
  const [saving, setSaving] = useState(false);

  // Report state
  const [report, setReport] = useState<ParentReport | null>(null);
  const [reportEdits, setReportEdits] = useState<Partial<ParentReport>>({});
  const [generatingReport, setGeneratingReport] = useState(false);
  const [reportMessage, setReportMessage] = useState("");
  const [editingReport, setEditingReport] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);

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

  const handleGenerateReport = async () => {
    if (!result) return;
    setGeneratingReport(true);
    setReportMessage("");
    try {
      const data = await generateParentReport({
        grading_result_id: result.id,
        student_name: "Student", // would come from submission data
        subject: "General",
        language: "bilingual",
      });
      setReport(data);
      setReportEdits({});
      setReportMessage(t("gradingReview.reportGenerated"));
    } catch {
      setReportMessage(t("gradingReview.reportError"));
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleExportPdf = () => {
    if (!reportRef.current) return;
    window.print();
  };

  const currentReport = report
    ? {
        ...report,
        ...reportEdits,
      }
    : null;

  if (!result)
    return <p className="text-gray-500">{t("common.loading")}</p>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          {t("gradingReview.title")}
        </h1>
        <div className="flex items-center gap-3">
          <div className="text-sm text-gray-500">
            {t("gradingReview.confidence")}:{" "}
            {((result.confidence_score ?? 0) * 100).toFixed(0)}%
            {result.needs_review && (
              <span className="ml-2 rounded bg-yellow-100 px-2 py-0.5 text-yellow-800">
                {t("gradingReview.needsReview")}
              </span>
            )}
          </div>
          <button
            onClick={handleGenerateReport}
            disabled={generatingReport}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {generatingReport
              ? t("gradingReview.generatingReport")
              : t("gradingReview.generateReport")}
          </button>
        </div>
      </div>

      {/* Score Summary */}
      <div className="rounded-lg border bg-white p-5 shadow-sm">
        <p className="text-lg font-semibold">
          {t("gradingReview.total")}: {result.total_score ?? 0}/
          {result.total_possible ?? 0}
        </p>
        <p className="mt-1 text-sm text-gray-600">
          {result.overall_feedback}
        </p>
      </div>

      {/* Question Cards */}
      <div className="space-y-4">
        {result.question_feedbacks.map((qf) => (
          <QuestionCard
            key={qf.id}
            qf={qf}
            edit={edits[qf.question_number]}
            onEdit={(v) =>
              setEdits({
                ...edits,
                [qf.question_number]: {
                  ...edits[qf.question_number],
                  ...v,
                },
              })
            }
            t={t}
          />
        ))}
      </div>

      {Object.keys(edits).length > 0 && (
        <button
          onClick={handleSaveReview}
          disabled={saving}
          className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
        >
          {saving ? t("gradingReview.saving") : t("gradingReview.saveReview")}
        </button>
      )}

      {/* AI Feedback Report */}
      {reportMessage && (
        <p
          className={`text-sm ${
            reportMessage.includes("fail") || reportMessage.includes("失败")
              ? "text-red-600"
              : "text-green-600"
          }`}
        >
          {reportMessage}
        </p>
      )}

      {currentReport && (
        <div
          ref={reportRef}
          className="space-y-6 rounded-lg border-2 border-emerald-200 bg-white p-6 shadow-sm print:border-none print:shadow-none"
        >
          <div className="flex items-center justify-between border-b pb-4">
            <h2 className="text-xl font-bold text-emerald-800">
              {t("gradingReview.reportTitle")}
            </h2>
            <div className="flex gap-2 print:hidden">
              <button
                onClick={() => setEditingReport(!editingReport)}
                className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                {t("gradingReview.editReport")}
              </button>
              <button
                onClick={handleExportPdf}
                className="rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700"
              >
                {t("gradingReview.exportPdf")}
              </button>
            </div>
          </div>

          {/* Performance Summary */}
          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-emerald-700">
              {t("gradingReview.performanceSummary")}
            </h3>
            {editingReport ? (
              <textarea
                value={
                  reportEdits.performance_summary ??
                  currentReport.performance_summary
                }
                onChange={(e) =>
                  setReportEdits({
                    ...reportEdits,
                    performance_summary: e.target.value,
                  })
                }
                className="w-full rounded-md border p-3 text-sm"
                rows={4}
              />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                {currentReport.performance_summary}
              </p>
            )}
          </section>

          {/* Core Error Analysis */}
          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-red-600">
              {t("gradingReview.coreErrorAnalysis")}
            </h3>
            {editingReport ? (
              <textarea
                value={
                  reportEdits.core_error_analysis ??
                  currentReport.core_error_analysis
                }
                onChange={(e) =>
                  setReportEdits({
                    ...reportEdits,
                    core_error_analysis: e.target.value,
                  })
                }
                className="w-full rounded-md border p-3 text-sm"
                rows={6}
              />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                {currentReport.core_error_analysis}
              </p>
            )}
          </section>

          {/* Improvement Suggestions */}
          <section>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-blue-600">
              {t("gradingReview.improvementSuggestions")}
            </h3>
            {editingReport ? (
              <textarea
                value={
                  reportEdits.improvement_suggestions ??
                  currentReport.improvement_suggestions
                }
                onChange={(e) =>
                  setReportEdits({
                    ...reportEdits,
                    improvement_suggestions: e.target.value,
                  })
                }
                className="w-full rounded-md border p-3 text-sm"
                rows={6}
              />
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                {currentReport.improvement_suggestions}
              </p>
            )}
          </section>

          {/* Normal Distribution Chart */}
          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-600">
              {t("gradingReview.percentileRank")} —{" "}
              {t("gradingReview.normalDistribution")}
            </h3>
            <NormalDistributionChart
              mean={currentReport.mean_score}
              stdDev={currentReport.std_dev}
              studentScore={currentReport.student_score}
              totalPossible={currentReport.total_possible}
              label={t("gradingReview.studentPercentile")}
            />
          </section>
        </div>
      )}
    </div>
  );
}

function QuestionCard({
  qf,
  edit,
  onEdit,
  t,
}: {
  qf: QuestionFeedback;
  edit?: { score?: number; feedback?: string };
  onEdit: (v: { score?: number; feedback?: string }) => void;
  t: (key: string) => string;
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
          <p className="text-xs font-medium text-gray-500">
            {t("gradingReview.studentAnswer")}
          </p>
          {qf.student_answer}
        </div>
      )}

      <div className="mt-3 space-y-2 text-sm">
        {qf.scoring_rationale && (
          <p>
            <span className="font-medium text-gray-600">
              {t("gradingReview.rationale")}:
            </span>{" "}
            {qf.scoring_rationale}
          </p>
        )}
        {qf.error_analysis && (
          <p>
            <span className="font-medium text-red-600">
              {t("gradingReview.error")}:
            </span>{" "}
            {qf.error_analysis}
          </p>
        )}
        {qf.improvement_suggestions && (
          <p>
            <span className="font-medium text-blue-600">
              {t("gradingReview.suggestion")}:
            </span>{" "}
            {qf.improvement_suggestions}
          </p>
        )}
      </div>

      <div className="mt-4 flex gap-4">
        <div>
          <label className="text-xs font-medium text-gray-500">
            {t("gradingReview.overrideScore")}
          </label>
          <input
            type="number"
            step="0.5"
            min={0}
            max={qf.max_score ?? 100}
            placeholder={String(qf.score ?? "")}
            value={edit?.score ?? ""}
            onChange={(e) =>
              onEdit({
                score: e.target.value
                  ? parseFloat(e.target.value)
                  : undefined,
              })
            }
            className="mt-1 block w-20 rounded border px-2 py-1 text-sm"
          />
        </div>
        <div className="flex-1">
          <label className="text-xs font-medium text-gray-500">
            {t("gradingReview.teacherFeedback")}
          </label>
          <input
            type="text"
            placeholder={t("gradingReview.addFeedback")}
            value={edit?.feedback ?? ""}
            onChange={(e) =>
              onEdit({ feedback: e.target.value || undefined })
            }
            className="mt-1 block w-full rounded border px-2 py-1 text-sm"
          />
        </div>
      </div>
    </div>
  );
}
