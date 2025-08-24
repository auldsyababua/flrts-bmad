#!/usr/bin/env python3
"""
Remote diagnostic script to check vector store status in production.
This script is designed to be run on Render to diagnose issues.
"""

import asyncio
import os
import sys
from datetime import datetime


# Add color support
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")


def print_success(text):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_info(text):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


async def run_diagnostics():
    """Run comprehensive diagnostics."""
    print_header(f"Remote Diagnostics - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 1. Check Python version
    print("1. System Information:")
    print(f"   Python version: {sys.version}")
    print(f"   Platform: {sys.platform}")

    # 2. Check environment variables
    print("\n2. Environment Variables:")
    env_vars = [
        ("UPSTASH_VECTOR_REST_URL", True),
        ("UPSTASH_VECTOR_REST_TOKEN", True),
        ("TELEGRAM_BOT_TOKEN", True),
        ("OPENAI_API_KEY", True),
        ("REDIS_URL", False),
        ("NOTES_FOLDER", False),
        ("VECTOR_NAMESPACE", False),
        ("VECTOR_TOP_K", False),
    ]

    missing_required = []
    for var_name, is_required in env_vars:
        value = os.getenv(var_name)
        if value:
            # Mask sensitive values
            if "TOKEN" in var_name or "KEY" in var_name or "URL" in var_name:
                masked_value = (
                    value[:10] + "..." + value[-5:] if len(value) > 15 else "***"
                )
                print_success(f"{var_name}: {masked_value}")
            else:
                print_success(f"{var_name}: {value}")
        else:
            if is_required:
                print_error(f"{var_name}: Missing")
                missing_required.append(var_name)
            else:
                print_info(f"{var_name}: Not set (optional)")

    if missing_required:
        print_error(
            f"\nMissing required environment variables: {', '.join(missing_required)}"
        )
        return False

    # 3. Test imports
    print("\n3. Testing Python imports:")
    imports_ok = True
    try:
        from vector_store import vector_store

        print_success("vector_store imported successfully")
    except Exception as e:
        print_error(f"Failed to import vector_store: {e}")
        imports_ok = False

    try:
        from llm import search_knowledge_base

        print_success("llm module imported successfully")
    except Exception as e:
        print_error(f"Failed to import llm: {e}")
        imports_ok = False

    try:
        from version import VERSION

        print_success(f"Version module imported: v{VERSION}")
    except Exception as e:
        print_error(f"Failed to import version: {e}")

    if not imports_ok:
        return False

    # 4. Test vector store connection
    print("\n4. Testing Vector Store Connection:")
    try:
        from vector_store import vector_store

        # Simple connectivity test
        await vector_store.search("test", top_k=1)
        print_success("Successfully connected to vector store")

        # 5. Count documents
        print("\n5. Checking for 10NetZero documents:")
        queries = ["10NetZero", "10 net zero", "10netzero", "FLRTS"]
        total_found = 0

        for query in queries:
            results = await vector_store.search(query, top_k=5)
            if results:
                print_success(f"Query '{query}': Found {len(results)} results")
                total_found += len(results)
                # Show first result
                if results[0].get("metadata"):
                    meta = results[0]["metadata"]
                    print(f"     First result: {meta.get('file_path', 'Unknown')}")
            else:
                print_warning(f"Query '{query}': No results found")

        if total_found == 0:
            print_error("\nNo 10NetZero documents found in vector store!")
            print_warning(
                "You need to run migration: python migrate_to_vector.py --chunked"
            )
        else:
            print_success(f"\nTotal documents found: {total_found}")

        # 6. Test search_knowledge_base function
        print("\n6. Testing search_knowledge_base function:")
        from llm import search_knowledge_base

        kb_results = await search_knowledge_base("10NetZero")
        if kb_results:
            print_success(f"Knowledge base search returned {len(kb_results)} results")
            print(f"     Using: {kb_results[0].get('source', 'unknown')} source")
        else:
            print_error("Knowledge base search returned no results")

    except Exception as e:
        print_error(f"Vector store error: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 7. Check file system
    print("\n7. Checking file system:")
    notes_folder = os.getenv("NOTES_FOLDER", "notes")
    if os.path.exists(notes_folder):
        print_success(f"Notes folder exists: {notes_folder}")
        # Count markdown files
        md_files = []
        for root, dirs, files in os.walk(notes_folder):
            for file in files:
                if file.endswith(".md"):
                    md_files.append(os.path.join(root, file))
        print_info(f"Found {len(md_files)} markdown files")

        # Check for 10NetZero folder
        ten_net_folder = os.path.join(notes_folder, "10NetZero")
        if os.path.exists(ten_net_folder):
            print_success("10NetZero folder exists")
            ten_files = [f for f in os.listdir(ten_net_folder) if f.endswith(".md")]
            print_info(f"Found {len(ten_files)} files in 10NetZero folder")
        else:
            print_warning("10NetZero folder not found")
    else:
        print_error(f"Notes folder not found: {notes_folder}")

    # Summary
    print_header("Diagnostic Summary")
    if total_found == 0:
        print_error("Vector store is empty or not properly configured")
        print_warning("\nACTION REQUIRED:")
        print("1. Run migration: python migrate_to_vector.py --chunked")
        print("2. Restart the service after migration")
    else:
        print_success("Vector store is working and contains documents")
        print_info("If bot still can't find documents, check:")
        print("1. Redis connection for conversation memory")
        print("2. OpenAI API limits or errors")

    return True


if __name__ == "__main__":
    print("Starting remote diagnostics...")
    success = asyncio.run(run_diagnostics())
    sys.exit(0 if success else 1)
