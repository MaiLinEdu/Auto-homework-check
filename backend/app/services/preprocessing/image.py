"""Image preprocessing pipeline: orientation, perspective, denoising, enhancement."""

import cv2
import numpy as np


class ImagePreprocessor:
    """Preprocessing pipeline for assignment images before OCR."""

    def process(self, image_bytes: bytes) -> bytes:
        """Run the full preprocessing pipeline and return processed image bytes."""
        img = self._decode(image_bytes)
        img = self._correct_orientation(img)
        img = self._correct_perspective(img)
        img = self._enhance_contrast(img)
        img = self._denoise(img)
        img = self._binarize(img)
        return self._encode(img)

    def _decode(self, image_bytes: bytes) -> np.ndarray:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")
        return img

    def _encode(self, img: np.ndarray) -> bytes:
        _, buffer = cv2.imencode(".png", img)
        return buffer.tobytes()

    def _correct_orientation(self, img: np.ndarray) -> np.ndarray:
        """Detect and correct image orientation using edge analysis."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 100, minLineLength=100, maxLineGap=10)

        if lines is None:
            return img

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            if abs(angle) < 45:
                angles.append(angle)

        if not angles:
            return img

        median_angle = np.median(angles)
        if abs(median_angle) < 0.5:
            return img

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
        return cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    def _correct_perspective(self, img: np.ndarray) -> np.ndarray:
        """Attempt perspective correction by detecting document edges."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 75, 200)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

        if len(approx) != 4:
            return img

        # Order points: top-left, top-right, bottom-right, bottom-left
        pts = approx.reshape(4, 2).astype(np.float32)
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1)
        ordered = np.array([
            pts[np.argmin(s)],
            pts[np.argmin(d)],
            pts[np.argmax(s)],
            pts[np.argmax(d)],
        ], dtype=np.float32)

        w = max(
            np.linalg.norm(ordered[0] - ordered[1]),
            np.linalg.norm(ordered[2] - ordered[3]),
        )
        h = max(
            np.linalg.norm(ordered[0] - ordered[3]),
            np.linalg.norm(ordered[1] - ordered[2]),
        )
        dst = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(ordered, dst)
        return cv2.warpPerspective(img, matrix, (int(w), int(h)))

    def _enhance_contrast(self, img: np.ndarray) -> np.ndarray:
        """Adaptive contrast enhancement using CLAHE."""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l = clahe.apply(l)
        return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)

    def _denoise(self, img: np.ndarray) -> np.ndarray:
        """Non-local means denoising."""
        return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)

    def _binarize(self, img: np.ndarray) -> np.ndarray:
        """Adaptive binarization for cleaner OCR input."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        # Convert back to 3-channel for consistency
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
