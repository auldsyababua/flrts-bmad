"""
Document chunking utilities for splitting large documents into smaller,
overlapping chunks suitable for vector embeddings.

Based on LangChain's RecursiveCharacterTextSplitter pattern.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class ChunkMetadata:
    """Metadata for a document chunk."""

    file_path: str
    chunk_index: int
    total_chunks: int
    start_char: int
    end_char: int
    title: Optional[str] = None
    type: Optional[str] = None


class DocumentChunker:
    """Splits documents into overlapping chunks for vector storage."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: Optional[List[str]] = None,
        keep_separator: bool = True,
    ):
        """
        Initialize the document chunker.

        Args:
            chunk_size: Target size for each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            separators: List of separators to use for splitting (in order of preference)
            keep_separator: Whether to keep separators in the chunks
        """
        if chunk_size <= 0:
            raise ValueError("Chunk size must be a positive integer.")
        if chunk_overlap >= chunk_size:
            raise ValueError("Chunk overlap must be smaller than chunk size.")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.keep_separator = keep_separator

        # Default separators optimized for markdown
        self.separators = separators or [
            "\n## ",  # H2 headers
            "\n### ",  # H3 headers
            "\n#### ",  # H4 headers
            "\n\n",  # Paragraphs
            "\n",  # Lines
            ". ",  # Sentences
            ", ",  # Clauses
            " ",  # Words
            "",  # Characters
        ]

    def chunk_document(self, content: str, metadata: Dict) -> List[Tuple[str, Dict]]:
        """
        Split document into overlapping chunks.

        Args:
            content: The document content to chunk
            metadata: Base metadata for the document

        Returns:
            List of (chunk_text, chunk_metadata) tuples
        """
        # Split the content into chunks
        chunks = self._split_text(content)

        # Create metadata for each chunk
        result = []
        char_offset = 0

        for i, chunk_text in enumerate(chunks):
            # Find the actual position in the original content
            start_pos = content.find(chunk_text, char_offset)
            if start_pos == -1:
                # Fallback if exact match not found (shouldn't happen)
                start_pos = char_offset

            end_pos = start_pos + len(chunk_text)

            # Create chunk metadata
            chunk_meta = {
                **metadata,  # Include all base metadata
                "chunk_index": i,
                "total_chunks": len(chunks),
                "start_char": start_pos,
                "end_char": end_pos,
                "chunk_id": f"{metadata.get('file_path', 'unknown')}#chunk_{i}",
            }

            result.append((chunk_text, chunk_meta))

            # Update offset for next search (accounting for overlap)
            char_offset = max(start_pos + 1, end_pos - self.chunk_overlap)

        return result

    def _split_text(self, text: str) -> List[str]:
        """
        Recursively split text using the configured separators.

        Args:
            text: Text to split

        Returns:
            List of text chunks
        """
        # Start with the whole text
        splits = [text]

        # Try each separator in order
        for separator in self.separators:
            if not separator:  # Empty separator means split by character
                splits = self._split_by_character(splits)
                break

            # Check if we need to split further
            temp_splits = []
            for split in splits:
                if len(split) <= self.chunk_size:
                    temp_splits.append(split)
                else:
                    # Split by this separator
                    new_splits = self._split_by_separator(split, separator)
                    temp_splits.extend(new_splits)

            splits = temp_splits

            # Check if all chunks are now small enough
            if all(len(s) <= self.chunk_size for s in splits):
                break

        # Merge small chunks and add overlap
        final_chunks = self._merge_and_overlap(splits)

        return final_chunks

    def _split_by_separator(self, text: str, separator: str) -> List[str]:
        """
        Split text by a specific separator.

        Args:
            text: Text to split
            separator: Separator to use

        Returns:
            List of splits
        """
        if not separator:
            return [text]

        # Use regex to split while optionally keeping the separator
        if self.keep_separator:
            # Split but keep separator with the following text
            parts = text.split(separator)
            splits: list[str] = []
            for i, part in enumerate(parts):
                if i > 0 and splits:
                    # Add separator to the beginning of this part
                    splits.append(separator + part)
                else:
                    splits.append(part)
            return [s for s in splits if s]  # Remove empty strings
        else:
            return [s for s in text.split(separator) if s]

    def _split_by_character(self, texts: List[str]) -> List[str]:
        """
        Split texts by character count as a last resort.

        Args:
            texts: List of texts to split

        Returns:
            List of character-split chunks
        """
        result = []
        for text in texts:
            if len(text) <= self.chunk_size:
                result.append(text)
            else:
                # Split into chunk_size pieces
                for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                    chunk = text[i : i + self.chunk_size]
                    if chunk:
                        result.append(chunk)
        return result

    def _merge_and_overlap(self, splits: List[str]) -> List[str]:
        """
        Merge small splits and add overlap between chunks.

        Args:
            splits: List of text splits

        Returns:
            List of final chunks with overlap
        """
        if not splits:
            return []

        final_chunks = []
        current_chunk = ""

        for split in splits:
            # Check if adding this split would exceed chunk size
            if current_chunk and len(current_chunk) + len(split) > self.chunk_size:
                # Save current chunk
                final_chunks.append(current_chunk)

                # Start new chunk with overlap from previous
                if self.chunk_overlap > 0 and len(current_chunk) > self.chunk_overlap:
                    # Take the last chunk_overlap characters as the start of the new chunk
                    overlap_text = current_chunk[-self.chunk_overlap :]
                    current_chunk = overlap_text + split
                else:
                    current_chunk = split
            else:
                # Add to current chunk
                current_chunk += split

        # Don't forget the last chunk
        if current_chunk:
            final_chunks.append(current_chunk)

        return final_chunks


def chunk_markdown_document(
    content: str,
    file_path: str,
    metadata: Optional[Dict] = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Tuple[str, Dict]]:
    """
    Convenience function to chunk a markdown document.

    Args:
        content: Markdown content to chunk
        file_path: Path to the source file
        metadata: Additional metadata to include
        chunk_size: Target chunk size
        chunk_overlap: Overlap between chunks

    Returns:
        List of (chunk_text, chunk_metadata) tuples
    """
    chunker = DocumentChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    base_metadata = {"file_path": file_path, **(metadata or {})}

    return chunker.chunk_document(content, base_metadata)
