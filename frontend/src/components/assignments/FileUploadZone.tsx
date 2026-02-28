"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { uploadSubmission } from "@/lib/api";

interface Props {
  assignmentId: string;
}

const ACCEPTED_TYPES = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/heic": [".heic"],
  "image/bmp": [".bmp"],
  "application/pdf": [".pdf"],
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
};

export default function FileUploadZone({ assignmentId }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  const onDrop = useCallback((accepted: File[]) => {
    setFiles((prev) => [...prev, ...accepted]);
    setMessage("");
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: 20 * 1024 * 1024, // 20 MB
  });

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setMessage("");
    try {
      await uploadSubmission(assignmentId, files);
      setMessage("Upload successful! Your submission is being processed.");
      setFiles([]);
    } catch {
      setMessage("Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition ${
          isDragActive
            ? "border-primary-400 bg-primary-50"
            : "border-gray-300 bg-gray-50 hover:border-gray-400"
        }`}
      >
        <input {...getInputProps()} />
        <p className="text-sm text-gray-600">
          {isDragActive
            ? "Drop files here..."
            : "Drag & drop files here, or click to select"}
        </p>
        <p className="mt-1 text-xs text-gray-400">
          JPG, PNG, PDF, DOCX — max 20MB per file
        </p>
      </div>

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((file, i) => (
            <li
              key={`${file.name}-${i}`}
              className="flex items-center justify-between rounded-md border bg-white px-3 py-2 text-sm"
            >
              <span className="truncate">{file.name}</span>
              <button
                onClick={() => removeFile(i)}
                className="ml-2 text-red-500 hover:text-red-700"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <button
        onClick={handleUpload}
        disabled={files.length === 0 || uploading}
        className="rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:opacity-50"
      >
        {uploading ? "Uploading..." : "Upload & Submit"}
      </button>

      {message && (
        <p className={`text-sm ${message.includes("failed") ? "text-red-600" : "text-green-600"}`}>
          {message}
        </p>
      )}
    </div>
  );
}
