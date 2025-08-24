#!/usr/bin/env python3
"""
Reset databases to clean state with only 10NetZero content.

This script:
1. Clears the vector store
2. Backs up 10NetZero folder
3. Clears entire notes folder
4. Restores 10NetZero folder
5. Re-indexes 10NetZero content
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../..", "src"))

from core.chunking import chunk_markdown_document  # noqa: E402
from storage.storage_service import DocumentStorage  # noqa: E402
from storage.vector_store import vector_store  # noqa: E402

# Initialize document storage
document_storage = DocumentStorage()


async def main():
    print("🧹 Cleaning databases...")
    print("=" * 50)

    # 1. Clear vector store
    print("\n1️⃣ Clearing vector store...")
    try:
        await vector_store.reset_store()
        print("✅ Vector store cleared successfully")
    except Exception as e:
        print(f"❌ Failed to clear vector store: {e}")
        return

    # 2. Clear Supabase documents
    print("\n2️⃣ Clearing Supabase documents...")
    try:
        await document_storage.clear_all_documents()
        print("✅ Supabase documents cleared successfully")
    except Exception as e:
        print(f"❌ Failed to clear Supabase: {e}")
        return

    # 3. Set up paths
    print("\n3️⃣ Setting up paths...")
    kb_path = Path("10nz_kb")
    if not kb_path.exists():
        print("❌ 10nz_kb directory not found!")
        return

    # 4. Re-index content from 10nz_kb
    print("\n4️⃣ Re-indexing content from 10nz_kb...")

    md_files = list(kb_path.rglob("*.md"))
    print(f"📄 Found {len(md_files)} markdown files to index")

    indexed_count = 0
    chunk_count = 0

    for file_path in md_files:
        try:
            print(f"\n📄 Processing: {file_path.relative_to(kb_path)}")

            # Read file content
            content = file_path.read_text(encoding="utf-8")

            # Extract metadata
            title = file_path.stem.replace("-", " ").replace("_", " ")
            # Get the relative path to determine the folder structure
            rel_path = file_path.relative_to(kb_path)
            folder_parts = list(rel_path.parts[:-1])  # All parts except filename
            folder = "/".join(folder_parts) if folder_parts else "root"

            # Store in Supabase first
            try:
                document_data = await document_storage.store_and_return_document(
                    file_path=str(file_path),
                    content=content,
                    metadata={"title": title, "folder": folder},
                    category="10NetZero",
                    tags=["10netzero", folder.lower()],
                    created_by="reset_script",
                )

                if not document_data:
                    print("   ❌ Failed to store document in Supabase")
                    continue

                document_id = document_data["id"]
                print(f"   ✅ Stored in Supabase with ID: {document_id}")

            except Exception as e:
                print(f"   ❌ Error storing in Supabase: {e}")
                continue

            # Chunk and index
            chunk_metadata = {
                "title": title,
                "folder": folder,
                "source": "database_reset",
                "document_id": document_id,
            }

            chunks = chunk_markdown_document(
                content=content,
                file_path=str(file_path),
                metadata=chunk_metadata,
                chunk_size=1000,
                chunk_overlap=200,
            )
            print(f"   📊 Created {len(chunks)} chunks")

            # Store chunks in vector store
            for chunk_content, chunk_meta in chunks:
                chunk_id = f"{document_id}#chunk_{chunk_meta['chunk_index']}"

                chunk_meta.update(
                    {
                        "indexed_at": datetime.now().isoformat(),
                        "document_id": document_id,
                    }
                )

                success = await vector_store.embed_and_store(
                    chunk_id, chunk_content, chunk_meta
                )

                if success:
                    chunk_count += 1
                    # Store chunk reference in Supabase
                    if document_storage:
                        await document_storage.store_document_chunk(
                            document_id=document_id,
                            chunk_index=chunk_meta["chunk_index"],
                            chunk_text=chunk_content,
                            vector_id=chunk_id,
                            start_char=chunk_meta.get("start_char", 0),
                            end_char=chunk_meta.get("end_char", len(chunk_content)),
                            metadata=chunk_meta,
                        )

            indexed_count += 1

        except Exception as e:
            print(f"   ❌ Error processing {file_path}: {e}")

    print(
        f"\n✅ Indexed {indexed_count}/{len(md_files)} documents ({chunk_count} chunks total)"
    )

    # Wait for eventual consistency
    print("\n⏳ Waiting 5 seconds for eventual consistency...")
    await asyncio.sleep(5)

    # Verify with a test query
    print("\n🔍 Verifying index with test query...")
    results = await vector_store.search("10NetZero sites", top_k=3)

    if results:
        print(f"✅ Found {len(results)} results - index is working!")
    else:
        print("⚠️  No results found - index might need more time")

    print("\n✅ Database reset complete!")


if __name__ == "__main__":
    asyncio.run(main())
