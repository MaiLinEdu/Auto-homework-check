"""OCR engine abstraction layer.

Supports multiple backends: Google Cloud Vision, Mathpix, PaddleOCR.
Each backend returns a unified OCRResult structure.
"""

from dataclasses import dataclass, field


@dataclass
class OCRTextBlock:
    """A single recognized text block with position and confidence."""
    text: str
    confidence: float
    bounding_box: list[dict[str, int]]  # [{"x": ..., "y": ...}, ...]
    block_type: str = "text"  # text, formula, diagram_label


@dataclass
class OCRResult:
    """Unified OCR output from any backend."""
    full_text: str
    blocks: list[OCRTextBlock] = field(default_factory=list)
    language: str = "en"
    page_number: int = 1


class BaseOCREngine:
    """Abstract base for OCR engines."""

    async def recognize(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError


class GoogleVisionOCR(BaseOCREngine):
    """Google Cloud Vision API backend."""

    def __init__(self, credentials_path: str = ""):
        self.credentials_path = credentials_path

    async def recognize(self, image_bytes: bytes) -> OCRResult:
        from google.cloud import vision

        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=image_bytes)
        response = client.document_text_detection(image=image)

        blocks = []
        if response.full_text_annotation:
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        text = "".join(
                            "".join(s.text for s in word.symbols)
                            for word in paragraph.words
                        )
                        vertices = [
                            {"x": v.x, "y": v.y}
                            for v in paragraph.bounding_box.vertices
                        ]
                        confidence = paragraph.confidence
                        blocks.append(
                            OCRTextBlock(
                                text=text,
                                confidence=confidence,
                                bounding_box=vertices,
                            )
                        )

        full_text = response.full_text_annotation.text if response.full_text_annotation else ""
        return OCRResult(full_text=full_text, blocks=blocks)


class MathpixOCR(BaseOCREngine):
    """Mathpix API backend — optimized for math formulas."""

    def __init__(self, app_id: str, app_key: str):
        self.app_id = app_id
        self.app_key = app_key

    async def recognize(self, image_bytes: bytes) -> OCRResult:
        import base64
        import httpx

        encoded = base64.b64encode(image_bytes).decode()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.mathpix.com/v3/text",
                headers={
                    "app_id": self.app_id,
                    "app_key": self.app_key,
                    "Content-type": "application/json",
                },
                json={
                    "src": f"data:image/png;base64,{encoded}",
                    "formats": ["text", "latex_styled"],
                    "data_options": {"include_asciimath": True},
                },
            )
            data = response.json()

        full_text = data.get("text", "")
        latex = data.get("latex_styled", "")
        blocks = [
            OCRTextBlock(
                text=latex or full_text,
                confidence=data.get("confidence", 0.0),
                bounding_box=[],
                block_type="formula" if latex else "text",
            )
        ]
        return OCRResult(full_text=full_text, blocks=blocks)


def get_ocr_engine(engine_type: str = "google") -> BaseOCREngine:
    """Factory function to get the appropriate OCR engine."""
    from app.core.config import settings

    if engine_type == "mathpix":
        return MathpixOCR(
            app_id=settings.MATHPIX_APP_ID,
            app_key=settings.MATHPIX_APP_KEY,
        )
    # Default to Google Vision
    return GoogleVisionOCR(credentials_path=settings.GOOGLE_CLOUD_VISION_CREDENTIALS)
