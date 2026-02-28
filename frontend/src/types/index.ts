/* ===== Core domain types for GradeAI ===== */

// --- Auth & Users ---
export type UserRole = "super_admin" | "school_admin" | "teacher" | "student";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  school_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  role: UserRole;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

// --- Curriculum ---
export interface CurriculumSystem {
  id: string;
  name: string; // "IB", "A-Level", "AP"
  description: string;
}

export interface Subject {
  id: string;
  name: string;
  curriculum_system_id: string;
  category: SubjectCategory;
}

export type SubjectCategory =
  | "stem_calculation"
  | "stem_essay"
  | "humanities_essay"
  | "data_analysis";

// --- Assignments ---
export type AssignmentStatus = "draft" | "published" | "closed" | "archived";

export interface Assignment {
  id: string;
  title: string;
  subject_id: string;
  curriculum_system_id: string;
  created_by: string;
  mark_scheme_id: string | null;
  status: AssignmentStatus;
  due_date: string | null;
  created_at: string;
}

export interface AssignmentCreateRequest {
  title: string;
  subject_id: string;
  curriculum_system_id: string;
  mark_scheme_id?: string;
  due_date?: string;
}

// --- Submissions ---
export type SubmissionStatus =
  | "uploaded"
  | "processing"
  | "ocr_complete"
  | "grading"
  | "graded"
  | "reviewed"
  | "error";

export interface Submission {
  id: string;
  assignment_id: string;
  student_id: string;
  status: SubmissionStatus;
  file_urls: string[];
  ocr_text: string | null;
  created_at: string;
}

// --- Grading ---
export interface QuestionFeedback {
  id: string;
  question_number: string;
  question_text: string | null;
  student_answer: string | null;
  score: number | null;
  max_score: number | null;
  scoring_rationale: string | null;
  error_analysis: string | null;
  error_type: string | null;
  model_solution: string | null;
  improvement_suggestions: string | null;
  knowledge_points: Record<string, unknown> | null;
  confidence: number | null;
  teacher_score: number | null;
  teacher_feedback: string | null;
}

export interface GradingResult {
  id: string;
  submission_id: string;
  total_score: number | null;
  total_possible: number | null;
  overall_feedback: string | null;
  confidence_score: number | null;
  needs_review: boolean;
  status: string;
  graded_at: string;
  reviewed_at: string | null;
  question_feedbacks: QuestionFeedback[];
}

// --- Mark Schemes ---
export interface MarkScheme {
  id: string;
  title: string;
  subject_id: string | null;
  curriculum_system_id: string | null;
  is_official: boolean;
  total_marks: number | null;
  current_version: number;
  created_at: string;
}
