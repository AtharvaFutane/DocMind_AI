import io
from typing import BinaryIO
import pypdf
import docx


class DocumentParser:
    """Extracts raw text content from uploaded files (PDF, DOCX, TXT)."""

    @staticmethod
    def parse_pdf(file: io.BytesIO) -> str:
        """Extract text from a PDF file using pypdf."""
        reader = pypdf.PdfReader(file)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)

    @staticmethod
    def parse_docx(file: io.BytesIO) -> str:
        """Extract text from a DOCX file using python-docx."""
        doc = docx.Document(file)
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        return "\n\n".join(text_parts)

    @staticmethod
    def parse_txt(file: io.BytesIO) -> str:
        """Extract text from a plaintext file, decoding as UTF-8."""
        return file.getvalue().decode("utf-8", errors="ignore")

    @classmethod
    def parse(cls, filename: str, content: bytes) -> str:
        """Parse file content based on filename extension."""
        ext = filename.split(".")[-1].lower()
        file_like = io.BytesIO(content)

        if ext == "pdf":
            return cls.parse_pdf(file_like)
        elif ext == "docx":
            return cls.parse_docx(file_like)
        elif ext in ("txt", "md"):
            return cls.parse_txt(file_like)
        else:
            raise ValueError(f"Unsupported file format: {ext}")
