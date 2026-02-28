"""Async tasks for submission processing: Preprocess -> OCR -> Segment -> Validate."""

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assignment import AssignmentSubmission
from app.services.ocr.engine import OCRResult, get_ocr_engine
from app.services.preprocessing.image import ImagePreprocessor
from app.services.preprocessing.separator import ContentSeparator, SeparationResult
from app.services.storage import StorageService
from app.worker import celery_app

logger = logging.getLogger(__name__)

sync_engine = create_engine(settings.database_url_sync, pool_pre_ping=True)

# ── Confidence thresholds ──────────────────────────────────────────────────────
OCR_CONFIDENCE_THRESHOLD = 0.70
SEGMENTATION_MIN_QUESTIONS = 1


def _run_async(coro):
    """Run an async coroutine from synchronous Celery worker context."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _update_status(db: Session, submission: AssignmentSubmission, status: str):
    """Persist a status change and flush immediately."""
    submission.status = status
    submission.updated_at = datetime.now(timezone.utc)
    db.commit()


# ── Main processing task ───────────────────────────────────────────────────────
@celery_app.task(
    bind=True,
    name="processing.process_submission",
    queue="ocr",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_submission_task(self, submission_id: str):
    """Full processing pipeline for one submission.

    Lifecycle:
        uploaded -> processing -> ocr_complete -> (ready for grading | requires_manual_review | error)

    Steps:
        1. Download files from S3
        2. Image preprocessing (orientation, perspective, denoise, binarise)
        3. OCR extraction via pluggable engine
        4. Confidence gating — flag if OCR quality is poor
        5. Smart segmentation (pattern -> LLM fallback)
        6. Validate segmentation output
    """
    with Session(sync_engine) as db:
        submission = db.execute(
            select(AssignmentSubmission).where(AssignmentSubmission.id == submission_id)
        ).scalar_one_or_none()

        if not submission:
            logger.error("Submission %s not found", submission_id)
            return {"error": "Submission not found"}

        # ── 1. Mark as processing ──────────────────────────────────────────
        _update_status(db, submission, "processing")
        logger.info("Processing submission %s — starting pipeline", submission_id)

        try:
            storage = StorageService()
            preprocessor = ImagePreprocessor()
            ocr_engine = get_ocr_engine()

            # ── 2. Download + Preprocess + OCR each page ───────────────────
            page_results: list[dict] = []
            all_text_parts: list[str] = []
            all_confidences: list[float] = []

            if submission.file_urls:
                for filename, storage_key in submission.file_urls.items():
                    page = _process_single_page(
                        storage, preprocessor, ocr_engine, filename, storage_key
                    )
                    page_results.append(page)
                    all_text_parts.append(page["text"])
                    all_confidences.extend(page["block_confidences"])

            # Append any direct text input
            if submission.raw_text:
                all_text_parts.append(submission.raw_text)

            full_text = "\n\n".join(all_text_parts)

            # ── 3. Compute aggregate OCR confidence ────────────────────────
            avg_ocr_confidence = (
                sum(all_confidences) / len(all_confidences)
                if all_confidences
                else 1.0  # no images → text-only, full confidence
            )

            low_confidence_blocks = [c for c in all_confidences if c < OCR_CONFIDENCE_THRESHOLD]

            ocr_metadata = {
                "pages": page_results,
                "full_text": full_text,
                "avg_confidence": round(avg_ocr_confidence, 4),
                "total_blocks": len(all_confidences),
                "low_confidence_blocks": len(low_confidence_blocks),
            }
            submission.ocr_result = ocr_metadata
            _update_status(db, submission, "ocr_complete")

            # ── 4. Confidence gate: flag if OCR is unreliable ──────────────
            if avg_ocr_confidence < OCR_CONFIDENCE_THRESHOLD:
                logger.warning(
                    "Submission %s: OCR confidence %.2f below threshold %.2f — flagging for review",
                    submission_id, avg_ocr_confidence, OCR_CONFIDENCE_THRESHOLD,
                )
                submission.separated_content = {
                    "error": "ocr_low_confidence",
                    "avg_confidence": round(avg_ocr_confidence, 4),
                    "items": [],
                }
                _update_status(db, submission, "requires_manual_review")
                return {
                    "status": "requires_manual_review",
                    "reason": "ocr_low_confidence",
                    "avg_confidence": avg_ocr_confidence,
                }

            # ── 5. Smart segmentation ──────────────────────────────────────
            separator = ContentSeparator()
            separation: SeparationResult = _run_async(separator.separate(full_text))

            # ── 6. Validate segmentation ───────────────────────────────────
            if len(separation.items) < SEGMENTATION_MIN_QUESTIONS:
                logger.warning(
                    "Submission %s: segmentation found %d questions (min %d) — flagging",
                    submission_id, len(separation.items), SEGMENTATION_MIN_QUESTIONS,
                )
                submission.separated_content = {
                    "error": "segmentation_failed",
                    "method": separation.method,
                    "raw_text": full_text[:2000],
                    "items": [],
                }
                _update_status(db, submission, "requires_manual_review")
                return {
                    "status": "requires_manual_review",
                    "reason": "segmentation_failed",
                    "questions_found": 0,
                }

            # Check per-question segmentation confidence
            low_seg_items = [
                it for it in separation.items if it.confidence < OCR_CONFIDENCE_THRESHOLD
            ]

            submission.separated_content = {
                "method": separation.method,
                "questions_found": len(separation.items),
                "low_confidence_questions": len(low_seg_items),
                "items": [
                    {
                        "question_number": item.question_number,
                        "question_text": item.question_text,
                        "student_answer": item.student_answer,
                        "confidence": round(item.confidence, 4),
                    }
                    for item in separation.items
                ],
            }

            # If many questions have low segmentation confidence, flag for review
            # but still keep the data (teacher can correct rather than redo)
            if low_seg_items and len(low_seg_items) > len(separation.items) / 2:
                _update_status(db, submission, "requires_manual_review")
                return {
                    "status": "requires_manual_review",
                    "reason": "low_segmentation_confidence",
                    "questions_found": len(separation.items),
                    "low_confidence_count": len(low_seg_items),
                }

            # ── Success ────────────────────────────────────────────────────
            _update_status(db, submission, "ocr_complete")
            logger.info(
                "Submission %s processed: %d questions found via %s",
                submission_id, len(separation.items), separation.method,
            )
            return {
                "status": "success",
                "questions_found": len(separation.items),
                "method": separation.method,
                "avg_ocr_confidence": round(avg_ocr_confidence, 4),
            }

        except Exception as exc:
            logger.exception("Submission %s: pipeline failed — %s", submission_id, exc)
            # Persist partial state so nothing is lost
            if submission.status != "requires_manual_review":
                submission.status = "error"
                submission.separated_content = submission.separated_content or {}
                submission.separated_content["pipeline_error"] = str(exc)[:500]
                db.commit()
            raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


# ── Single-page processing helper ─────────────────────────────────────────────
def _process_single_page(
    storage: StorageService,
    preprocessor: ImagePreprocessor,
    ocr_engine,
    filename: str,
    storage_key: str,
) -> dict:
    """Download, preprocess, and OCR a single page. Returns structured result."""
    # Download
    url = storage.get_presigned_url(storage_key)
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    image_bytes = response.content

    # Preprocess
    processed_bytes = preprocessor.process(image_bytes)

    # OCR
    ocr_result: OCRResult = _run_async(ocr_engine.recognize(processed_bytes))

    block_confidences = [b.confidence for b in ocr_result.blocks if b.confidence > 0]

    return {
        "filename": filename,
        "text": ocr_result.full_text,
        "block_count": len(ocr_result.blocks),
        "block_confidences": block_confidences,
        "avg_confidence": (
            round(sum(block_confidences) / len(block_confidences), 4)
            if block_confidences
            else 0.0
        ),
        "blocks": [
            {
                "text": b.text,
                "confidence": round(b.confidence, 4),
                "type": b.block_type,
                "bbox": b.bounding_box,
            }
            for b in ocr_result.blocks
        ],
    }
