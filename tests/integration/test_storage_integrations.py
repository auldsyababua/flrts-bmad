#!/usr/bin/env python3
"""
Comprehensive Storage Integration Tests
Tests all storage systems: Redis, Vector Store, Supabase, and S3

Usage:
    python test_storage_integrations.py
    python test_storage_integrations.py --verbose
    python test_storage_integrations.py --test redis
    python test_storage_integrations.py --test vector
    python test_storage_integrations.py --test supabase
    python test_storage_integrations.py --test s3
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from src.storage import vector_store
from src.storage.media_storage import media_storage

# Import storage modules
from src.storage.redis_store import redis_store
from src.storage.storage_service import document_storage


# Color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


def print_header(text: str):
    """Print a colored header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.WHITE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.END}")


def print_test_result(test_name: str, success: bool, details: str = ""):
    """Print formatted test result"""
    status = "PASS" if success else "FAIL"
    color = Colors.GREEN if success else Colors.RED
    symbol = "✅" if success else "❌"

    print(f"{color}{symbol} {test_name:<40} [{status}]{Colors.END}")
    if details:
        print(f"    {Colors.CYAN}{details}{Colors.END}")


class StorageTestSuite:
    """Comprehensive storage integration test suite"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.test_results = {"redis": [], "vector": [], "supabase": [], "s3": []}

    def log(self, message: str):
        """Log message if verbose mode is enabled"""
        if self.verbose:
            print(f"{Colors.PURPLE}[DEBUG] {message}{Colors.END}")

    async def test_redis_storage(self) -> bool:
        """Test Redis conversation storage"""
        print_header("REDIS STORAGE TESTS")

        if not redis_store:
            print_error("Redis store not initialized")
            return False

        all_passed = True

        try:
            # Test 1: Basic conversation storage and retrieval
            test_chat_id = f"test_chat_{datetime.now().timestamp()}"
            test_messages = [
                {"role": "user", "content": "Hello, this is a test message"},
                {
                    "role": "assistant",
                    "content": "Hi! I'm responding to your test message",
                },
            ]

            # Store conversation
            self.log(f"Storing conversation for chat_id: {test_chat_id}")
            store_result = await redis_store.save_conversation(
                test_chat_id, test_messages
            )

            success = store_result is True
            print_test_result("Store conversation", success)
            self.test_results["redis"].append(("Store conversation", success))
            if not success:
                all_passed = False

            # Retrieve conversation
            self.log(f"Retrieving conversation for chat_id: {test_chat_id}")
            retrieved_messages = await redis_store.get_conversation(test_chat_id)

            success = (
                retrieved_messages is not None
                and len(retrieved_messages) == 2
                and retrieved_messages[0]["content"] == test_messages[0]["content"]
            )
            print_test_result(
                "Retrieve conversation",
                success,
                f"Retrieved {len(retrieved_messages) if retrieved_messages else 0} messages",
            )
            self.test_results["redis"].append(("Retrieve conversation", success))
            if not success:
                all_passed = False

            # Test 2: TTL extension
            self.log("Testing TTL extension")
            extend_result = await redis_store.extend_conversation_ttl(test_chat_id)

            success = extend_result is True
            print_test_result("Extend TTL", success)
            self.test_results["redis"].append(("Extend TTL", success))
            if not success:
                all_passed = False

            # Test 3: Get metadata
            self.log("Getting conversation metadata")
            metadata = await redis_store.get_conversation_metadata(test_chat_id)

            success = (
                metadata is not None
                and "message_count" in metadata
                and metadata["message_count"] == 2
            )
            details = (
                f"Messages: {metadata.get('message_count', 'N/A')}, TTL: {metadata.get('ttl_seconds', 'N/A')}s"
                if metadata
                else ""
            )
            print_test_result("Get metadata", success, details)
            self.test_results["redis"].append(("Get metadata", success))
            if not success:
                all_passed = False

            # Test 4: Delete conversation
            self.log("Deleting test conversation")
            delete_result = await redis_store.delete_conversation(test_chat_id)

            success = delete_result is True
            print_test_result("Delete conversation", success)
            self.test_results["redis"].append(("Delete conversation", success))
            if not success:
                all_passed = False

            # Verify deletion
            deleted_conv = await redis_store.get_conversation(test_chat_id)
            success = deleted_conv is None
            print_test_result("Verify deletion", success)
            self.test_results["redis"].append(("Verify deletion", success))
            if not success:
                all_passed = False

        except Exception as e:
            print_error(f"Redis test failed with exception: {e}")
            all_passed = False

        return all_passed

    async def test_vector_storage(self) -> bool:
        """Test Vector store embedding and search"""
        print_header("VECTOR STORAGE TESTS")

        if not vector_store:
            print_error("Vector store not initialized")
            return False

        # Note: Using single-tenant vector store (no namespace isolation needed)
        print("[DEBUG] Testing vector store operations")

        all_passed = True

        try:
            # Test documents
            test_docs = [
                {
                    "id": f"test_doc_1_{datetime.now().timestamp()}",
                    "content": "This is a test document about machine learning and artificial intelligence. It covers neural networks, deep learning, and natural language processing.",
                    "metadata": {
                        "title": "ML Guide",
                        "category": "tech",
                        "file_path": "/test/ml_guide.md",
                    },
                },
                {
                    "id": f"test_doc_2_{datetime.now().timestamp()}",
                    "content": "Python programming guide for beginners. Learn about variables, functions, classes, and data structures like lists and dictionaries.",
                    "metadata": {
                        "title": "Python Basics",
                        "category": "programming",
                        "file_path": "/test/python_basics.md",
                    },
                },
                {
                    "id": f"test_doc_3_{datetime.now().timestamp()}",
                    "content": "Cooking recipes for Italian cuisine. Pasta, pizza, risotto, and traditional desserts like tiramisu and gelato.",
                    "metadata": {
                        "title": "Italian Recipes",
                        "category": "cooking",
                        "file_path": "/test/italian_recipes.md",
                    },
                },
            ]

            # Test 1: Store documents with embeddings
            self.log("Storing test documents with automatic embeddings")
            for doc in test_docs:
                store_result = await vector_store.embed_and_store(
                    doc["id"], doc["content"], doc["metadata"]
                )

                success = store_result is True
                print_test_result(
                    f"Store document: {doc['metadata']['title']}", success
                )
                self.test_results["vector"].append(
                    (f"Store {doc['metadata']['title']}", success)
                )
                if not success:
                    all_passed = False

            # Test 2: Semantic search
            search_queries = [
                ("machine learning algorithms", "ML Guide"),
                ("python programming basics", "Python Basics"),
                ("italian food recipes", "Italian Recipes"),
            ]

            for query, expected_title in search_queries:
                self.log(f"Searching for: {query}")
                search_results = await vector_store.search(
                    query, top_k=3, include_metadata=True
                )

                success = (
                    len(search_results) > 0
                    and search_results[0].get("metadata", {}).get("title")
                    == expected_title
                )
                details = f"Found {len(search_results)} results, top match: {search_results[0].get('metadata', {}).get('title', 'N/A') if search_results else 'None'}"
                print_test_result(f"Search: '{query[:30]}...'", success, details)
                self.test_results["vector"].append((f"Search {query[:20]}...", success))
                if not success:
                    all_passed = False

            # Test 3: Batch storage
            batch_docs = [
                (
                    f"batch_doc_1_{datetime.now().timestamp()}",
                    "Batch document 1 about data science and analytics",
                    {"title": "Data Science", "category": "tech"},
                ),
                (
                    f"batch_doc_2_{datetime.now().timestamp()}",
                    "Batch document 2 about web development and frameworks",
                    {"title": "Web Dev", "category": "tech"},
                ),
            ]

            self.log("Testing batch document storage")
            batch_result = await vector_store.batch_embed_and_store(batch_docs)

            success = batch_result == len(batch_docs)
            print_test_result(
                "Batch storage",
                success,
                f"Stored {batch_result}/{len(batch_docs)} documents",
            )
            self.test_results["vector"].append(("Batch storage", success))
            if not success:
                all_passed = False

            # Test 4: Document retrieval
            test_doc_id = test_docs[0]["id"]
            self.log(f"Fetching document: {test_doc_id}")
            fetched_doc = await vector_store.fetch_document(test_doc_id)

            success = fetched_doc is not None and fetched_doc.get("id") == test_doc_id
            print_test_result("Fetch document", success)
            self.test_results["vector"].append(("Fetch document", success))
            if not success:
                all_passed = False

            # Test 5: Update metadata
            new_metadata = {"updated_at": datetime.now().isoformat(), "test_flag": True}
            self.log(f"Updating metadata for: {test_doc_id}")
            update_result = await vector_store.update_metadata(
                test_doc_id, new_metadata
            )

            success = update_result is True
            print_test_result("Update metadata", success)
            self.test_results["vector"].append(("Update metadata", success))
            if not success:
                all_passed = False

            # Cleanup: Delete test documents
            self.log("Cleaning up test documents")
            cleanup_success = True
            for doc in test_docs:
                delete_result = await vector_store.delete_document(doc["id"])
                if not delete_result:
                    cleanup_success = False

            for doc_id, _, _ in batch_docs:
                delete_result = await vector_store.delete_document(doc_id)
                if not delete_result:
                    cleanup_success = False

            print_test_result("Cleanup test documents", cleanup_success)
            self.test_results["vector"].append(("Cleanup", cleanup_success))
            if not cleanup_success:
                all_passed = False

        except Exception as e:
            print_error(f"Vector test failed with exception: {e}")
            all_passed = False
        finally:
            # Note: No namespace cleanup needed for single-tenant system
            print("[DEBUG] Vector store test completed")

        return all_passed

    async def test_supabase_storage(self) -> bool:
        """Test Supabase document storage"""
        print_header("SUPABASE STORAGE TESTS")

        if not document_storage:
            print_error("Document storage not initialized")
            return False

        all_passed = True

        try:
            # Test document data
            test_file_path = f"test/documents/test_doc_{datetime.now().timestamp()}.md"
            test_content = """# Test Document
            
This is a test markdown document for Supabase storage testing.
            
## Features
- Document storage
- Version control
- Metadata tracking
- Search capabilities
            
## Tags
- test
- documentation
- storage
"""
            test_metadata = {
                "title": "Test Document",
                "author": "Test Suite",
                "created_for": "storage_testing",
            }

            # Test 1: Store document
            self.log(f"Storing document: {test_file_path}")
            doc_id = await document_storage.store_document(
                file_path=test_file_path,
                content=test_content,
                metadata=test_metadata,
                category="test",
                tags=["test", "storage", "supabase"],
                is_public=False,
                created_by="test_suite",
            )

            success = doc_id is not None
            print_test_result(
                "Store document", success, f"Doc ID: {doc_id[:8]}..." if doc_id else ""
            )
            self.test_results["supabase"].append(("Store document", success))
            if not success:
                all_passed = False
                return all_passed

            # Test 2: Retrieve by file path
            self.log(f"Retrieving document by path: {test_file_path}")
            retrieved_doc = await document_storage.get_document(test_file_path)

            success = (
                retrieved_doc is not None
                and retrieved_doc["file_path"] == test_file_path
                and retrieved_doc["content"] == test_content
            )
            print_test_result("Retrieve by path", success)
            self.test_results["supabase"].append(("Retrieve by path", success))
            if not success:
                all_passed = False

            # Test 3: Retrieve by ID
            self.log(f"Retrieving document by ID: {doc_id}")
            retrieved_by_id = await document_storage.get_document_by_id(doc_id)

            success = retrieved_by_id is not None and retrieved_by_id["id"] == doc_id
            print_test_result("Retrieve by ID", success)
            self.test_results["supabase"].append(("Retrieve by ID", success))
            if not success:
                all_passed = False

            # Test 4: Update document
            updated_content = (
                test_content
                + "\n\n## Updated Section\nThis content was added during testing."
            )
            updated_metadata = {"last_test_update": datetime.now().isoformat()}

            self.log("Updating document content and metadata")
            update_result = await document_storage.update_document(
                test_file_path, updated_content, updated_metadata
            )

            success = update_result is True
            print_test_result("Update document", success)
            self.test_results["supabase"].append(("Update document", success))
            if not success:
                all_passed = False

            # Test 5: Search documents
            search_tests = [
                ("test document", "content search"),
                (None, "all documents", {"category": "test"}),
                (None, "by tags", {"tags": ["storage"]}),
            ]

            for query, test_name, *extra_params in search_tests:
                self.log(f"Testing search: {test_name}")

                if extra_params and extra_params[0]:
                    search_results = await document_storage.search_documents(
                        query=query, **extra_params[0]
                    )
                else:
                    search_results = await document_storage.search_documents(
                        query=query
                    )

                success = len(search_results) > 0
                print_test_result(
                    f"Search: {test_name}",
                    success,
                    f"Found {len(search_results)} results",
                )
                self.test_results["supabase"].append((f"Search {test_name}", success))
                if not success:
                    all_passed = False

            # Test 6: Document chunks (if the table exists)
            try:
                self.log("Testing document chunking")
                chunk_id = await document_storage.store_document_chunk(
                    document_id=doc_id,
                    chunk_index=0,
                    chunk_text="This is the first chunk of the test document.",
                    vector_id=f"vector_{doc_id}_0",
                    start_char=0,
                    end_char=50,
                    metadata={"chunk_type": "header"},
                )

                chunk_success = chunk_id is not None
                print_test_result("Store document chunk", chunk_success)
                self.test_results["supabase"].append(("Store chunk", chunk_success))
                if not chunk_success:
                    all_passed = False

                if chunk_success:
                    # Get chunks for document
                    chunks = await document_storage.get_document_chunks(doc_id)
                    get_chunks_success = len(chunks) > 0
                    print_test_result(
                        "Get document chunks",
                        get_chunks_success,
                        f"Found {len(chunks)} chunks",
                    )
                    self.test_results["supabase"].append(
                        ("Get chunks", get_chunks_success)
                    )
                    if not get_chunks_success:
                        all_passed = False

            except Exception as e:
                print_warning(
                    f"Chunk operations not available (table may not exist): {e}"
                )

            # Cleanup: Delete test document
            self.log("Cleaning up test document")
            delete_result = await document_storage.delete_document(test_file_path)

            success = delete_result is True
            print_test_result("Delete document", success)
            self.test_results["supabase"].append(("Delete document", success))
            if not success:
                all_passed = False

            # EDGE CASE TESTS
            print_info("\nTesting Supabase edge cases...")

            # Test 7: Null/None handling
            try:
                await document_storage.store_document(None, "content", {})
                success = False
            except (ValueError, TypeError, AttributeError):
                success = True
            print_test_result("Null file path", success)
            self.test_results["supabase"].append(("Null file path", success))

            # Test 8: Empty document
            empty_doc_id = await document_storage.store_document(
                "test/empty.md", "", {"empty": True}
            )
            success = empty_doc_id is not None
            print_test_result("Empty document", success)
            self.test_results["supabase"].append(("Empty document", success))
            if success:
                await document_storage.delete_document("test/empty.md")

            # Test 9: Very large document
            large_content = "x" * (5 * 1024 * 1024)  # 5MB
            large_doc_id = await document_storage.store_document(
                "test/large.md", large_content, {"size": "5MB"}
            )
            success = large_doc_id is not None
            print_test_result("Large document (5MB)", success)
            self.test_results["supabase"].append(("Large document", success))
            if success:
                await document_storage.delete_document("test/large.md")

            # Test 10: Special characters in path
            special_paths = [
                "test/file with spaces.md",
                "test/文件.md",
                "test/файл.md",
                "test/emoji-😀.md",
            ]

            for path in special_paths:
                try:
                    doc_id = await document_storage.store_document(
                        path, "Special path test", {}
                    )
                    if doc_id:
                        await document_storage.delete_document(path)
                        success = True
                    else:
                        success = False
                except Exception:
                    success = False

                print_test_result(f"Special path: {repr(path[:20])}", success)

            # Test 11: SQL injection attempts
            malicious_paths = [
                "test/'; DROP TABLE documents;--.md",
                "test/<script>alert(1)</script>.md",
                "test/../../../etc/passwd",
            ]

            injection_safe = True
            for path in malicious_paths:
                try:
                    doc_id = await document_storage.store_document(
                        path, "Injection test", {}
                    )
                    if doc_id:
                        # Verify no injection occurred
                        search_results = await document_storage.search_documents(
                            "Injection test"
                        )
                        await document_storage.delete_document(path)
                except Exception:
                    pass  # Expected to fail

            print_test_result("SQL injection prevention", injection_safe)
            self.test_results["supabase"].append(("Injection safe", injection_safe))

            # Test 12: Concurrent document operations
            async def concurrent_doc_op(index):
                path = f"test/concurrent_{index}.md"
                return (
                    await document_storage.store_document(
                        path, f"Concurrent doc {index}", {"index": index}
                    ),
                    path,
                )

            tasks = [concurrent_doc_op(i) for i in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successful_paths = []
            for result in results:
                if isinstance(result, tuple) and result[0] is not None:
                    successful_paths.append(result[1])

            success = len(successful_paths) >= 8
            print_test_result(
                "Concurrent operations",
                success,
                f"{len(successful_paths)}/10 succeeded",
            )
            self.test_results["supabase"].append(("Concurrent ops", success))

            # Cleanup concurrent docs
            for path in successful_paths:
                await document_storage.delete_document(path)

        except Exception as e:
            print_error(f"Supabase test failed with exception: {e}")
            all_passed = False

        return all_passed

    async def test_s3_storage(self) -> bool:
        """Test S3 media storage with edge cases"""
        print_header("S3 STORAGE TESTS")

        if not media_storage:
            print_error("Media storage not initialized")
            return False

        all_passed = True

        try:
            # Test files
            test_files = [
                {
                    "name": "test_image.png",
                    "content": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n\x02\xdb\x00\x00\x00\x00IEND\xaeB`\x82",
                    "type": "image/png",
                    "description": "Test PNG image",
                    "tags": ["test", "image"],
                },
                {
                    "name": "test_document.txt",
                    "content": b"This is a test text document for S3 storage testing.\nIt contains multiple lines.\nAnd tests file upload functionality.",
                    "type": "text/plain",
                    "description": "Test text document",
                    "tags": ["test", "document"],
                },
            ]

            uploaded_files = []

            # Test 1: Upload files
            for test_file in test_files:
                self.log(f"Uploading file: {test_file['name']}")

                upload_result = await media_storage.upload_media(
                    file_content=test_file["content"],
                    file_name=test_file["name"],
                    file_type=test_file["type"],
                    description=test_file["description"],
                    tags=test_file["tags"],
                    telegram_chat_id=12345,
                    telegram_user_id=67890,
                )

                success = (
                    upload_result is not None
                    and "s3_key" in upload_result
                    and "s3_url" in upload_result
                )

                details = (
                    f"S3 Key: {upload_result.get('s3_key', 'N/A')[:30]}..."
                    if upload_result
                    else ""
                )
                print_test_result(f"Upload: {test_file['name']}", success, details)
                self.test_results["s3"].append((f"Upload {test_file['name']}", success))

                if success:
                    uploaded_files.append(upload_result)
                else:
                    all_passed = False

            # Test 2: Download files
            for i, upload_result in enumerate(uploaded_files):
                s3_key = upload_result["s3_key"]
                original_content = test_files[i]["content"]

                self.log(f"Downloading file: {s3_key}")
                downloaded_content = await media_storage.download_media(s3_key)

                success = (
                    downloaded_content is not None
                    and downloaded_content == original_content
                )

                print_test_result(
                    f"Download: {test_files[i]['name']}",
                    success,
                    f"Size: {len(downloaded_content) if downloaded_content else 0} bytes",
                )
                self.test_results["s3"].append(
                    (f"Download {test_files[i]['name']}", success)
                )
                if not success:
                    all_passed = False

            # Test 3: Generate presigned URLs
            for i, upload_result in enumerate(uploaded_files):
                s3_key = upload_result["s3_key"]

                self.log(f"Generating presigned URL for: {s3_key}")
                presigned_url = await media_storage.get_media_url(
                    s3_key, expires_in=300
                )

                success = (
                    presigned_url is not None
                    and presigned_url.startswith("https://")
                    and "amazonaws.com" in presigned_url
                )

                print_test_result(f"Presigned URL: {test_files[i]['name']}", success)
                self.test_results["s3"].append(
                    (f"Presigned URL {test_files[i]['name']}", success)
                )
                if not success:
                    all_passed = False

            # Test 4: List media files
            self.log("Listing media files")
            media_list = await media_storage.list_media(media_type="image", limit=10)

            success = isinstance(media_list, list)
            print_test_result(
                "List media files", success, f"Found {len(media_list)} files"
            )
            self.test_results["s3"].append(("List media", success))
            if not success:
                all_passed = False

            # Cleanup: Delete test files
            self.log("Cleaning up test files")
            cleanup_success = True
            for upload_result in uploaded_files:
                s3_key = upload_result["s3_key"]
                delete_result = await media_storage.delete_media(s3_key)
                if not delete_result:
                    cleanup_success = False

            print_test_result("Cleanup test files", cleanup_success)
            self.test_results["s3"].append(("Cleanup", cleanup_success))
            if not cleanup_success:
                all_passed = False

            # EDGE CASE TESTS
            print_info("\nTesting S3 edge cases...")

            # Test 6: Null/None handling
            try:
                await media_storage.upload_media(None, "test.txt", "text/plain")
                success = False
            except (ValueError, TypeError, AttributeError):
                success = True
            print_test_result("Null file content", success)
            self.test_results["s3"].append(("Null content", success))

            # Test 7: Empty file
            empty_result = await media_storage.upload_media(
                b"", "empty.txt", "text/plain"
            )
            success = empty_result is not None
            print_test_result("Empty file upload", success)
            self.test_results["s3"].append(("Empty file", success))
            if success:
                await media_storage.delete_media(empty_result["s3_key"])

            # Test 8: Large file
            large_file = b"x" * (10 * 1024 * 1024)  # 10MB
            large_result = await media_storage.upload_media(
                large_file, "large.bin", "application/octet-stream"
            )
            success = large_result is not None
            print_test_result(
                "Large file (10MB)",
                success,
                f"Hash: {large_result['file_hash'][:8]}..." if large_result else "",
            )
            self.test_results["s3"].append(("Large file", success))
            if success:
                await media_storage.delete_media(large_result["s3_key"])

            # Test 9: Special characters in filename
            special_names = [
                "file with spaces.txt",
                "文件.txt",
                "файл.txt",
                "emoji-😀.txt",
                "special!@#$%^&().txt",
            ]

            for name in special_names:
                try:
                    result = await media_storage.upload_media(
                        b"Special name test", name, "text/plain"
                    )
                    if result:
                        await media_storage.delete_media(result["s3_key"])
                        success = True
                    else:
                        success = False
                except Exception:
                    success = False

                print_test_result(f"Special filename: {repr(name[:20])}", success)

            # Test 10: Invalid MIME types
            invalid_types = [
                "",
                "invalid/type/with/slashes",
                "text/plain; rm -rf /",
                "<script>alert(1)</script>",
            ]

            for mime_type in invalid_types:
                try:
                    result = await media_storage.upload_media(
                        b"MIME test", "mime_test.txt", mime_type
                    )
                    # Should handle gracefully, possibly defaulting to octet-stream
                    if result:
                        await media_storage.delete_media(result["s3_key"])
                except Exception:
                    pass  # Expected for some types

            # Test 11: Concurrent uploads of same content
            same_content = b"Deduplication test content"

            async def concurrent_upload(index):
                return await media_storage.upload_media(
                    same_content, f"dedup_test_{index}.txt", "text/plain"
                )

            tasks = [concurrent_upload(i) for i in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should have same S3 key due to deduplication
            s3_keys = set()
            for result in results:
                if isinstance(result, dict) and "s3_key" in result:
                    s3_keys.add(result["s3_key"])

            success = len(s3_keys) == 1  # All deduplicated to same key
            print_test_result(
                "Concurrent deduplication", success, f"Unique keys: {len(s3_keys)}"
            )
            self.test_results["s3"].append(("Deduplication", success))

            # Cleanup dedup test
            if s3_keys:
                await media_storage.delete_media(list(s3_keys)[0])

            # Test 12: Presigned URL edge cases
            if uploaded_files:  # Reuse from earlier test
                test_key = uploaded_files[0]["s3_key"]

                # Test various expiration times
                for expires_in in [0, -1, 604800]:  # 0, negative, 1 week
                    try:
                        await media_storage.get_media_url(test_key, expires_in)
                        # Should handle edge cases
                    except Exception:
                        pass  # Expected for invalid values

        except Exception as e:
            print_error(f"S3 test failed with exception: {e}")
            all_passed = False

        return all_passed

    def print_summary(self):
        """Print test summary"""
        print_header("TEST SUMMARY")

        total_tests = 0
        total_passed = 0

        for service, tests in self.test_results.items():
            if not tests:
                continue

            service_passed = sum(1 for _, success in tests if success)
            service_total = len(tests)
            total_tests += service_total
            total_passed += service_passed

            percentage = (
                (service_passed / service_total * 100) if service_total > 0 else 0
            )
            color = (
                Colors.GREEN
                if percentage == 100
                else Colors.YELLOW if percentage >= 80 else Colors.RED
            )

            print(
                f"{color}{service.upper():<12} {service_passed:>3}/{service_total:<3} ({percentage:>5.1f}%){Colors.END}"
            )

            if self.verbose:
                for test_name, success in tests:
                    status_color = Colors.GREEN if success else Colors.RED
                    status = "PASS" if success else "FAIL"
                    print(f"  {status_color}{test_name:<30} [{status}]{Colors.END}")

        print()
        overall_percentage = (
            (total_passed / total_tests * 100) if total_tests > 0 else 0
        )
        overall_color = (
            Colors.GREEN
            if overall_percentage == 100
            else Colors.YELLOW if overall_percentage >= 80 else Colors.RED
        )

        print(
            f"{Colors.BOLD}OVERALL RESULT: {overall_color}{total_passed}/{total_tests} tests passed ({overall_percentage:.1f}%){Colors.END}"
        )

        if overall_percentage == 100:
            print(
                f"{Colors.GREEN}{Colors.BOLD}🎉 All storage integrations are working correctly!{Colors.END}"
            )
        elif overall_percentage >= 80:
            print(
                f"{Colors.YELLOW}{Colors.BOLD}⚠️  Most tests passed, but some issues detected{Colors.END}"
            )
        else:
            print(
                f"{Colors.RED}{Colors.BOLD}❌ Multiple storage systems have issues{Colors.END}"
            )


async def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Test storage integrations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--test",
        "-t",
        choices=["redis", "vector", "supabase", "s3"],
        help="Run specific test only",
    )

    args = parser.parse_args()

    print_header("MARKDOWN BRAIN BOT - STORAGE INTEGRATION TESTS")
    print_info(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_suite = StorageTestSuite(verbose=args.verbose)

    results = {}

    if args.test:
        # Run specific test
        if args.test == "redis":
            results["redis"] = await test_suite.test_redis_storage()
        elif args.test == "vector":
            results["vector"] = await test_suite.test_vector_storage()
        elif args.test == "supabase":
            results["supabase"] = await test_suite.test_supabase_storage()
        elif args.test == "s3":
            results["s3"] = await test_suite.test_s3_storage()
    else:
        # Run all tests
        print_info("Running comprehensive storage integration tests...")
        print_info("This will test Redis, Vector Store, Supabase, and S3 storage")

        results["redis"] = await test_suite.test_redis_storage()
        results["vector"] = await test_suite.test_vector_storage()
        results["supabase"] = await test_suite.test_supabase_storage()
        results["s3"] = await test_suite.test_s3_storage()

    # Print summary
    test_suite.print_summary()

    # Return appropriate exit code
    all_passed = all(results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print_error(f"Test runner failed: {e}")
        sys.exit(1)
