"""AI Grading Engine — LLM-based grading with Pydantic structured output.

Key design decisions:
- Pydantic models enforce strict JSON schema on LLM output.
- Subject-category-specific prompt strategies (STEM calc vs Humanities essay).
- Explicit partial-credit / method-marks logic for IB/A-Level/AP STEM.
- Retry + JSON repair for robustness against malformed LLM responses.
"""

import json
import logging
import re
from enum import Enum
from typing import Literal

import anthropic
import openai
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Pydantic output schemas — the contract between LLM and our system
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ErrorType(str, Enum):
    conceptual = "conceptual"
    calculation = "calculation"
    expression = "expression"
    missing_key_points = "missing_key_points"
    none = "none"


class CriterionBreakdown(BaseModel):
    """One row of the mark-scheme rubric assessment."""
    criterion: str = Field(..., description="Name or description of the scoring criterion")
    marks_available: float = Field(..., ge=0)
    marks_awarded: float = Field(..., ge=0)
    justification: str = Field(..., description="Why this mark was (or was not) awarded")


class MethodMark(BaseModel):
    """A partial-credit award for a correct intermediate step."""
    step_description: str = Field(..., description="What the student did correctly")
    marks_awarded: float = Field(..., ge=0)


class QuestionGrade(BaseModel):
    """Structured grading output for a single question."""
    question_number: str = ""
    score: float = Field(..., ge=0, description="Total marks awarded")
    max_score: float = Field(..., ge=0, description="Maximum possible marks")

    criteria_breakdown: list[CriterionBreakdown] = Field(
        default_factory=list,
        description="Per-criterion scoring breakdown matching the mark scheme",
    )
    method_marks: list[MethodMark] = Field(
        default_factory=list,
        description="Partial credit for correct intermediate steps (STEM)",
    )

    error_analysis: str = Field(
        default="",
        description="Specific description of where/why the student went wrong",
    )
    error_type: ErrorType = Field(
        default=ErrorType.none,
        description="Classification of the primary error",
    )
    scoring_rationale: str = Field(
        default="",
        description="Overall explanation of the grading decision",
    )
    model_solution: str = Field(
        default="",
        description="Key steps of the reference solution",
    )
    improvement_suggestions: str = Field(
        default="",
        description="Personalized advice for the student",
    )
    knowledge_points: list[str] = Field(
        default_factory=list,
        description="Relevant knowledge point / topic tags",
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="Grader confidence in this assessment",
    )

    @field_validator("score")
    @classmethod
    def score_lte_max(cls, v, info):
        max_s = info.data.get("max_score")
        if max_s is not None and v > max_s:
            return max_s
        return v


class GradingOutput(BaseModel):
    """Full grading output for an entire submission."""
    question_grades: list[QuestionGrade] = Field(default_factory=list)
    total_score: float = 0.0
    total_possible: float = 0.0
    overall_feedback: str = ""
    confidence: float = 0.0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Subject-specific prompt strategies
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SubjectCategory = Literal[
    "stem_calculation", "stem_essay", "humanities_essay", "data_analysis"
]

_SUBJECT_PROMPTS: dict[str, str] = {
    "stem_calculation": """## Subject-Specific Instructions: STEM Calculation (Math / Physics)

You are grading a calculation-heavy STEM question. Apply these rules strictly:

1. **Method Marks (M-marks):** Award marks for each correct METHOD STEP even if the
   final numerical answer is wrong. If the student selects the right formula, sets up
   the equation correctly, or performs valid algebraic manipulation, award the
   corresponding method mark. Populate the `method_marks` array for every such step.

2. **Accuracy Marks (A-marks):** Award only if the preceding method is correct AND
   the numerical result is accurate (including correct units and significant figures).

3. **Follow-Through Marks:** If an earlier step has an arithmetic error but the
   student correctly applies the right method to their (wrong) intermediate value,
   award method marks for subsequent steps (ECF — Error Carried Forward).

4. **Units & Sig Figs:** Note any unit errors or significant figure violations in
   error_analysis, but only deduct marks if the mark scheme explicitly requires it.

5. **Criteria Breakdown:** Map each scoring point from the mark scheme to a
   `criteria_breakdown` entry showing marks_available vs marks_awarded.""",

    "stem_essay": """## Subject-Specific Instructions: STEM Essay (Biology / Chemistry)

You are grading a scientific explanation or essay question. Apply these rules:

1. **Key Terminology:** Check whether the student uses correct scientific vocabulary.
   Missing or misused terms should be noted in error_analysis.

2. **Causal Logic:** The explanation must show clear cause-and-effect reasoning.
   Award marks for each logical link in the chain of reasoning.

3. **Experimental Design:** If the question involves experimental methodology,
   evaluate variables (IV, DV, controlled), hypothesis clarity, and validity.

4. **Diagrams / Equations:** If chemical equations or biological diagrams are
   relevant, assess their correctness and completeness.

5. **Criteria Breakdown:** Map mark scheme points to `criteria_breakdown`. Award
   partial credit for partially correct explanations.""",

    "humanities_essay": """## Subject-Specific Instructions: Humanities Essay (History / Economics / English)

You are grading an analytical or evaluative essay. Apply these rules:

1. **Thesis / Argument:** Does the student present a clear, defensible thesis?
   Award marks for argument clarity and positioning.

2. **Evidence & Examples:** Are claims supported with specific, relevant evidence?
   Check for factual accuracy and appropriate sourcing.

3. **Critical Analysis:** Does the student go beyond description to evaluate,
   compare, or challenge perspectives? Depth of analysis is key.

4. **Structure & Coherence:** Assess logical flow: introduction, body paragraphs
   with topic sentences, transitions, and conclusion.

5. **Language Quality:** Evaluate academic register, grammar, and vocabulary
   sophistication — but weight this less than content.

6. **Counter-Arguments:** In evaluation questions, does the student acknowledge
   and address opposing viewpoints?

7. **Criteria Breakdown:** Map each assessment objective from the mark scheme to
   a `criteria_breakdown` entry.""",

    "data_analysis": """## Subject-Specific Instructions: Data Analysis (Economics graphs / Physics data)

You are grading a data-interpretation or graph-analysis question. Apply these rules:

1. **Data Reading:** Check that values are read accurately from tables/graphs.
   Note any misreadings in error_analysis.

2. **Trend Identification:** Does the student correctly identify patterns,
   correlations, or anomalies in the data?

3. **Calculation:** If numerical operations are required (percentage change,
   gradient, area under curve), apply method-mark logic as in STEM calculation.

4. **Error & Uncertainty:** For experimental data, assess whether the student
   discusses sources of error, uncertainty, and reliability.

5. **Interpretation:** Does the student connect data patterns to underlying
   theory or real-world implications?

6. **Criteria Breakdown:** Map each rubric point to `criteria_breakdown`.""",
}

# The JSON schema the LLM must produce (derived from Pydantic model)
_OUTPUT_SCHEMA_STR = json.dumps(QuestionGrade.model_json_schema(), indent=2)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AIGrader class
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AIGrader:
    """Orchestrates LLM-based grading using Anthropic Claude or OpenAI GPT."""

    MAX_PARSE_RETRIES = 2

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        if provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    # ── Prompt construction ──────────────────────────────────────────────────

    def _build_grading_prompt(
        self,
        question_text: str,
        student_answer: str,
        mark_scheme: dict,
        subject_category: SubjectCategory,
    ) -> str:
        """Build a subject-aware grading prompt with strict schema."""

        subject_instructions = _SUBJECT_PROMPTS.get(
            subject_category, _SUBJECT_PROMPTS["stem_calculation"]
        )

        mark_scheme_str = (
            json.dumps(mark_scheme, indent=2, ensure_ascii=False)
            if isinstance(mark_scheme, dict)
            else str(mark_scheme)
        )

        return f"""You are an expert examiner for international curriculum assessments (IB, A-Level, AP).
Your task is to grade a student's answer STRICTLY according to the provided mark scheme.

{subject_instructions}

## Mark Scheme
```json
{mark_scheme_str}
```

## Question
{question_text}

## Student Answer
{student_answer}

## Output Format
You MUST return a single valid JSON object conforming to this schema:
```json
{_OUTPUT_SCHEMA_STR}
```

Critical rules:
- `score` must be <= `max_score`.
- `criteria_breakdown` must have one entry per mark-scheme criterion.
- For STEM calculation questions, populate `method_marks` for every correct intermediate step
  (even if the final answer is wrong). This is ESSENTIAL for IB/A-Level partial credit.
- `error_type` must be one of: "conceptual", "calculation", "expression", "missing_key_points", "none".
- `confidence` is YOUR confidence in the grading (0.0-1.0), not the student's.

Return ONLY the JSON object. No markdown fences. No surrounding text."""

    # ── JSON extraction + repair ─────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> str:
        """Extract a JSON object from LLM text, stripping markdown fences."""
        cleaned = text.strip()
        # Remove markdown code fences
        if cleaned.startswith("```"):
            # Remove opening fence (possibly with "json" label)
            cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].rstrip()
        # Find the outermost { ... }
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return cleaned[start : end + 1]
        return cleaned

    # ── Single-question grading ──────────────────────────────────────────────

    async def grade_question(
        self,
        question_text: str,
        student_answer: str,
        mark_scheme: dict,
        subject_category: SubjectCategory = "stem_calculation",
    ) -> QuestionGrade:
        """Grade a single question with retry on parse failure."""

        prompt = self._build_grading_prompt(
            question_text, student_answer, mark_scheme, subject_category
        )

        last_error = ""
        for attempt in range(1 + self.MAX_PARSE_RETRIES):
            if attempt > 0:
                # On retry, append the parse error so the LLM can self-correct
                prompt_with_fix = (
                    prompt
                    + f"\n\n[SYSTEM: Your previous response was not valid JSON. "
                    f"Error: {last_error}. Please return ONLY a valid JSON object.]"
                )
            else:
                prompt_with_fix = prompt

            response_text = await self.raw_completion(prompt_with_fix)
            json_str = self._extract_json(response_text)

            try:
                grade = QuestionGrade.model_validate_json(json_str)
                return grade
            except Exception as e:
                last_error = str(e)[:200]
                logger.warning(
                    "Grade parse attempt %d/%d failed: %s",
                    attempt + 1, 1 + self.MAX_PARSE_RETRIES, last_error,
                )

        # All retries exhausted — return a low-confidence fallback
        logger.error("All parse retries exhausted. Returning fallback grade.")
        return QuestionGrade(
            score=0,
            max_score=0,
            scoring_rationale="Failed to parse AI response after retries.",
            error_analysis=f"Parse error: {last_error}",
            error_type=ErrorType.none,
            model_solution="",
            improvement_suggestions="",
            confidence=0.0,
        )

    # ── Full-submission grading ──────────────────────────────────────────────

    async def grade_submission(
        self,
        questions: list[dict],
        mark_scheme: dict,
        subject_category: SubjectCategory = "stem_calculation",
    ) -> GradingOutput:
        """Grade all questions in a submission sequentially."""
        grades: list[QuestionGrade] = []
        total_score = 0.0
        total_possible = 0.0

        for q in questions:
            grade = await self.grade_question(
                question_text=q.get("question_text", ""),
                student_answer=q.get("student_answer", ""),
                mark_scheme=mark_scheme,
                subject_category=subject_category,
            )
            grade.question_number = q.get("question_number", str(len(grades) + 1))
            grades.append(grade)
            total_score += grade.score
            total_possible += grade.max_score

        avg_confidence = (
            sum(g.confidence for g in grades) / len(grades) if grades else 0.0
        )

        return GradingOutput(
            question_grades=grades,
            total_score=total_score,
            total_possible=total_possible,
            overall_feedback=self._generate_overall_feedback(grades),
            confidence=round(avg_confidence, 4),
        )

    # ── Overall feedback synthesis ───────────────────────────────────────────

    @staticmethod
    def _generate_overall_feedback(grades: list[QuestionGrade]) -> str:
        """Synthesise per-question grades into an overall summary."""
        if not grades:
            return "No questions were graded."

        total = sum(g.score for g in grades)
        possible = sum(g.max_score for g in grades)
        pct = (total / possible * 100) if possible > 0 else 0

        # Count error types
        error_counts: dict[str, int] = {}
        for g in grades:
            if g.error_type != ErrorType.none:
                error_counts[g.error_type.value] = error_counts.get(g.error_type.value, 0) + 1

        # Count method marks awarded
        total_method_marks = sum(
            mm.marks_awarded for g in grades for mm in g.method_marks
        )

        parts = [f"Overall score: {total:.1f}/{possible:.0f} ({pct:.0f}%)."]

        if total_method_marks > 0:
            parts.append(
                f"Method/process marks awarded: {total_method_marks:.1f} "
                f"(partial credit for correct working)."
            )

        if error_counts:
            most_common = max(error_counts, key=error_counts.get)
            parts.append(f"Most frequent error type: {most_common}.")

        # Collect unique knowledge points that need work
        weak_kps = set()
        for g in grades:
            if g.error_type != ErrorType.none:
                weak_kps.update(g.knowledge_points[:3])
        if weak_kps:
            parts.append(f"Areas to review: {', '.join(sorted(weak_kps)[:5])}.")

        parts.append("See per-question feedback for detailed guidance.")
        return " ".join(parts)

    # ── Raw LLM completion ───────────────────────────────────────────────────

    async def raw_completion(self, prompt: str) -> str:
        """Send a prompt to the configured LLM provider and return raw text."""
        if self.provider == "anthropic":
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        else:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content
