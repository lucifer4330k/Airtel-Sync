"""OCR for KYC documents: OpenCV preprocessing + RapidOCR (ONNX, runs offline).

Preprocessing:
  1. Decode bytes (PNG/JPEG; PDFs are rasterised by the caller if supported).
  2. Upscale small phone photos so text is ~30px high.
  3. Remove coloured watermarks/stamps: keep only near-black ink by
     thresholding the brightest channel (pink "SPECIMEN" overlays vanish,
     black and dark-blue text stays).
  4. OCR; if text boxes are tilted (a photo), rotate by their median angle
     and read again.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np

log = logging.getLogger(__name__)
INK_THRESHOLD = 150  # max(R,G,B) below this counts as ink
BLUR_THRESHOLD = 100.0  # variance of Laplacian; the specimen set is ~930+ when sharp


@dataclass(frozen=True)
class Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2


@lru_cache
def _engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def sharpness(data: bytes) -> float | None:
    """Variance of the Laplacian: low means blurred. None if not an image."""
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    return None if img is None else float(cv2.Laplacian(img, cv2.CV_64F).var())


def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=(255, 255, 255))


def _text_angle(result) -> float:
    """Median slope of OCR text boxes (degrees). Robust to borders and photos."""
    angles = []
    for box, text, _ in result or []:
        (x0, y0), (x1, y1) = box[0], box[1]
        if len(text) >= 6 and x1 - x0 > 40:
            angles.append(np.degrees(np.arctan2(y1 - y0, x1 - x0)))
    return float(np.median(angles)) if angles else 0.0


def preprocess(data: bytes) -> np.ndarray | None:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    if w < 1000:
        scale = 1000 / w
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    brightest = img.max(axis=2)
    bw = np.where(brightest < INK_THRESHOLD, 0, 255).astype(np.uint8)
    return cv2.cvtColor(bw, cv2.COLOR_GRAY2BGR)


def read_lines(data: bytes) -> list[Line]:
    img = preprocess(data)
    if img is None:
        return []
    result, _ = _engine()(img)
    angle = _text_angle(result)
    if abs(angle) > 1.0:  # photographed at a tilt: straighten and read again
        result, _ = _engine()(_rotate(img, angle))
    lines = []
    for box, text, score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        lines.append(Line(text.strip(), min(xs), min(ys), max(xs), max(ys), float(score)))
    return sorted(lines, key=lambda ln: (round(ln.yc / 12), ln.x0))
