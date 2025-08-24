"""Automatic index generation for Supabase documents."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .storage_service import document_storage

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages automatic index generation for document categories."""

    def __init__(self):
        self.storage = document_storage

    async def generate_index(self, category: str) -> Optional[str]:
        """Generate an index for a specific category.

        Args:
            category: The category path (e.g., '10NetZero/sites/Eagle Lake')

        Returns:
            The generated index content or None if failed
        """
        try:
            # Get all documents in this category
            documents = await self.storage.list_documents_by_category(category)

            if not documents:
                return None

            # Sort documents by title
            documents.sort(key=lambda d: d.get("title", "").lower())

            # Generate index content
            index_lines = [
                f"# 📁 {category.split('/')[-1]}",
                "",
                f"This folder contains {len(documents)} documents.",
                "",
                "## 📄 Contents",
                "",
            ]

            # Group by subcategory if applicable
            subcategories: Dict[str, Any] = {}
            direct_docs = []

            for doc in documents:
                doc_category = doc.get("category", "")
                if doc_category.startswith(category + "/"):
                    # This is in a subcategory
                    subcat = doc_category[len(category) + 1 :].split("/")[0]
                    if subcat not in subcategories:
                        subcategories[subcat] = []
                    subcategories[subcat].append(doc)
                elif doc_category == category:
                    # Direct child of this category
                    direct_docs.append(doc)

            # Add direct documents
            if direct_docs:
                for doc in direct_docs:
                    title = doc.get("title", "Untitled")
                    file_path = doc.get("file_path", "")
                    tags = doc.get("tags", [])

                    # Skip index files
                    if "index.md" in file_path:
                        continue

                    tag_str = f" `{'` `'.join(tags)}`" if tags else ""
                    index_lines.append(f"- [{title}]({Path(file_path).name}){tag_str}")

                if subcategories:
                    index_lines.append("")

            # Add subcategories
            if subcategories:
                index_lines.append("## 📂 Subcategories")
                index_lines.append("")

                for subcat, docs in sorted(subcategories.items()):
                    index_lines.append(f"### {subcat}/")
                    index_lines.append(f"_{len(docs)} documents_")
                    index_lines.append("")

            # Add metadata
            index_lines.extend(
                [
                    "",
                    "---",
                    f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
                ]
            )

            return "\n".join(index_lines)

        except Exception as e:
            logger.error(f"Failed to generate index for {category}: {e}")
            return None

    async def update_index(
        self, category: str, telegram_chat_id: Optional[str] = None
    ) -> bool:
        """Update or create the index for a category.

        Args:
            category: The category path
            telegram_chat_id: Optional chat ID for tracking who triggered update

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate the index content
            content = await self.generate_index(category)
            if not content:
                logger.info(f"No documents found for category {category}")
                return False

            # Store the index
            index_path = f"{category}/index.md"

            metadata = {
                "title": f"{category.split('/')[-1]} Index",
                "type": "index",
                "auto_generated": True,
                "category": category,
            }

            result = await self.storage.store_document(
                file_path=index_path,
                content=content,
                metadata=metadata,
                category=category,
                tags=["index", "auto-generated"],
                telegram_chat_id=telegram_chat_id,
                created_by="index_manager",
            )

            if result:
                logger.info(f"Updated index for {category}")
                return True
            else:
                logger.error(f"Failed to store index for {category}")
                return False

        except Exception as e:
            logger.error(f"Failed to update index for {category}: {e}")
            return False

    async def update_all_indexes(
        self, telegram_chat_id: Optional[str] = None
    ) -> Dict[str, bool]:
        """Update all category indexes.

        Returns:
            Dict mapping category to success status
        """
        try:
            # Get all unique categories
            all_documents = await self.storage.list_all_documents()
            categories = set()

            for doc in all_documents:
                category = doc.get("category", "")
                if category:
                    # Add this category and all parent categories
                    parts = category.split("/")
                    for i in range(1, len(parts) + 1):
                        categories.add("/".join(parts[:i]))

            # Update each category's index
            results: Dict[str, Any] = {}
            for category in sorted(categories):
                results[category] = await self.update_index(category, telegram_chat_id)

            return results

        except Exception as e:
            logger.error(f"Failed to update all indexes: {e}")
            return {}


# Global instance
index_manager = IndexManager()
