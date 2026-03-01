"""Intelligent content separator: distinguishes questions from student answers.

Strategy hierarchy:
    1. Pattern-based (regex): Fast, high-confidence for well-structured docs.
    2. Layout/visual markers: Uses vertical whitespace gaps and indentation shifts.
    3. LLM semantic fallback: For messy or ambiguous OCR output.

Each strategy returns a confidence score per separated item. The pipeline
picks the best strategy automatically.
"""

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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
    method: str = "pattern"  # pattern, visual, llm


# ── Regex patterns covering IB / A-Level / AP formatting ─────────────────────
# Each tuple: (compiled regex, group index that holds the question number)
_QUESTION_PATTERNS = [
    # "Question 1", "Q1", "Q.1", "Question 1(a)"
    (re.compile(r"^(?:Question|Q)\.?\s*(\d+(?:\s*\([a-z]\))?)", re.IGNORECASE), 1),
    # "1." or "12." at line start
    (re.compile(r"^(\d{1,3})\.\s"), 1),
    # "(a)" "(b)" "(i)" "(ii)" — sub-questions
    (re.compile(r"^\(([a-z]|[ivxlc]{1,4})\)\s", re.IGNORECASE), 1),
    # "a)" "b)" — common A-Level style
    (re.compile(r"^([a-z])\)\s"), 1),
    # "1(a)" compound format
    (re.compile(r"^(\d{1,3})\s*\([a-z]\)"), 1),
    # "Part A", "Part 1" — AP free-response style
    (re.compile(r"^Part\s+([A-Z]|\d+)", re.IGNORECASE), 1),
]

# Lines that look like question continuations (printed) rather than answers
_QUESTION_CONTINUATION_HINTS = re.compile(
    r"\b(?:calculate|determine|explain|evaluate|state|describe|discuss|"
    r"outline|suggest|justify|compare|contrast|analyse|analyze|define|"
    r"find|show\s+that|prove|sketch|draw|consider|given\s+that|"
    r"the\s+(?:diagram|graph|table|figure)\s+(?:below|above|shows?))\b",
    re.IGNORECASE,
)


class ContentSeparator:
    """Separates question prompts from student answers in OCR text."""

    # ── Strategy 1: Pattern-based ────────────────────────────────────────────
    def separate_by_pattern(self, text: str) -> SeparationResult:
        """Regex-based segmentation using question number markers."""
        lines = text.split("\n")

        # First pass: find all question-start line indices
        q_starts: list[tuple[int, str]] = []  # (line_index, question_number)
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue
            for pattern, group_idx in _QUESTION_PATTERNS:
                m = pattern.match(stripped)
                if m:
                    q_num = m.group(group_idx)
                    q_starts.append((idx, q_num))
                    break

        if not q_starts:
            return SeparationResult(items=[], raw_text=text, method="pattern")

        # Second pass: for each question block, split into question_text vs answer
        items: list[SeparatedItem] = []
        for i, (start_idx, q_num) in enumerate(q_starts):
            end_idx = q_starts[i + 1][0] if i + 1 < len(q_starts) else len(lines)
            block_lines = lines[start_idx:end_idx]

            q_text_lines: list[str] = []
            answer_lines: list[str] = []
            transitioned_to_answer = False

            for j, bline in enumerate(block_lines):
                stripped = bline.strip()
                if not stripped:
                    # Blank line after question text -> likely transition to answer
                    if q_text_lines and not transitioned_to_answer:
                        transitioned_to_answer = True
                    continue

                if not transitioned_to_answer:
                    # Still in question territory if line has question keywords
                    if j == 0 or _QUESTION_CONTINUATION_HINTS.search(stripped):
                        q_text_lines.append(stripped)
                    else:
                        # No keyword -> assume answer started
                        transitioned_to_answer = True
                        answer_lines.append(stripped)
                else:
                    answer_lines.append(stripped)

            items.append(SeparatedItem(
                question_number=q_num,
                question_text=" ".join(q_text_lines),
                student_answer="\n".join(answer_lines),
                confidence=0.95 if answer_lines else 0.6,
            ))

        return SeparationResult(items=items, raw_text=text, method="pattern")

    # ── Strategy 2: Visual/layout-based ──────────────────────────────────────
    def separate_by_visual_markers(self, text: str) -> SeparationResult:
        """Use vertical whitespace gaps and indentation shifts to find blocks.

        Heuristic: large gaps (2+ blank lines) between sections suggest
        question boundaries. Indented blocks are more likely to be answers.
        """
        lines = text.split("\n")
        blocks: list[list[str]] = []
        current_block: list[str] = []

        for line in lines:
            if line.strip() == "":
                if current_block:
                    current_block.append("")
            else:
                # Count trailing blank lines
                trailing_blanks = 0
                for prev in reversed(current_block):
                    if prev == "":
                        trailing_blanks += 1
                    else:
                        break

                if trailing_blanks >= 2 and current_block:
                    # Strip trailing blanks and save block
                    while current_block and current_block[-1] == "":
                        current_block.pop()
                    blocks.append(current_block)
                    current_block = []

                current_block.append(line)

        if current_block:
            while current_block and current_block[-1] == "":
                current_block.pop()
            if current_block:
                blocks.append(current_block)

        if len(blocks) < 2:
            return SeparationResult(items=[], raw_text=text, method="visual")

        # Try to pair blocks: check if block starts with a question pattern
        items: list[SeparatedItem] = []
        for idx, block in enumerate(blocks):
            first_line = block[0].strip() if block else ""
            is_question = any(p.match(first_line) for p, _ in _QUESTION_PATTERNS)

            if is_question:
                q_lines = []
                a_lines = []
                past_q = False
                for bline in block:
                    s = bline.strip()
                    if not past_q and (
                        not s
                        or _QUESTION_CONTINUATION_HINTS.search(s)
                        or bline == block[0]
                    ):
                        q_lines.append(s)
                    else:
                        past_q = True
                        a_lines.append(s)

                # If no answer found in same block, grab next block
                if not a_lines and idx + 1 < len(blocks):
                    a_lines = [ln.strip() for ln in blocks[idx + 1]]

                m = None
                for p, gi in _QUESTION_PATTERNS:
                    m = p.match(first_line)
                    if m:
                        break
                q_num = m.group(gi) if m else str(len(items) + 1)

                items.append(SeparatedItem(
                    question_number=q_num,
                    question_text=" ".join(ln for ln in q_lines if ln),
                    student_answer="\n".join(a_lines),
                    confidence=0.75,
                ))

        return SeparationResult(items=items, raw_text=text, method="visual")

    # ── Strategy 3: LLM semantic fallback ────────────────────────────────────
    async def separate_by_llm(self, text: str) -> SeparationResult:
        """Use an LLM to intelligently separate questions and answers.

        This is the most expensive but most robust strategy. Used only when
        pattern and visual strategies both fail.
        """
        from app.services.ai.grader import AIGrader

        grader = AIGrader()
        prompt = f"""You are an expert at analyzing educational documents from international curricula (IB, A-Level, AP).

The following text was extracted via OCR from a student's assignment sheet.
Your task is to identify each question and the student's corresponding answer.

Rules:
- A "question" is the printed/typed prompt set by the teacher or exam board.
- An "answer" is the student's handwritten or typed response.
- If you cannot distinguish question from answer for a block, include the entire text as student_answer and leave question_text empty.
- Assign sequential question_numbers if not explicitly labeled.
- For each item, rate your confidence from 0.0 to 1.0.

Return a JSON array where each element has:
  "question_number" (string), "question_text" (string), "student_answer" (string), "confidence" (float)

Return ONLY valid JSON. No markdown. No explanation.

--- OCR TEXT ---
{text[:8000]}"""

        try:
            response = await grader.raw_completion(prompt)
            # Strip markdown code fences if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            items = [
                SeparatedItem(
                    question_number=str(item.get("question_number", str(idx + 1))),
                    question_text=item.get("question_text", ""),
                    student_answer=item.get("student_answer", ""),
                    confidence=min(float(item.get("confidence", 0.7)), 1.0),
                )
                for idx, item in enumerate(parsed)
                if isinstance(item, dict)
            ]
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("LLM separation JSON parse failed: %s", e)
            items = []

        return SeparationResult(items=items, raw_text=text, method="llm")

    # ── Orchestrator ─────────────────────────────────────────────────────────
    async def separate(self, text: str) -> SeparationResult:
        """Run separation with automatic strategy escalation.

        1. Try pattern-based (fast, high confidence).
        2. If <1 question found, try visual/layout markers.
        3. If still <1 question found, fall back to LLM.
        """
        if not text or not text.strip():
            return SeparationResult(items=[], raw_text=text, method="none")

        # Strategy 1: Pattern
        result = self.separate_by_pattern(text)
        if result.items:
            logger.info("Pattern separation: %d questions found", len(result.items))
            return result

        # Strategy 2: Visual markers
        result = self.separate_by_visual_markers(text)
        if result.items:
            logger.info("Visual separation: %d questions found", len(result.items))
            return result

        # Strategy 3: LLM fallback
        logger.info("Falling back to LLM separation")
        return await self.separate_by_llm(text)
