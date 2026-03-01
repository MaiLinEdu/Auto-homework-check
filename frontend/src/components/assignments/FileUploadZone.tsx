"use client";

import { useState, useCallback, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useI18n } from "@/i18n/provider";
import { uploadSubmission } from "@/lib/api";
import api from "@/lib/api";
import type { MarkScheme } from "@/types";

interface Props {
  assignmentId: string;
}

interface UploadBatch {
  files: File[];
  markSchemeId: string;
  syllabusId: string;
}

const ACCEPTED_TYPES = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "application/pdf": [".pdf"],
};

export default function FileUploadZone({ assignmentId }: Props) {
  const { t } = useI18n();
  const [batches, setBatches] = useState<UploadBatch[]>([
    { files: [], markSchemeId: "", syllabusId: "" },
  ]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [markSchemes, setMarkSchemes] = useState<MarkScheme[]>([]);
  const [syllabi, setSyllabi] = useState<{ id: string; title: string }[]>([]);

  useEffect(() => {
    api
      .get<MarkScheme[]>("/mark-schemes/")
      .then((res) => setMarkSchemes(res.data))
      .catch(() => {});
    api
      .get<{ id: string; title: string }[]>("/curriculum/syllabi")
      .then((res) => setSyllabi(res.data))
      .catch(() => {});
  }, []);

  const onDropForBatch = useCallback(
    (batchIndex: number) => (accepted: File[]) => {
      setBatches((prev) =>
        prev.map((batch, i) =>
          i === batchIndex
            ? { ...batch, files: [...batch.files, ...accepted] }
            : batch
        )
      );
      setMessage("");
    },
    []
  );

  const removeFile = (batchIndex: number, fileIndex: number) => {
    setBatches((prev) =>
      prev.map((batch, i) =>
        i === batchIndex
          ? { ...batch, files: batch.files.filter((_, fi) => fi !== fileIndex) }
          : batch
      )
    );
  };

  const updateBatch = (
    batchIndex: number,
    field: "markSchemeId" | "syllabusId",
    value: string
  ) => {
    setBatches((prev) =>
      prev.map((batch, i) =>
        i === batchIndex ? { ...batch, [field]: value } : batch
      )
    );
  };

  const addBatch = () => {
    setBatches((prev) => [
      ...prev,
      { files: [], markSchemeId: "", syllabusId: "" },
    ]);
  };

  const removeBatch = (index: number) => {
    if (batches.length <= 1) return;
    setBatches((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    const allFiles = batches.flatMap((b) => b.files);
    if (allFiles.length === 0) return;
    setUploading(true);
    setMessage("");
    try {
      for (const batch of batches) {
        if (batch.files.length === 0) continue;
        await uploadSubmission(
          assignmentId,
          batch.files,
          batch.markSchemeId || undefined,
          batch.syllabusId || undefined
        );
      }
      setMessage(t("upload.uploadSuccess"));
      setBatches([{ files: [], markSchemeId: "", syllabusId: "" }]);
    } catch {
      setMessage(t("upload.uploadFailed"));
    } finally {
      setUploading(false);
    }
  };

  const totalFiles = batches.reduce((sum, b) => sum + b.files.length, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-700">
          {t("upload.batchUpload")}
        </h3>
        <button
          onClick={addBatch}
          className="rounded-md border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
        >
          + {t("upload.batchUpload")}
        </button>
      </div>

      <p className="text-xs text-gray-500">{t("upload.associateFiles")}</p>

      {batches.map((batch, batchIndex) => (
        <BatchCard
          key={batchIndex}
          batch={batch}
          batchIndex={batchIndex}
          totalBatches={batches.length}
          markSchemes={markSchemes}
          syllabi={syllabi}
          onDrop={onDropForBatch(batchIndex)}
          onRemoveFile={(fi) => removeFile(batchIndex, fi)}
          onUpdateBatch={(field, val) => updateBatch(batchIndex, field, val)}
          onRemoveBatch={() => removeBatch(batchIndex)}
          t={t}
        />
      ))}

      <button
        onClick={handleUpload}
        disabled={totalFiles === 0 || uploading}
        className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
      >
        {uploading ? t("upload.uploading") : t("upload.uploadSubmit")}
      </button>

      {message && (
        <p
          className={`text-sm ${
            message.includes("failed") || message.includes("失败")
              ? "text-red-600"
              : "text-green-600"
          }`}
        >
          {message}
        </p>
      )}
    </div>
  );
}

function BatchCard({
  batch,
  batchIndex,
  totalBatches,
  markSchemes,
  syllabi,
  onDrop,
  onRemoveFile,
  onUpdateBatch,
  onRemoveBatch,
  t,
}: {
  batch: UploadBatch;
  batchIndex: number;
  totalBatches: number;
  markSchemes: MarkScheme[];
  syllabi: { id: string; title: string }[];
  onDrop: (files: File[]) => void;
  onRemoveFile: (fileIndex: number) => void;
  onUpdateBatch: (field: "markSchemeId" | "syllabusId", value: string) => void;
  onRemoveBatch: () => void;
  t: (key: string) => string;
}) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 20 * 1024 * 1024,
  });

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-gray-700">
          #{batchIndex + 1}
        </span>
        {totalBatches > 1 && (
          <button
            onClick={onRemoveBatch}
            className="text-xs text-red-500 hover:text-red-700"
          >
            {t("common.delete")}
          </button>
        )}
      </div>

      <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">
            {t("upload.markScheme")}
          </label>
          <select
            value={batch.markSchemeId}
            onChange={(e) => onUpdateBatch("markSchemeId", e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="">{t("upload.selectScheme")}</option>
            {markSchemes.map((ms) => (
              <option key={ms.id} value={ms.id}>
                {ms.title}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-500">
            {t("upload.syllabus")}
          </label>
          <select
            value={batch.syllabusId}
            onChange={(e) => onUpdateBatch("syllabusId", e.target.value)}
            className="block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
          >
            <option value="">{t("upload.selectSyllabus")}</option>
            {syllabi.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div
        {...getRootProps()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-6 text-center transition ${
          isDragActive
            ? "border-primary-400 bg-primary-50"
            : "border-gray-300 bg-gray-50 hover:border-gray-400"
        }`}
      >
        <input {...getInputProps()} />
        <p className="text-sm text-gray-600">
          {isDragActive ? t("upload.dropHere") : t("upload.dragDrop")}
        </p>
        <p className="mt-1 text-xs text-gray-400">{t("upload.fileTypes")}</p>
      </div>

      {batch.files.length > 0 && (
        <ul className="mt-3 space-y-1">
          {batch.files.map((file, i) => (
            <li
              key={`${file.name}-${i}`}
              className="flex items-center justify-between rounded-md border bg-gray-50 px-3 py-1.5 text-sm"
            >
              <span className="truncate">{file.name}</span>
              <button
                onClick={() => onRemoveFile(i)}
                className="ml-2 text-xs text-red-500 hover:text-red-700"
              >
                {t("upload.remove")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
