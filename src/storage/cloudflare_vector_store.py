"""
Cloudflare Vectorize implementation for semantic search.
Handles document embedding, storage, and retrieval using Cloudflare's vector database.
"""

import hashlib
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

from core.benchmarks import async_benchmark, get_performance_monitor

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class CloudflareVectorStore:
    """Handles semantic search using Cloudflare Vectorize."""

    def __init__(self):
        """Initialize Cloudflare Vectorize client from environment variables."""
        self.account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
        self.api_token = os.getenv("CLOUDFLARE_API_TOKEN")
        self.index_name = os.getenv("CLOUDFLARE_VECTORIZE_INDEX", "flrts-vectors")
        self.top_k = int(os.getenv("VECTOR_TOP_K", "5"))

        if not self.account_id or not self.api_token:
            raise ValueError("Cloudflare credentials not configured")

        # API endpoints
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/vectorize/indexes"
        self.index_url = f"{self.base_url}/{self.index_name}"

        # HTTP client with auth headers
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        # Cache configuration (will use Cloudflare KV in Story 1.3)
        self.cache_enabled = os.getenv("VECTOR_CACHE_ENABLED", "true").lower() == "true"
        self.cache_ttl = int(os.getenv("VECTOR_CACHE_TTL", "300"))  # 5 minutes default

    def ping(self) -> bool:
        """Test connection to Cloudflare Vectorize."""
        try:
            # Make a simple API call to check connectivity
            response = httpx.get(self.index_url, headers=self.headers, timeout=5.0)
            return response.status_code in [
                200,
                404,
            ]  # 404 is ok, means API is reachable
        except Exception:
            return False

        # Initialize performance monitor
        self.monitor = None

        # OpenAI client for embeddings (Cloudflare Vectorize requires pre-computed embeddings)
        self._init_openai()

    def _init_openai(self):
        """Initialize OpenAI client for generating embeddings."""
        import openai

        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = openai.OpenAI()
        self.embedding_model = os.getenv(
            "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
        )

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector using OpenAI."""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model, input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def _get_cache_key(
        self, query: str, top_k: int, filter: Optional[str] = None
    ) -> str:
        """Generate a cache key for a query."""
        key_parts = [query, str(top_k), filter or ""]
        key_string = "|".join(key_parts)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"vector_cache:{key_hash}"

    async def _ensure_monitor(self):
        """Ensure performance monitor is initialized."""
        if self.monitor is None:
            self.monitor = get_performance_monitor()

    async def invalidate_cache(self, pattern: Optional[str] = None):
        """Invalidate cache entries (placeholder for Cloudflare KV implementation)."""
        # Will be implemented with Cloudflare KV in Story 1.3
        pass

    async def embed_and_store(
        self,
        document_id: str,
        content: str,
        metadata: Optional[Dict] = None,
        namespace: Optional[str] = None,
    ) -> bool:
        """
        Store a document with embedding generation via OpenAI and storage in Cloudflare.

        Args:
            document_id: Unique identifier for the document
            content: Text content to embed and store
            metadata: Optional metadata to attach to the document
            namespace: Optional namespace for user isolation

        Returns:
            True if stored successfully, False otherwise
        """
        try:
            logger.info(
                f"📝 Storing document {document_id} in namespace: {namespace or 'default'}"
            )

            # Generate embedding
            embedding = await self._generate_embedding(content)

            # Prepare metadata
            if metadata is None:
                metadata: Dict[str, Any] = {}

            # Add timestamp and content preview
            metadata.update(
                {
                    "indexed_at": datetime.now().isoformat(),
                    "content_preview": (
                        content[:1500] + "..." if len(content) > 1500 else content
                    ),
                    "content_length": len(content),
                }
            )

            # Add namespace to metadata if provided
            if namespace:
                metadata["namespace"] = namespace

            # Prepare vector data for Cloudflare
            vector_data = {
                "vectors": [
                    {"id": document_id, "values": embedding, "metadata": metadata}
                ]
            }

            # Upsert to Cloudflare Vectorize
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.index_url}/upsert", headers=self.headers, json=vector_data
                )
                response.raise_for_status()

            # Invalidate cache after storing new document
            await self.invalidate_cache()

            logger.info(f"✅ Document {document_id} stored successfully")
            return True

        except Exception as e:
            logger.error(f"Error storing document {document_id}: {e}")
            return False

    @async_benchmark("vector_search")
    async def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter: Optional[str] = None,
        include_metadata: bool = True,
        namespace: Optional[str] = None,
    ) -> List[Dict]:
        """
        Search for documents using semantic similarity.

        Args:
            query: Natural language query text
            top_k: Number of results to return
            filter: Optional metadata filter (JSON string)
            include_metadata: Whether to include metadata in results
            namespace: Optional namespace for user isolation

        Returns:
            List of matching documents with scores and metadata
        """
        start_time = time.perf_counter()

        try:
            # Ensure monitor is initialized
            await self._ensure_monitor()

            # Use configured top_k if not specified
            if top_k is None:
                top_k = self.top_k

            logger.info(
                f"🔍 Searching in namespace: {namespace or 'default'} for query: {query[:50]}..."
            )

            # Generate query embedding
            query_embedding = await self._generate_embedding(query)

            # Prepare search request
            search_data = {
                "vector": query_embedding,
                "topK": top_k,
                "returnValues": False,
                "returnMetadata": include_metadata,
            }

            # Add filter if provided
            if filter:
                search_data["filter"] = (
                    json.loads(filter) if isinstance(filter, str) else filter
                )

            # Add namespace filter if provided
            if namespace:
                namespace_filter = {"namespace": {"$eq": namespace}}
                if "filter" in search_data:
                    search_data["filter"] = {
                        "$and": [search_data["filter"], namespace_filter]
                    }
                else:
                    search_data["filter"] = namespace_filter

            # Query Cloudflare Vectorize
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.index_url}/query", headers=self.headers, json=search_data
                )
                response.raise_for_status()
                results = response.json().get("result", {}).get("matches", [])

            logger.info(
                f"🔍 Found {len(results)} results in namespace: {namespace or 'default'}"
            )

            # Format results
            formatted_results = []
            for result in results:
                content = None
                if result.get("metadata"):
                    content = result["metadata"].get("content_preview", "")

                formatted_result = {
                    "id": result["id"],
                    "score": result["score"],
                    "content": content,
                    "metadata": result.get("metadata") if include_metadata else None,
                }
                formatted_results.append(formatted_result)

            # Track performance
            duration = time.perf_counter() - start_time
            if self.monitor:
                await self.monitor.track_vector_search(
                    query=query,
                    results_count=len(formatted_results),
                    duration=duration,
                    cache_hit=False,
                )

            return formatted_results

        except Exception as e:
            logger.error(f"Error searching for query '{query}': {e}")
            return []

    async def delete_document(
        self, document_id: str, namespace: Optional[str] = None
    ) -> bool:
        """
        Delete a document from the vector store.

        Args:
            document_id: Document ID to delete
            namespace: Optional namespace

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Prepare delete request
            delete_data = {"ids": [document_id]}

            # Delete from Cloudflare Vectorize
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.index_url}/delete", headers=self.headers, json=delete_data
                )
                response.raise_for_status()

            # Invalidate cache after deletion
            await self.invalidate_cache()

            logger.info(f"✅ Document {document_id} deleted successfully")
            return True

        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            return False

    async def batch_embed_and_store(
        self,
        documents: List[Tuple[str, str, Optional[Dict]]],
        namespace: Optional[str] = None,
    ) -> int:
        """
        Store multiple documents in batch for efficiency.

        Args:
            documents: List of tuples (document_id, content, metadata)
            namespace: Optional namespace for all documents

        Returns:
            Number of documents successfully stored
        """
        try:
            vectors = []

            for doc_id, content, metadata in documents:
                # Generate embedding for each document
                embedding = await self._generate_embedding(content)

                if metadata is None:
                    metadata: Dict[str, Any] = {}

                # Add standard metadata
                metadata.update(
                    {
                        "indexed_at": datetime.now().isoformat(),
                        "content_preview": (
                            content[:200] + "..." if len(content) > 200 else content
                        ),
                        "content_length": len(content),
                    }
                )

                # Add namespace if provided
                if namespace:
                    metadata["namespace"] = namespace

                vectors.append(
                    {"id": doc_id, "values": embedding, "metadata": metadata}
                )

            # Batch upsert to Cloudflare
            batch_data = {"vectors": vectors}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.index_url}/upsert", headers=self.headers, json=batch_data
                )
                response.raise_for_status()

            # Invalidate cache after batch update
            await self.invalidate_cache()

            logger.info(f"✅ Batch stored {len(vectors)} documents successfully")
            return len(vectors)

        except Exception as e:
            logger.error(f"Error in batch storage: {e}")
            return 0

    async def fetch_document(self, document_id: str) -> Optional[Dict]:
        """
        Fetch a specific document by ID.

        Args:
            document_id: Document ID to fetch

        Returns:
            Document data or None if not found
        """
        try:
            # Fetch from Cloudflare Vectorize
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.index_url}/vectors/{document_id}", headers=self.headers
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                result = response.json().get("result")

                if result:
                    return {
                        "id": document_id,
                        "content": None,  # Content not stored in vector DB
                        "metadata": result.get("metadata", {}),
                    }

            return None

        except Exception as e:
            logger.error(f"Error fetching document {document_id}: {e}")
            return None

    async def update_metadata(
        self, document_id: str, metadata: Dict, mode: str = "overwrite"
    ) -> bool:
        """
        Update metadata for a document.

        Args:
            document_id: Document ID to update
            metadata: New metadata to apply
            mode: "overwrite" (replace all) or "patch" (merge)

        Returns:
            True if updated successfully
        """
        try:
            # Fetch existing document if patch mode
            if mode == "patch":
                existing = await self.fetch_document(document_id)
                if not existing:
                    logger.error(
                        f"Document {document_id} not found for metadata update"
                    )
                    return False

                # Merge metadata
                existing_metadata = existing.get("metadata", {})
                metadata = {**existing_metadata, **metadata}

            # Update metadata in Cloudflare
            update_data = {"vectors": [{"id": document_id, "metadata": metadata}]}

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.index_url}/upsert", headers=self.headers, json=update_data
                )
                response.raise_for_status()

            await self.invalidate_cache()
            return True

        except Exception as e:
            logger.error(f"Error updating metadata for {document_id}: {e}")
            return False

    async def list_documents(
        self, prefix: Optional[str] = None, limit: int = 100
    ) -> List[str]:
        """
        List document IDs in the vector store.
        Note: This requires a metadata search or separate tracking.

        Args:
            prefix: Optional prefix to filter document IDs
            limit: Maximum number of IDs to return

        Returns:
            List of document IDs
        """
        # Cloudflare Vectorize doesn't have a direct list operation
        # Would need to implement via metadata search or separate index
        logger.warning("list_documents not fully implemented for Cloudflare Vectorize")
        return []

    async def reset_store(self) -> bool:
        """
        Reset (clear) all documents in the vector store.
        WARNING: This will delete all vectors in the index.

        Returns:
            True if reset successfully, False otherwise
        """
        try:
            # Delete the index and recreate it
            async with httpx.AsyncClient() as client:
                # Delete index
                response = await client.delete(self.index_url, headers=self.headers)

                if response.status_code not in [200, 404]:
                    response.raise_for_status()

                # Recreate index
                create_data = {
                    "name": self.index_name,
                    "config": {
                        "dimensions": 1536,  # Default for text-embedding-3-small
                        "metric": "cosine",
                    },
                }

                response = await client.post(
                    self.base_url, headers=self.headers, json=create_data
                )

                if response.status_code != 409:  # 409 = already exists
                    response.raise_for_status()

            logger.info("✅ Vector store reset successfully")
            return True

        except Exception as e:
            logger.error(f"Error resetting vector store: {e}")
            return False

    async def search_with_full_content(
        self, query: str, top_k: Optional[int] = None, include_full_docs: bool = True
    ) -> List[Dict]:
        """
        Search for documents and retrieve full content from Supabase.
        Maintains compatibility with existing interface.
        """
        try:
            # Perform vector search
            results = await self.search(query, top_k=top_k, include_metadata=True)

            # Group results by document ID
            docs_to_fetch: Dict[str, Any] = {}
            for result in results:
                if result.get("metadata"):
                    document_id = result["metadata"].get("document_id")
                    file_path = result["metadata"].get("file_path")

                    doc_key = document_id if document_id else file_path

                    if doc_key:
                        if doc_key not in docs_to_fetch:
                            docs_to_fetch[doc_key] = {
                                "chunks": [],
                                "best_score": result["score"],
                                "metadata": result["metadata"],
                                "document_id": document_id,
                                "file_path": file_path,
                            }
                        docs_to_fetch[doc_key]["chunks"].append(result)
                        if result["score"] > docs_to_fetch[doc_key]["best_score"]:
                            docs_to_fetch[doc_key]["best_score"] = result["score"]

            # Fetch full documents if requested
            enhanced_results = []

            if include_full_docs and docs_to_fetch:
                from storage.storage_service import document_storage

                for doc_key, doc_info in docs_to_fetch.items():
                    try:
                        full_content = None
                        document_data = None

                        # Try to fetch from Supabase
                        if doc_info["document_id"] and document_storage:
                            document_data = await document_storage.get_document_by_id(
                                doc_info["document_id"]
                            )
                            if document_data:
                                full_content = document_data.get("content", "")

                        if (
                            not full_content
                            and doc_info["file_path"]
                            and document_storage
                        ):
                            document_data = await document_storage.get_document(
                                doc_info["file_path"]
                            )
                            if document_data:
                                full_content = document_data.get("content", "")

                        if full_content and document_data:
                            enhanced_result = {
                                "id": document_data["id"],
                                "score": doc_info["best_score"],
                                "content": full_content,
                                "metadata": {
                                    **doc_info["metadata"],
                                    "title": document_data.get("title", ""),
                                    "category": document_data.get("category", ""),
                                    "tags": document_data.get("tags", []),
                                },
                                "chunks": doc_info["chunks"],
                                "source": "supabase",
                                "document_url": f"/documents/{document_data['id']}",
                            }
                            enhanced_results.append(enhanced_result)
                        else:
                            # Fallback to chunks
                            content_parts = []
                            for chunk in doc_info["chunks"]:
                                chunk_content = chunk.get("content")
                                if not chunk_content and chunk.get("metadata"):
                                    chunk_content = chunk["metadata"].get(
                                        "content_preview"
                                    )
                                if chunk_content:
                                    content_parts.append(chunk_content)

                            enhanced_result = {
                                "id": doc_key,
                                "score": doc_info["best_score"],
                                "content": (
                                    "\n\n".join(content_parts) if content_parts else ""
                                ),
                                "metadata": doc_info["metadata"],
                                "chunks": doc_info["chunks"],
                                "source": "chunks",
                            }
                            enhanced_results.append(enhanced_result)

                    except Exception as e:
                        logger.error(f"Error fetching document {doc_key}: {e}")
                        # Fallback to chunks
                        content_parts = []
                        for chunk in doc_info["chunks"]:
                            chunk_content = chunk.get("content")
                            if not chunk_content and chunk.get("metadata"):
                                chunk_content = chunk["metadata"].get("content_preview")
                            if chunk_content:
                                content_parts.append(chunk_content)

                        enhanced_result = {
                            "id": doc_key,
                            "score": doc_info["best_score"],
                            "content": (
                                "\n\n".join(content_parts) if content_parts else ""
                            ),
                            "metadata": doc_info["metadata"],
                            "chunks": doc_info["chunks"],
                            "source": "chunks",
                        }
                        enhanced_results.append(enhanced_result)
            else:
                # Return chunks only
                for doc_info in docs_to_fetch.values():
                    for chunk in doc_info["chunks"]:
                        enhanced_results.append(chunk)

            # Sort by score (highest first)
            enhanced_results.sort(key=lambda x: x["score"], reverse=True)

            return enhanced_results

        except Exception as e:
            logger.error(f"Error in search_with_full_content: {e}")
            return []


# Singleton instance
cloudflare_vector_store = CloudflareVectorStore()
