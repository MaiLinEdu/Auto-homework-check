"""Intelligent content separator: distinguishes questions from student answers."""

import re
from dataclasses import dataclass, field


@dataclass
class SeparatedItem:
    """A paired question-answer unit."""
    question_number: str
    question_text: str
    student_answer: str
    confidence: float = 1.0


@dataclass
class SeparationResult:
    """Result of the question/answer separation process."""
    items: list[SeparatedItem] = field(default_factory=list)
    raw_text: str = ""
    method: str = "pattern"  # pattern, layout, llm


class ContentSeparator:
    """Separates question prompts from student answers in OCR text.

    Uses a multi-strategy approach:
    1. Pattern-based: regex to detect question numbers and segment text.
    2. Layout-based: uses OCR bounding boxes to identify regions.
    3. LLM-based: falls back to LLM for ambiguous content.
    """

    # Common question number patterns across IB/A-Level/AP
    QUESTION_PATTERNS = [
        r"(?:Question|Q)\s*(\d+)",
        r"^(\d+)\.\s",
        r"^\(([a-z])\)\s",
        r"^\(([ivxlc]+)\)\s",
        r"^([a-z])\)\s",
        r"^(\d+)\s*\([a-z]\)",
    ]

    def separate_by_pattern(self, text: str) -> SeparationResult:
        """Use regex patterns to detect question boundaries and split text."""
        combined_pattern = "|".join(f"({p})" for p in self.QUESTION_PATTERNS)
        lines = text.split("\n")

        items: list[SeparatedItem] = []
        current_q_num = ""
        current_q_text = ""
        current_answer_lines: list[str] = []
        in_answer = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            match = re.match(combined_pattern, stripped, re.IGNORECASE | re.MULTILINE)
            if match:
                # Save previous question-answer pair
                if current_q_num:
                    items.append(SeparatedItem(
                        question_number=current_q_num,
                        question_text=current_q_text,
                        student_answer="\n".join(current_answer_lines).strip(),
                    ))

                # Extract the matched question number
                groups = [g for g in match.groups() if g is not None]
                current_q_num = groups[0] if groups else stripped[:10]
                current_q_text = stripped
                current_answer_lines = []
                in_answer = False
            else:
                # Heuristic: if the line looks like printed text (question continuation)
                # vs handwritten answer — for now, accumulate as answer after first question line
                if current_q_num and not in_answer:
                    # First non-question line after question number => start of answer
                    in_answer = True
                if in_answer:
                    current_answer_lines.append(stripped)
                elif current_q_num:
                    current_q_text += " " + stripped

        # Save last pair
        if current_q_num:
            items.append(SeparatedItem(
                question_number=current_q_num,
                question_text=current_q_text,
                student_answer="\n".join(current_answer_lines).strip(),
            ))

        return SeparationResult(items=items, raw_text=text, method="pattern")

    async def separate_by_llm(self, text: str) -> SeparationResult:
        """Use an LLM to intelligently separate questions and answers.

        This is the fallback for complex or ambiguous content.
        """
        from app.services.ai.grader import AIGrader

        grader = AIGrader()
        prompt = (
            "You are an expert at analyzing educational documents. "
            "The following text was extracted via OCR from a student's assignment. "
            "Identify each question and the student's corresponding answer. "
            "Return a JSON array where each element has: "
            '"question_number", "question_text", "student_answer".\n\n'
            f"OCR Text:\n{text}"
        )
        response = await grader.raw_completion(prompt)

        import json
        try:
            parsed = json.loads(response)
            items = [
                SeparatedItem(
                    question_number=str(item.get("question_number", "")),
                    question_text=item.get("question_text", ""),
                    student_answer=item.get("student_answer", ""),
                    confidence=0.8,
                )
                for item in parsed
            ]
        except (json.JSONDecodeError, TypeError):
            items = []

        return SeparationResult(items=items, raw_text=text, method="llm")

    async def separate(self, text: str) -> SeparationResult:
        """Run separation with automatic fallback.

        Tries pattern-based first; if confidence is low, falls back to LLM.
        """
        result = self.separate_by_pattern(text)
        if result.items:
            return result
        # Fallback to LLM-based separation
        return await self.separate_by_llm(text)
