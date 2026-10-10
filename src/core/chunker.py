"""
Heading-aware sliding-window chunker.

Handles Markdown (heading split) and generic text (paragraph split).
Code blocks are preserved intact during chunking.
"""
import re
from typing import List
from collections import deque

from langchain_core.documents import Document
from config.settings import settings
import structlog

log = structlog.get_logger()

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
CODEBLOCK_PATTERN = re.compile(r"```[\s\S]*?```")


def _restore_code(text: str, blocks: List[str]) -> str:
    for i, block in enumerate(blocks):
        text = text.replace(f"\x00CB{i}\x00", block)
    return text


def _split_by_headings(content: str) -> List[dict]:
    sections = []
    matches = list(HEADING_PATTERN.finditer(content))

    if not matches:
        return [{"level": 0, "heading": "", "content": content}]

    # Content before first heading
    if matches[0].start() > 0:
        sections.append({
            "level": 0,
            "heading": "",
            "content": content[: matches[0].start()],
        })

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append({
            "level": len(m.group(1)),
            "heading": m.group(2).strip(),
            "content": content[start:end],
        })

    return sections


class Chunker:
    def __init__(
            self,
            chunk_size: int = settings.chunk_size,
            chunk_overlap: int = settings.chunk_overlap,
            min_chunk_length: int = settings.min_chunk_length,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_length = min_chunk_length

    def chunk_documents(self, documents: List[Document]) -> List[Document]:
        """Chunk a list of raw documents into smaller overlapping chunks."""
        all_chunks: List[Document] = []
        for doc in documents:
            file_type = doc.metadata.get("file_type", "txt")
            if file_type in ("md", "markdown"):
                chunks = self._chunk_markdown(doc)
            else:
                chunks = self._chunk_generic(doc)
            all_chunks.extend(chunks)

        log.info("chunking_complete", total_chunks=len(all_chunks))
        return all_chunks

    # ── Markdown-specific ────────────────────────────────────────────────────

    def _chunk_markdown(self, doc: Document) -> List[Document]:
        content = doc.page_content
        base_meta = doc.metadata.copy()
        sections = _split_by_headings(content)
        result: List[Document] = []
        heading_stack: deque = deque()

        for sec in sections:
            self._update_heading_stack(heading_stack, sec["level"], sec["heading"])
            hierarchy = " > ".join(heading_stack)
            raw_chunks = self._sliding_window_chunk(sec["content"])

            for i, chunk_text in enumerate(raw_chunks):
                if len(chunk_text.strip()) < self.min_chunk_length:
                    continue
                meta = {
                    **base_meta,
                    "heading": sec["heading"],
                    "heading_level": sec["level"],
                    "headings_hierarchy": hierarchy,
                    "chunk_index": i,
                    "total_chunks": len(raw_chunks),
                }
                result.append(Document(page_content=chunk_text, metadata=meta))

        return result

    # ── Generic text (txt, pdf, docx) ────────────────────────────────────────

    def _chunk_generic(self, doc: Document) -> List[Document]:
        content = doc.page_content
        base_meta = doc.metadata.copy()
        raw_chunks = self._sliding_window_chunk(content)
        result = []
        for i, chunk_text in enumerate(raw_chunks):
            if len(chunk_text.strip()) < self.min_chunk_length:
                continue
            meta = {
                **base_meta,
                "heading": base_meta.get("heading", ""),
                "heading_level": 0,
                "headings_hierarchy": "",
                "chunk_index": i,
                "total_chunks": len(raw_chunks),
            }
            result.append(Document(page_content=chunk_text, metadata=meta))
        return result

    # ── Sliding window ───────────────────────────────────────────────────────

    def _sliding_window_chunk(self, text: str) -> List[str]:
        """Split text into overlapping chunks, preserving code blocks."""
        code_blocks: List[str] = []

        def stash_code(m: re.Match) -> str:
            code_blocks.append(m.group())
            return f"\x00CB{len(code_blocks) - 1}\x00"

        processed = CODEBLOCK_PATTERN.sub(stash_code, text)
        paragraphs = processed.split("\n\n")

        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)
            if current_len + para_len > self.chunk_size and current:
                chunk = "\n\n".join(current)
                chunks.append(_restore_code(chunk, code_blocks))
                # Overlap: keep last portion
                overlap_text = chunk[-self.chunk_overlap:] if len(chunk) > self.chunk_overlap else chunk
                current = [overlap_text, para]
                current_len = len(overlap_text) + para_len
            else:
                current.append(para)
                current_len += para_len

        if current:
            chunk = "\n\n".join(current)
            chunks.append(_restore_code(chunk, code_blocks))

        return chunks

    @staticmethod
    def _update_heading_stack(stack: deque, level: int, heading: str) -> None:
        while len(stack) >= level > 0:
            stack.pop()
        if heading:
            stack.append(heading)


# Module-level singleton
chunker = Chunker()