#!/usr/bin/env python3
"""
List and view contents of the vector store in human-readable format.
"""

import asyncio
import json
import sys

from vector_store import vector_store


async def list_all_documents(limit: int = 100):
    """List all documents in the vector store."""
    print("\n📚 Documents in Vector Store\n" + "=" * 60)

    # Search with a very broad query to get many results
    # This is a workaround since Upstash doesn't have a direct list operation
    queries = ["", "the", "a", "10NetZero", "*"]

    all_docs = {}

    for query in queries:
        try:
            results = await vector_store.search(query, top_k=limit)
            for result in results:
                doc_id = result.get("id", "Unknown")
                if doc_id not in all_docs:
                    all_docs[doc_id] = result
        except Exception:
            continue

    if not all_docs:
        print("No documents found in vector store.")
        return

    # Sort by ID
    sorted_docs = sorted(all_docs.items(), key=lambda x: x[0])

    print(f"Found {len(sorted_docs)} unique documents:\n")

    for i, (doc_id, doc) in enumerate(sorted_docs, 1):
        print(f"{i}. ID: {doc_id}")

        if doc.get("metadata"):
            meta = doc["metadata"]
            print(f"   File: {meta.get('file_path', 'N/A')}")
            print(f"   Title: {meta.get('title', 'N/A')}")
            print(f"   Type: {meta.get('type', 'N/A')}")
            print(f"   Source: {meta.get('source', 'N/A')}")

            # Check if it's a chunk
            if "chunk_index" in meta:
                print(
                    f"   Chunk: {meta['chunk_index']}/{meta.get('total_chunks', '?')}"
                )

        # Show content preview
        content = doc.get("content", "")
        if content:
            preview = content[:100].replace("\n", " ")
            print(f"   Preview: {preview}...")

        print()


async def view_document(doc_id: str):
    """View full details of a specific document."""
    print(f"\n📄 Document Details: {doc_id}\n" + "=" * 60)

    result = await vector_store.fetch_document(doc_id)

    if not result:
        print(f"Document '{doc_id}' not found.")
        return

    print(f"ID: {result.get('id', 'Unknown')}")

    if result.get("metadata"):
        print("\nMetadata:")
        for key, value in result["metadata"].items():
            print(f"  {key}: {value}")

    content = result.get("content", "")
    if content:
        print(f"\nContent Preview ({len(content)} chars):")
        print("-" * 40)
        print(content[:500] + "..." if len(content) > 500 else content)
        print("-" * 40)


async def search_and_show(query: str, top_k: int = 5):
    """Search for documents and show results."""
    print(f"\n🔍 Search Results for: '{query}'\n" + "=" * 60)

    results = await vector_store.search(query, top_k=top_k)

    if not results:
        print("No results found.")
        return

    print(f"Found {len(results)} results:\n")

    for i, result in enumerate(results, 1):
        print(f"{i}. Score: {result.get('score', 0):.4f}")
        print(f"   ID: {result.get('id', 'Unknown')}")

        if result.get("metadata"):
            meta = result["metadata"]
            print(f"   File: {meta.get('file_path', 'N/A')}")
            print(f"   Title: {meta.get('title', 'N/A')}")

        content = result.get("content", "")
        if content:
            preview = content[:150].replace("\n", " ")
            print(f"   Content: {preview}...")

        print()


async def export_to_json(filename: str = "vector_store_export.json"):
    """Export vector store contents to JSON file."""
    print(f"\n💾 Exporting to {filename}...")

    # Get all documents
    queries = ["", "the", "a", "*"]
    all_docs = {}

    for query in queries:
        try:
            results = await vector_store.search(query, top_k=100)
            for result in results:
                doc_id = result.get("id", "Unknown")
                if doc_id not in all_docs:
                    all_docs[doc_id] = {
                        "id": doc_id,
                        "score": result.get("score", 0),
                        "metadata": result.get("metadata", {}),
                        "content_preview": result.get("content", "")[:500],
                    }
        except Exception:
            continue

    with open(filename, "w") as f:
        json.dump(all_docs, f, indent=2)

    print(f"✅ Exported {len(all_docs)} documents to {filename}")


async def main():
    if len(sys.argv) < 2:
        print(
            """
Usage:
    python list_vector_contents.py list [limit]      - List all documents
    python list_vector_contents.py view <doc_id>     - View specific document
    python list_vector_contents.py search <query>    - Search documents
    python list_vector_contents.py export [filename] - Export to JSON
        """
        )
        return

    command = sys.argv[1].lower()

    if command == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
        await list_all_documents(limit)

    elif command == "view" and len(sys.argv) > 2:
        await view_document(sys.argv[2])

    elif command == "search" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        await search_and_show(query)

    elif command == "export":
        filename = sys.argv[2] if len(sys.argv) > 2 else "vector_store_export.json"
        await export_to_json(filename)

    else:
        print("Invalid command. Run without arguments for usage.")


if __name__ == "__main__":
    asyncio.run(main())
