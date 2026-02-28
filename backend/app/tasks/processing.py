"""Async tasks for submission processing: OCR + content separation."""

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.core.config import settings
from app.models.assignment import AssignmentSubmission
from app.services.ocr.engine import get_ocr_engine
from app.services.preprocessing.image import ImagePreprocessor
from app.services.preprocessing.separator import ContentSeparator
from app.services.storage import StorageService
from app.worker import celery_app

sync_engine = create_engine(settings.database_url_sync)


@celery_app.task(bind=True, max_retries=3)
def process_submission_task(self, submission_id: str):
    """Process a submission: download files -> preprocess -> OCR -> separate."""
    with Session(sync_engine) as db:
        submission = db.execute(
            select(AssignmentSubmission).where(
                AssignmentSubmission.id == submission_id
            )
        ).scalar_one_or_none()

        if not submission:
            return {"error": "Submission not found"}

        submission.status = "processing"
        db.commit()

        try:
            storage = StorageService()
            preprocessor = ImagePreprocessor()
            ocr_engine = get_ocr_engine()
            separator = ContentSeparator()

            all_text = ""
            ocr_results = []

            # Process each uploaded file
            if submission.file_urls:
                for filename, key in submission.file_urls.items():
                    # Download from storage
                    url = storage.get_presigned_url(key)
                    import httpx
                    response = httpx.get(url)
                    image_bytes = response.content

                    # Preprocess
                    processed = preprocessor.process(image_bytes)

                    # OCR
                    result = asyncio.get_event_loop().run_until_complete(
                        ocr_engine.recognize(processed)
                    )
                    all_text += result.full_text + "\n"
                    ocr_results.append({
                        "file": filename,
                        "text": result.full_text,
                        "blocks": [
                            {
                                "text": b.text,
                                "confidence": b.confidence,
                                "type": b.block_type,
                            }
                            for b in result.blocks
                        ],
                    })

            # If raw text was submitted directly
            if submission.raw_text:
                all_text += submission.raw_text

            # Separate questions from answers
            separation = asyncio.get_event_loop().run_until_complete(
                separator.separate(all_text)
            )

            submission.ocr_result = {"pages": ocr_results, "full_text": all_text}
            submission.separated_content = {
                "method": separation.method,
                "items": [
                    {
                        "question_number": item.question_number,
                        "question_text": item.question_text,
                        "student_answer": item.student_answer,
                        "confidence": item.confidence,
                    }
                    for item in separation.items
                ],
            }
            submission.status = "submitted"
            db.commit()

            return {"status": "success", "questions_found": len(separation.items)}

        except Exception as exc:
            submission.status = "submitted"
            db.commit()
            raise self.retry(exc=exc, countdown=30)
