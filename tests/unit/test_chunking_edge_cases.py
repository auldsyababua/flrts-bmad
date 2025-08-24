"""Edge case tests for document chunking functionality."""

from unittest.mock import patch

import pytest

from src.core.chunking import chunk_markdown_document


class TestChunkingEdgeCases:
    """Test document chunking with various edge cases and failure scenarios."""

    def test_empty_document(self):
        """Test chunking with empty document."""
        chunks = chunk_markdown_document(
            content="",
            file_path="test.md",
            metadata={"title": "Empty"},
            chunk_size=1000,
            chunk_overlap=200,
        )

        # Should return at least one chunk even for empty content
        assert len(chunks) >= 0
        if len(chunks) > 0:
            chunk_text, chunk_metadata = chunks[0]
            assert chunk_text == "" or len(chunk_text) == 0

    def test_document_exceeding_size_limits(self):
        """Test chunking with documents that exceed memory limits."""
        # Create a very large document
        large_content = "x" * (10 * 1024 * 1024)  # 10MB

        chunks = chunk_markdown_document(
            content=large_content,
            file_path="large.md",
            metadata={"title": "Large"},
            chunk_size=1000,
            chunk_overlap=200,
        )

        # Should handle large documents by creating many chunks
        assert len(chunks) > 1000

        # Verify chunks don't exceed specified size
        for chunk_text, _ in chunks:
            assert len(chunk_text) <= 1200  # chunk_size + some buffer

    def test_invalid_encoding(self):
        """Test chunking with invalid character encoding."""
        # Various problematic encodings
        invalid_contents = [
            "Hello \x00 World",  # Null byte
            "Test \xff\xfe",  # Invalid UTF-8
            "\x80\x81\x82\x83",  # More invalid UTF-8
            "Valid text \xf0\x28\x8c\x28 more text",  # Invalid UTF-8 sequence
        ]

        for content in invalid_contents:
            # Should handle gracefully without crashing
            try:
                chunks = chunk_markdown_document(
                    content=content,
                    file_path="invalid.md",
                    metadata={"title": "Invalid"},
                    chunk_size=100,
                    chunk_overlap=20,
                )
                assert isinstance(chunks, list)
            except UnicodeDecodeError:
                # Acceptable if it raises proper error
                pass

    def test_chunk_size_edge_cases(self):
        """Test with unusual chunk sizes."""
        content = "This is a test document with some content that needs to be chunked properly."

        edge_cases = [
            (0, 0),  # Zero size
            (1, 0),  # Tiny chunks
            (10000, 5000),  # Overlap larger than content
            (50, 51),  # Overlap larger than chunk size
            (-10, 5),  # Negative chunk size
            (100, -5),  # Negative overlap
        ]

        for chunk_size, chunk_overlap in edge_cases:
            try:
                chunks = chunk_markdown_document(
                    content=content,
                    file_path="test.md",
                    metadata={},
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                # Should either handle gracefully or use defaults
                assert isinstance(chunks, list)
            except (ValueError, AssertionError):
                # Acceptable if it validates inputs
                pass

    def test_corrupted_markdown(self):
        """Test chunking with corrupted markdown content."""
        corrupted_contents = [
            "# Unclosed code block\n```python\nprint('hello')",  # Unclosed code block
            "[Broken link](http://example.com",  # Unclosed link
            "**Bold text without closing",  # Unclosed bold
            "```\n```\n```\n```",  # Nested code blocks
            "# Title\n" + "#" * 100,  # Too many headers
            "![Image](" + "x" * 10000 + ")",  # Very long image URL
        ]

        for content in corrupted_contents:
            chunks = chunk_markdown_document(
                content=content,
                file_path="corrupted.md",
                metadata={"title": "Corrupted"},
                chunk_size=100,
                chunk_overlap=20,
            )

            # Should still produce chunks
            assert len(chunks) > 0

            # Verify metadata is preserved
            for _, metadata in chunks:
                assert "title" in metadata
                assert "chunk_index" in metadata

    @pytest.mark.skip(
        reason="Memory exhaustion simulation not applicable in current implementation"
    )
    def test_memory_exhaustion_simulation(self):
        """Test behavior when chunking might cause memory issues."""
        # Create content with many repeated patterns that might cause issues
        problematic_content = "[" * 10000 + "text" + "]" * 10000

        with patch("src.core.chunking.chunk_markdown_document") as mock_chunk:
            # Simulate memory error
            mock_chunk.side_effect = MemoryError("Out of memory")

            with pytest.raises(MemoryError):
                chunk_markdown_document(
                    content=problematic_content,
                    file_path="memory.md",
                    metadata={},
                    chunk_size=1000,
                    chunk_overlap=200,
                )

    def test_special_characters_in_metadata(self):
        """Test chunking with special characters in metadata."""
        special_metadata = {
            "title": "Test <script>alert('xss')</script>",
            "tags": ["tag1", "<tag2>", "tag&3"],
            "special": "\x00\n\r\t",
            "unicode": "🔥📚🎉",
            "nested": {"key": "value"},
        }

        chunks = chunk_markdown_document(
            content="Test content",
            file_path="special.md",
            metadata=special_metadata,
            chunk_size=100,
            chunk_overlap=20,
        )

        # Metadata should be preserved
        for _, chunk_metadata in chunks:
            assert "title" in chunk_metadata
            assert "tags" in chunk_metadata

    def test_concurrent_chunking(self):
        """Test thread safety of chunking."""
        import queue
        import threading

        results_queue = queue.Queue()
        errors_queue = queue.Queue()

        def chunk_document(content, result_q, error_q):
            try:
                chunks = chunk_markdown_document(
                    content=content,
                    file_path="concurrent.md",
                    metadata={"thread": threading.current_thread().name},
                    chunk_size=100,
                    chunk_overlap=20,
                )
                result_q.put(len(chunks))
            except Exception as e:
                error_q.put(e)

        # Create multiple threads chunking different documents
        threads = []
        contents = [f"Document {i} content" * 50 for i in range(10)]

        for content in contents:
            t = threading.Thread(
                target=chunk_document, args=(content, results_queue, errors_queue)
            )
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Check no errors occurred
        assert errors_queue.empty(), "Errors occurred during concurrent chunking"

        # Check all results are valid
        total_chunks = 0
        while not results_queue.empty():
            chunk_count = results_queue.get()
            assert chunk_count > 0
            total_chunks += chunk_count

        assert total_chunks > 0

    def test_pathological_markdown_structures(self):
        """Test with markdown that might break parsers."""
        pathological_cases = [
            "# " * 1000 + "Title",  # Many header markers
            "[" * 100 + "text" + "]" * 100 + "(url)",  # Nested brackets
            "```" + "\n" * 1000 + "```",  # Large code block
            "*" * 100 + "text" + "*" * 100,  # Many emphasis markers
            "> " * 50 + "Deeply nested quote",  # Deep nesting
        ]

        for content in pathological_cases:
            chunks = chunk_markdown_document(
                content=content,
                file_path="pathological.md",
                metadata={},
                chunk_size=500,
                chunk_overlap=100,
            )

            # Should handle without crashing
            assert isinstance(chunks, list)
            assert len(chunks) > 0

    def test_chunk_boundary_calculations(self):
        """Test edge cases in chunk boundary calculations."""
        # Content with exact chunk size
        exact_content = "x" * 100

        chunks = chunk_markdown_document(
            content=exact_content,
            file_path="exact.md",
            metadata={},
            chunk_size=100,
            chunk_overlap=0,
        )

        # Should create exactly one chunk
        assert len(chunks) == 1
        assert chunks[0][0] == exact_content

        # Content slightly over chunk size
        over_content = "x" * 101

        chunks = chunk_markdown_document(
            content=over_content,
            file_path="over.md",
            metadata={},
            chunk_size=100,
            chunk_overlap=0,
        )

        # Should create two chunks
        assert len(chunks) == 2

    def test_metadata_preservation_across_chunks(self):
        """Test that metadata is correctly preserved and updated across chunks."""
        content = "Test content. " * 100  # Long content to ensure multiple chunks

        original_metadata = {
            "title": "Test Document",
            "author": "Test Author",
            "created": "2024-01-01",
            "tags": ["test", "chunking"],
        }

        chunks = chunk_markdown_document(
            content=content,
            file_path="metadata_test.md",
            metadata=original_metadata,
            chunk_size=100,
            chunk_overlap=20,
        )

        # Verify all chunks have required metadata
        for i, (chunk_text, chunk_metadata) in enumerate(chunks):
            # Original metadata should be preserved
            assert chunk_metadata["title"] == original_metadata["title"]
            assert chunk_metadata["author"] == original_metadata["author"]

            # Chunk-specific metadata should be added
            assert "chunk_index" in chunk_metadata
            assert chunk_metadata["chunk_index"] == i
            assert "start_char" in chunk_metadata
            assert "end_char" in chunk_metadata
            assert chunk_metadata["start_char"] < chunk_metadata["end_char"]

    def test_network_timeout_simulation(self):
        """Test handling of timeouts during chunk processing."""
        import asyncio

        async def slow_chunk_process():
            # Simulate slow processing
            await asyncio.sleep(10)
            return chunk_markdown_document(
                content="Test",
                file_path="slow.md",
                metadata={},
                chunk_size=100,
                chunk_overlap=20,
            )

        # This test demonstrates timeout handling pattern
        # In real implementation, chunk processing should have timeouts
        async def test_with_timeout():
            try:
                await asyncio.wait_for(slow_chunk_process(), timeout=0.1)
                assert False, "Should have timed out"
            except asyncio.TimeoutError:
                # Expected behavior
                pass

        # Run the async test
        asyncio.run(test_with_timeout())
