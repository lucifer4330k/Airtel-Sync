"""Upload safety: type is decided by the file's bytes, never its name or the
browser-declared Content-Type."""

from dataclasses import dataclass

MAX_BYTES = 5 * 1024 * 1024

# magic bytes -> (mime type, extension, label shown to the owner)
_SIGNATURES: list[tuple[bytes, str, str, str]] = [
    (b"\xff\xd8\xff", "image/jpeg", "jpg", "JPEG image"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png", "PNG image"),
    (b"%PDF-", "application/pdf", "pdf", "PDF"),
]


@dataclass(frozen=True)
class SniffedFile:
    mime: str
    ext: str
    label: str


def sniff(data: bytes) -> SniffedFile | None:
    for magic, mime, ext, label in _SIGNATURES:
        if data.startswith(magic):
            return SniffedFile(mime, ext, label)
    return None


def human_size(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.1f} MB"
