"""AI Grading Engine — core LLM-based grading logic."""

from dataclasses import dataclass, field

import anthropic
import openai

from app.core.config import settings


@dataclass
class QuestionGrade:
    """Grading output for a single question."""
    question_number: str
    score: float
    max_score: float
    scoring_rationale: str
    error_analysis: str
    error_type: str  # conceptual, calculation, expression, missing_key_points, none
    model_solution: str
    improvement_suggestions: str
    knowledge_points: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class GradingOutput:
    """Full grading output for a submission."""
    question_grades: list[QuestionGrade] = field(default_factory=list)
    total_score: float = 0.0
    total_possible: float = 0.0
    overall_feedback: str = ""
    confidence: float = 0.0


class AIGrader:
    """Orchestrates LLM-based grading using Anthropic Claude or OpenAI GPT."""

    def __init__(self, provider: str = "anthropic"):
        self.provider = provider
        if provider == "anthropic":
            self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        else:
            self.openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

    def _build_grading_prompt(
        self,
        question_text: str,
        student_answer: str,
        mark_scheme: dict,
        subject_category: str,
    ) -> str:
        """Build a subject-aware grading prompt."""

        category_instructions = {
            "stem_calculation": (
                "Focus on: calculation process accuracy, formula application, "
                "unit conversion, significant figures. Award partial credit for "
                "correct intermediate steps even if the final answer is wrong."
            ),
            "stem_essay": (
                "Focus on: use of key scientific terminology, causal reasoning, "
                "experimental design soundness, logical structure of the explanation."
            ),
            "humanities_essay": (
                "Focus on: clarity and strength of the argument/thesis, sufficiency "
                "and relevance of evidence, text structure and coherence, depth of "
                "critical thinking, language quality and academic register."
            ),
            "data_analysis": (
                "Focus on: accuracy of data reading, trend identification and "
                "analysis, error discussion, appropriate use of statistical concepts."
            ),
        }

        category_detail = category_instructions.get(
            subject_category, category_instructions["stem_calculation"]
        )

        return f"""You are an expert grader for international curriculum examinations (IB, A-Level, AP).
Grade the following student answer according to the provided mark scheme.

## Instructions
{category_detail}

## Mark Scheme
{mark_scheme}

## Question
{question_text}

## Student Answer
{student_answer}

## Required Output (JSON)
Return a JSON object with these fields:
- "score": numeric score awarded
- "max_score": maximum possible score for this question
- "scoring_rationale": point-by-point explanation of how each criterion was met or missed
- "error_analysis": specific description of where and why the student went wrong (empty string if fully correct)
- "error_type": one of "conceptual", "calculation", "expression", "missing_key_points", "none"
- "model_solution": key steps of the reference/model solution
- "improvement_suggestions": personalized advice for the student
- "knowledge_points": list of relevant knowledge point tags
- "confidence": your confidence in this grading from 0.0 to 1.0

Return ONLY valid JSON, no markdown formatting."""

    async def grade_question(
        self,
        question_text: str,
        student_answer: str,
        mark_scheme: dict,
        subject_category: str = "stem_calculation",
    ) -> QuestionGrade:
        """Grade a single question using the LLM."""
        prompt = self._build_grading_prompt(
            question_text, student_answer, mark_scheme, subject_category
        )
        response_text = await self.raw_completion(prompt)

        import json
        try:
            data = json.loads(response_text)
        except json.JSONDecodeError:
            return QuestionGrade(
                question_number="",
                score=0,
                max_score=0,
                scoring_rationale="Failed to parse AI response",
                error_analysis="",
                error_type="none",
                model_solution="",
                improvement_suggestions="",
                confidence=0.0,
            )

        return QuestionGrade(
            question_number="",
            score=float(data.get("score", 0)),
            max_score=float(data.get("max_score", 0)),
            scoring_rationale=data.get("scoring_rationale", ""),
            error_analysis=data.get("error_analysis", ""),
            error_type=data.get("error_type", "none"),
            model_solution=data.get("model_solution", ""),
            improvement_suggestions=data.get("improvement_suggestions", ""),
            knowledge_points=data.get("knowledge_points", []),
            confidence=float(data.get("confidence", 0.0)),
        )

    async def grade_submission(
        self,
        questions: list[dict],
        mark_scheme: dict,
        subject_category: str = "stem_calculation",
    ) -> GradingOutput:
        """Grade all questions in a submission."""
        grades = []
        total_score = 0.0
        total_possible = 0.0

        for q in questions:
            grade = await self.grade_question(
                question_text=q["question_text"],
                student_answer=q["student_answer"],
                mark_scheme=mark_scheme,
                subject_category=subject_category,
            )
            grade.question_number = q.get("question_number", "")
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
            confidence=avg_confidence,
        )

    def _generate_overall_feedback(self, grades: list[QuestionGrade]) -> str:
        """Generate summary feedback from individual question grades."""
        if not grades:
            return "No questions were graded."

        total = sum(g.score for g in grades)
        possible = sum(g.max_score for g in grades)
        pct = (total / possible * 100) if possible > 0 else 0

        error_types = [g.error_type for g in grades if g.error_type != "none"]
        common_errors = {}
        for et in error_types:
            common_errors[et] = common_errors.get(et, 0) + 1

        feedback = f"Overall score: {total}/{possible} ({pct:.0f}%). "
        if common_errors:
            most_common = max(common_errors, key=common_errors.get)
            feedback += f"Most common error type: {most_common}. "
        feedback += "Review the per-question feedback for detailed improvement guidance."
        return feedback

    async def raw_completion(self, prompt: str) -> str:
        """Send a raw prompt to the LLM and return the text response."""
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
            )
            return response.choices[0].message.content
