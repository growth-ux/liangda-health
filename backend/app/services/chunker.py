from dataclasses import dataclass
from uuid import uuid4

from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class TextChunk:
    chunk_id: str
    document_id: str
    page_no: int
    content: str


def chunk_page_text(
    document_id: str,
    page_no: int,
    text: str,
    chunk_size: int = 800,
    overlap: int = 100,
) -> list[TextChunk]:
    content = text.strip()
    if not content:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be lower than chunk_size")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=[
            "\n\n",
            "\n",
            "。 ",
            "。",
            "；",
            ";",
            "，",
            ",",
            " ",
            "",
        ],
        keep_separator=False,
    )

    chunks: list[TextChunk] = []
    for section in _split_structured_sections(content):
        for chunk_content in splitter.split_text(section):
            normalized = chunk_content.strip()
            if not normalized:
                continue
            chunks.append(
                TextChunk(
                    chunk_id=f"chunk_{uuid4().hex}",
                    document_id=document_id,
                    page_no=page_no,
                    content=normalized,
                )
            )
    return chunks


def _split_structured_sections(text: str) -> list[str]:
    sections = [section.strip() for section in text.split("\n\n")]
    return [section for section in sections if section]
