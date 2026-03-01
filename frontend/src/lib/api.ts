import axios from "axios";
import type {
  AuthResponse,
  LoginRequest,
  RegisterRequest,
  User,
  Assignment,
  AssignmentCreateRequest,
  Submission,
  GradingResult,
} from "@/types";

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1",
  headers: { "Content-Type": "application/json" },
});

// Attach JWT to every request when available
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// --- Auth ---
export async function login(data: LoginRequest): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("/auth/login", data);
  return res.data;
}

export async function register(data: RegisterRequest): Promise<User> {
  const res = await api.post<User>("/auth/register", data);
  return res.data;
}

export async function getCurrentUser(): Promise<User> {
  const res = await api.get<User>("/auth/me");
  return res.data;
}

// --- Assignments ---
export async function getAssignments(): Promise<Assignment[]> {
  const res = await api.get<Assignment[]>("/assignments/");
  return res.data;
}

export async function getAssignment(id: string): Promise<Assignment> {
  const res = await api.get<Assignment>(`/assignments/${id}`);
  return res.data;
}

export async function createAssignment(data: AssignmentCreateRequest): Promise<Assignment> {
  const res = await api.post<Assignment>("/assignments/", data);
  return res.data;
}

// --- Submissions ---
export async function uploadSubmission(
  assignmentId: string,
  files: File[],
): Promise<Submission> {
  const formData = new FormData();
  formData.append("assignment_id", assignmentId);
  files.forEach((file) => formData.append("files", file));

  const res = await api.post<Submission>("/submissions/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function getSubmission(id: string): Promise<Submission> {
  const res = await api.get<Submission>(`/submissions/${id}`);
  return res.data;
}

// --- Grading ---
export async function triggerGrading(
  submissionId: string,
  markSchemeId?: string,
): Promise<{ message: string; submission_id: string }> {
  const res = await api.post("/grading/grade", {
    submission_id: submissionId,
    mark_scheme_id: markSchemeId || null,
  });
  return res.data;
}

export async function getGradingResult(submissionId: string): Promise<GradingResult> {
  const res = await api.get<GradingResult>(`/grading/results/${submissionId}`);
  return res.data;
}

export async function submitTeacherReview(
  gradingResultId: string,
  reviews: { question_number: string; teacher_score?: number; teacher_feedback?: string }[],
): Promise<{ message: string }> {
  const res = await api.post(`/grading/review/${gradingResultId}`, reviews);
  return res.data;
}

export default api;
