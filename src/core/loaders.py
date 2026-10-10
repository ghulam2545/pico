"""
Format-aware document loaders.

Supports: .md, .markdown, .txt, .pdf, .docx
All return List[Document] with page_content and metadata.
"""
from pathlib import Path
from typing import List, Tuple
import io
import pymupdf
import structlog

from langchain_core.documents import Document

log = structlog.get_logger()

SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf", ".docx"}


def detect_file_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".md": "md",
        ".markdown": "md",
        ".txt": "txt",
        ".pdf": "pdf",
        ".docx": "docx",
    }
    return mapping.get(ext, "unknown")


def load_document(file_bytes: bytes, filename: str, base_metadata: dict) -> List[Document]:
    """
    Load raw bytes into LangChain Documents based on file type.
    base_metadata: dict with workspace_id, user_id, file_hash, file_type, etc.
    Returns raw unsplit documents (chunking is done separately).
    """
    file_type = detect_file_type(filename)

    if file_type == "unknown":
        raise ValueError(f"Unsupported file type for: {filename}")

    if file_type in ("md", "txt"):
        return _load_text(file_bytes, filename, file_type, base_metadata)
    elif file_type == "pdf":
        return _load_pdf(file_bytes, filename, base_metadata)
    # elif file_type == "docx":
    #     return _load_docx(file_bytes, filename, base_metadata)
    return []


def _load_text(file_bytes: bytes, filename: str, file_type: str, base_metadata: dict) -> List[Document]:
    """Load plain text / markdown files."""
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        text = file_bytes.decode("latin-1", errors="replace")

    meta = {**base_metadata, "filename": filename, "file_type": file_type, "page": 1, "total_pages": 1}
    return [Document(page_content=text, metadata=meta)]


def _load_pdf(file_bytes: bytes, filename: str, base_metadata: dict) -> List[Document]:
    """Load PDF page by page using PyMuPDF."""
    docs = []
    with pymupdf.open(stream=file_bytes, filetype="pdf") as pdf:
        total_pages = len(pdf)

    for page_num, page in enumerate(pdf, start=1):
        text = page.get_text("text")
        if text and text.strip():
            meta = {
                **base_metadata,
                "filename": filename,
                "file_type": "pdf",
                "page": page_num,
                "total_pages": total_pages,
            }
            docs.append(Document(page_content=text, metadata=meta))

    pdf.close()
    log.info("pdf_loaded", filename=filename, pages=total_pages, non_empty_pages=len(docs))
    return docs


# def _load_docx(file_bytes: bytes, filename: str, base_metadata: dict) -> List[Document]:
#     """Load DOCX by extracting paragraphs with section awareness."""
#     from docx import Document as DocxDocument
#
#     docx_file = io.BytesIO(file_bytes)
#     doc = DocxDocument(docx_file)
#
#     sections: List[Tuple[str, str]] = []
#     current_section: List[str] = []
#     current_heading = ""
#
#     for para in doc.paragraphs:
#         text = para.text.strip()
#         if not text:
#             continue
#
#         style_name = para.style.name if para.style else ""
#         is_heading = style_name.startswith("Heading")
#
#         if is_heading and current_section:
#             sections.append((current_heading, "\n".join(current_section)))
#             current_section = []
#             current_heading = text
#         elif is_heading:
#             current_heading = text
#         else:
#             current_section.append(text)
#
#     if current_section:
#         sections.append((current_heading, "\n".join(current_section)))
#
#     if not sections:
#         full_text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
#         meta = {**base_metadata, "filename": filename, "file_type": "docx", "page": 1, "total_pages": 1}
#         return [Document(page_content=full_text, metadata=meta)]
#
#     docs = []
#     for i, (heading, content) in enumerate(sections):
#         meta = {
#             **base_metadata,
#             "filename": filename,
#             "file_type": "docx",
#             "heading": heading,
#             "page": i + 1,
#             "total_pages": len(sections),
#         }
#         docs.append(Document(page_content=content, metadata=meta))
#
#     log.info("docx_loaded", filename=filename, sections=len(docs))
#     return docs