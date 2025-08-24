#!/usr/bin/env python3
"""
Diagnostic script to test vector store connectivity and search functionality.
This helps debug why the bot might not be finding 10NetZero content.
"""

import asyncio
import os

from dotenv import load_dotenv
from llm import search_knowledge_base
from vector_store import vector_store
from version import VERSION

# Load environment variables
load_dotenv()


async def diagnose_vector_store():
    """Run comprehensive diagnostics on the vector store."""
    print(f"🔍 Vector Store Diagnostics (Bot Version {VERSION})")
    print("=" * 60)

    # 1. Check environment variables
    print("\n1. Environment Check:")
    vector_url = os.getenv("UPSTASH_VECTOR_REST_URL")
    vector_token = os.getenv("UPSTASH_VECTOR_REST_TOKEN")
    namespace = os.getenv("VECTOR_NAMESPACE", "")

    print(f"   UPSTASH_VECTOR_REST_URL: {'✅ Set' if vector_url else '❌ Missing'}")
    print(f"   UPSTASH_VECTOR_REST_TOKEN: {'✅ Set' if vector_token else '❌ Missing'}")
    print(f"   VECTOR_NAMESPACE: '{namespace}' (empty means default)")

    if not vector_url or not vector_token:
        print("\n❌ Missing required environment variables!")
        return

    # 2. Test basic connectivity
    print("\n2. Vector Store Connectivity Test:")
    try:
        # Try a simple search
        test_results = await vector_store.search("test", top_k=1)
        print("   ✅ Successfully connected to vector store")
    except Exception as e:
        print(f"   ❌ Failed to connect: {e}")
        return

    # 3. Search for 10NetZero content
    print("\n3. Searching for 10NetZero Content:")
    queries = ["10NetZero", "10NetZero company", "carbon emissions", "FLRTS"]

    for query in queries:
        print(f"\n   Query: '{query}'")
        try:
            # Direct vector search
            results = await vector_store.search(query, top_k=3)
            print(f"   Found {len(results)} results from direct vector search")

            if results:
                for i, result in enumerate(results[:2], 1):
                    print(f"\n   Result {i}:")
                    print(f"     ID: {result.get('id', 'Unknown')}")
                    print(f"     Score: {result.get('score', 0):.4f}")
                    if result.get("metadata"):
                        meta = result["metadata"]
                        print(f"     File: {meta.get('file_path', 'Unknown')}")
                        print(f"     Title: {meta.get('title', 'Unknown')}")
                        print(f"     Type: {meta.get('type', 'Unknown')}")
                        print(f"     Source: {meta.get('source', 'Unknown')}")

                    content = result.get("content", "")
                    if content:
                        preview = content[:100].replace("\n", " ")
                        print(f"     Preview: {preview}...")
            else:
                print("     No results found")

        except Exception as e:
            print(f"   ❌ Error searching: {e}")

    # 4. Test search_knowledge_base function (what the bot uses)
    print("\n4. Testing Bot's search_knowledge_base Function:")
    try:
        kb_results = await search_knowledge_base("10NetZero")
        print(f"   Found {len(kb_results)} results from knowledge base search")

        if kb_results:
            result = kb_results[0]
            print("\n   Top result:")
            print(f"     ID: {result.get('id', 'Unknown')}")
            print(f"     Score: {result.get('score', 0):.4f}")
            print(f"     Content length: {len(result.get('content', ''))} chars")
            print(
                f"     Source: {result.get('source', 'vector' if result.get('score', 0) > 0.5 else 'file search fallback')}"
            )
    except Exception as e:
        print(f"   ❌ Error in knowledge base search: {e}")

    # 5. Test with full content search
    print("\n5. Testing search_with_full_content Method:")
    try:
        full_results = await vector_store.search_with_full_content(
            "10NetZero", top_k=3, include_full_docs=True
        )
        print(f"   Found {len(full_results)} results with full content")

        if full_results:
            result = full_results[0]
            print("\n   Top result:")
            print(f"     File: {result.get('id', 'Unknown')}")
            print(f"     Score: {result.get('score', 0):.4f}")
            print(f"     Content length: {len(result.get('content', ''))} chars")
            print(f"     Source: {result.get('source', 'Unknown')}")
            print(f"     Chunks: {len(result.get('chunks', []))}")
    except Exception as e:
        print(f"   ❌ Error in full content search: {e}")

    # 6. Check for specific document IDs
    print("\n6. Checking for Specific Document IDs:")
    doc_ids = [
        "10NetZero_README",
        "10NetZero_about-10netzero",
        "10NetZero_## 10NetZero Company Overview",
        "notes/10NetZero/README.md#chunk_0",
        "notes/10NetZero/about-10netzero.md#chunk_0",
    ]

    found_count = 0
    for doc_id in doc_ids:
        try:
            result = await vector_store.fetch_document(doc_id)
            if result:
                found_count += 1
                print(f"   ✅ Found: {doc_id}")
            else:
                print(f"   ❌ Not found: {doc_id}")
        except Exception as e:
            print(f"   ❌ Error fetching {doc_id}: {e}")

    print(f"\n   Summary: Found {found_count}/{len(doc_ids)} documents")

    # Final summary
    print("\n" + "=" * 60)
    print("Diagnostic Summary:")
    print(f"- Bot Version: {VERSION}")
    print(
        f"- Vector store connection: {'✅ Working' if test_results is not None else '❌ Failed'}"
    )
    print(f"- Documents found: {found_count > 0}")
    print("\nPossible issues:")
    if found_count == 0:
        print("- No 10NetZero documents in vector store")
        print("- May need to run migration: python migrate_to_vector.py")
        print("- Or chunked migration: python migrate_to_vector.py --chunked")
    if namespace:
        print(f"- Check if namespace '{namespace}' is correct")
    print("\nNext steps:")
    print("1. Ensure environment variables are set correctly")
    print("2. Run migration if documents are missing")
    print("3. Check Render logs for any errors")


if __name__ == "__main__":
    asyncio.run(diagnose_vector_store())
