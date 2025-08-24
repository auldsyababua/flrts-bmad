"""List operations processor working with existing lists/list_items tables."""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from src.core.benchmarks import async_benchmark
from src.monitoring import log_direct_execution_performance, production_logger

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class ListProcessor(BaseProcessor):
    """Handles all list-related operations using existing lists and list_items tables."""

    def __init__(self, supabase_client):
        super().__init__(supabase_client)

    def get_extraction_schema(self, operation: str) -> str:
        """Get JSON schema for LLM data extraction based on operation."""

        if operation is None:
            raise ValueError("Operation cannot be None")

        if not isinstance(operation, str):
            raise TypeError(f"Operation must be a string, got {type(operation)}")

        if not operation:
            raise ValueError("Operation cannot be empty")

        if operation == "create":
            return """{
                "list_name": "name of the list",
                "items": ["item1", "item2"],
                "list_type": "Tools Inventory|Shopping List|Safety Checklist|Maintenance Procedure|Contact List|Other",
                "description": "optional description",
                "site_name": "optional site name if site-specific"
            }"""

        elif operation == "add_items":
            return """{
                "list_name": "name of the list to update",
                "items": ["items to add"],
                "operation_type": "add_items"
            }"""

        elif operation == "remove_items":
            return """{
                "list_name": "name of the list to update", 
                "items": ["items to remove"],
                "operation_type": "remove_items"
            }"""

        elif operation == "rename":
            return """{
                "current_list_name": "current list name",
                "new_list_name": "new list name",
                "operation_type": "rename"
            }"""

        elif operation == "clear":
            return """{
                "list_name": "name of the list to clear",
                "operation_type": "clear",
                "confirm": true
            }"""

        elif operation == "read":
            return """{
                "list_name": "name of the list to show",
                "filters": {
                    "show_completed": true,
                    "limit": 50,
                    "site_name": "optional site filter"
                }
            }"""

        elif operation == "delete":
            return """{
                "list_name": "name of the list to delete",
                "operation_type": "delete",
                "confirm": true
            }"""

        else:
            raise KeyError(f"Unknown operation: {operation}")

    async def validate_operation(
        self, operation: str, data: Dict[str, Any], user_role: str = "user"
    ) -> Tuple[bool, str]:
        """Validate if operation is allowed and data is complete."""

        if operation is None:
            raise ValueError("Operation cannot be None")

        if data is None:
            raise ValueError("Data cannot be None")

        if user_role is None:
            raise ValueError("User role cannot be None")

        if not operation:
            return False, "Operation cannot be empty"

        # Check admin-only operations
        if operation == "delete" and user_role != "admin":
            return False, "List deletion requires admin privileges"

        # Check for protected lists (site-specific)
        if "list_name" in data:
            list_name = data["list_name"].lower()

            # Check if this is a site-protected list by looking up in database
            try:
                response = await self._safe_db_operation(
                    self.supabase.table("sites").select("site_name").execute()
                )
                if response and response.data:
                    site_names = [site["site_name"].lower() for site in response.data]

                    for site_name in site_names:
                        if site_name in list_name and operation == "delete":
                            return (
                                False,
                                f"Cannot delete site-specific list: {data['list_name']}",
                            )
            except Exception as e:
                logger.warning(f"Could not validate site protection: {e}")
                return False, "Database error occurred during validation"

        # Validate required fields
        required_fields = {
            "create": ["list_name"],
            "add_items": ["list_name", "items"],
            "remove_items": ["list_name", "items"],
            "rename": ["current_list_name", "new_list_name"],
            "clear": ["list_name"],
            "read": ["list_name"],
            "delete": ["list_name"],
        }

        if operation in required_fields:
            missing = [
                field for field in required_fields[operation] if field not in data
            ]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"

        return True, "Valid"

    def get_confidence_boost_factors(self, message: str, operation: str) -> float:
        """Calculate confidence boost based on message analysis."""
        boost = 0.0
        message_lower = message.lower()

        # Specific operation keywords boost confidence
        operation_keywords = {
            "add_items": ["add to", "put on", "include", "append"],
            "remove_items": ["remove from", "take off", "delete from"],
            "create": ["new list", "create list", "make list"],
            "clear": ["clear list", "empty list", "remove all"],
        }

        if operation in operation_keywords:
            if any(
                keyword in message_lower for keyword in operation_keywords[operation]
            ):
                boost += 0.1

        # Item enumeration boosts list operations
        if "," in message and operation in ["add_items", "remove_items", "create"]:
            boost += 0.05

        # List type specifications
        list_types = [
            "checklist",
            "shopping list",
            "todo list",
            "task list",
            "inventory",
            "tools",
        ]
        if any(list_type in message_lower for list_type in list_types):
            boost += 0.05

        # Site mentions boost confidence
        site_names = ["eagle lake", "crockett", "mathis"]
        if any(site in message_lower for site in site_names):
            boost += 0.1

        return boost

    def get_dynamic_extraction_schema(
        self, operation: str, prefilled_data: Dict[str, Any]
    ) -> str:
        """Generate dynamic extraction schema based on prefilled data."""

        if operation == "create":
            # We always need at least the list name
            return """{
                "list_name": "name of the list",
                "items": ["item1", "item2"],
                "list_type": "Tools Inventory|Shopping List|Safety Checklist|Maintenance Procedure|Contact List|Other",
                "description": "optional description",
                "site_name": "optional site name if site-specific"
            }"""

        elif operation == "add_items":
            # If we have prefilled assignee, we don't need to ask for it
            return """{
                "list_name": "name of the list to update",
                "items": ["items to add"]
            }"""

        elif operation == "remove_items":
            return """{
                "list_name": "name of the list to update", 
                "items": ["items to remove"]
            }"""

        elif operation == "rename":
            return """{
                "current_list_name": "current list name",
                "new_list_name": "new list name"
            }"""

        elif operation == "clear":
            return """{
                "list_name": "name of the list to clear",
                "confirm": true
            }"""

        elif operation == "read":
            # For read operations, we might have assignee prefilled
            if "assignee" in prefilled_data:
                return """{
                    "list_name": "name of the list to show",
                    "filters": {
                        "show_completed": true,
                        "limit": 50
                    }
                }"""
            else:
                return """{
                    "list_name": "name of the list to show",
                    "filters": {
                        "show_completed": true,
                        "limit": 50,
                        "site_name": "optional site filter"
                    }
                }"""

        elif operation == "delete":
            return """{
                "list_name": "name of the list to delete",
                "confirm": true
            }"""

        # Fall back to full schema if operation unknown
        return self.get_extraction_schema(operation)

    @async_benchmark("list_direct_execution")
    @log_direct_execution_performance(production_logger)
    async def execute_direct(
        self, operation: str, extracted_data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """
        Execute list operation directly without LLM.

        Args:
            operation: The operation to perform (create, add_items, remove_items, etc.)
            extracted_data: Data extracted from the router
            user_id: The user performing the operation

        Returns:
            Result dictionary with success status and details
        """
        start_time = time.perf_counter()

        try:
            # Validate the operation first
            is_valid, message = await self.validate_operation(
                operation, extracted_data, "user"
            )

            if not is_valid:
                return {
                    "success": False,
                    "error": message,
                    "operation": operation,
                    "execution_time": time.perf_counter() - start_time,
                }

            # Route to specific operation handler
            if operation == "create":
                result = await self._execute_create(extracted_data, user_id)
            elif operation == "add_items":
                result = await self._execute_add_items(extracted_data, user_id)
            elif operation == "remove_items":
                result = await self._execute_remove_items(extracted_data, user_id)
            elif operation == "rename":
                result = await self._execute_rename(extracted_data, user_id)
            elif operation == "clear":
                result = await self._execute_clear(extracted_data, user_id)
            elif operation == "read":
                result = await self._execute_read(extracted_data, user_id)
            elif operation == "delete":
                result = await self._execute_delete(extracted_data, user_id)
            else:
                result = {"success": False, "error": f"Unknown operation: {operation}"}

            # Add execution time
            result["execution_time"] = time.perf_counter() - start_time

            # Verify we're under 500ms target
            if result["execution_time"] > 0.5:
                logger.warning(
                    f"List {operation} took {result['execution_time']:.3f}s (target: <500ms)"
                )

            return result

        except Exception as e:
            logger.error(f"Error in direct list execution: {e}")
            return {
                "success": False,
                "error": "An error occurred while processing your request",
                "details": str(e),
                "operation": operation,
                "execution_time": time.perf_counter() - start_time,
            }

    async def _execute_create(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute list creation."""
        try:
            # Build list data
            list_data = {
                "name": data.get("list_name"),
                "type": data.get("list_type", "Other"),
                "description": data.get("description", ""),
                "created_by": user_id,
                "created_at": datetime.utcnow().isoformat(),
            }

            if "site_name" in data:
                list_data["site_name"] = data["site_name"]

            # Insert list
            response = await self._safe_db_operation(
                self.supabase.table("lists").insert(list_data).execute()
            )

            if response and response.data:
                list_id = response.data[0]["id"]

                # Add items if provided
                if "items" in data and data["items"]:
                    items_data = [
                        {
                            "list_id": list_id,
                            "content": item,
                            "is_completed": False,
                            "created_at": datetime.utcnow().isoformat(),
                        }
                        for item in data["items"]
                    ]

                    await self._safe_db_operation(
                        self.supabase.table("list_items").insert(items_data).execute()
                    )

                return {
                    "success": True,
                    "message": f"List '{list_data['name']}' created with {len(data.get('items', []))} items",
                    "list_id": list_id,
                    "data": response.data[0],
                }
            else:
                return {"success": False, "error": "Failed to create list in database"}

        except Exception as e:
            logger.error(f"Error creating list: {e}")
            return {"success": False, "error": f"Failed to create list: {str(e)}"}

    async def _execute_add_items(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute adding items to a list."""
        try:
            # Find the list
            list_obj = await self._find_list_by_name(data["list_name"])
            if not list_obj:
                return {
                    "success": False,
                    "error": f"List '{data['list_name']}' not found",
                }

            # Add items
            items_data = [
                {
                    "list_id": list_obj["id"],
                    "content": item,
                    "is_completed": False,
                    "created_at": datetime.utcnow().isoformat(),
                }
                for item in data.get("items", [])
            ]

            response = await self._safe_db_operation(
                self.supabase.table("list_items").insert(items_data).execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"Added {len(items_data)} items to '{list_obj['name']}'",
                    "list_id": list_obj["id"],
                    "items_added": len(items_data),
                }
            else:
                return {"success": False, "error": "Failed to add items to list"}

        except Exception as e:
            logger.error(f"Error adding items to list: {e}")
            return {"success": False, "error": f"Failed to add items: {str(e)}"}

    async def _execute_remove_items(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute removing items from a list."""
        try:
            # Find the list
            list_obj = await self._find_list_by_name(data["list_name"])
            if not list_obj:
                return {
                    "success": False,
                    "error": f"List '{data['list_name']}' not found",
                }

            # Find and remove items
            removed_count = 0
            for item in data.get("items", []):
                response = await self._safe_db_operation(
                    self.supabase.table("list_items")
                    .delete()
                    .eq("list_id", list_obj["id"])
                    .ilike("content", f"%{item}%")
                    .execute()
                )
                if response and response.data:
                    removed_count += len(response.data)

            return {
                "success": True,
                "message": f"Removed {removed_count} items from '{list_obj['name']}'",
                "list_id": list_obj["id"],
                "items_removed": removed_count,
            }

        except Exception as e:
            logger.error(f"Error removing items from list: {e}")
            return {"success": False, "error": f"Failed to remove items: {str(e)}"}

    async def _execute_rename(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute list renaming."""
        try:
            # Find the list
            list_name = data.get("current_list_name") or data.get("list_name")
            if not list_name:
                return {"success": False, "error": "No list name specified"}
            list_obj = await self._find_list_by_name(list_name)
            if not list_obj:
                return {"success": False, "error": "List not found"}

            # Update list name
            response = await self._safe_db_operation(
                self.supabase.table("lists")
                .update({"name": data["new_list_name"]})
                .eq("id", list_obj["id"])
                .execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"List renamed to '{data['new_list_name']}'",
                    "list_id": list_obj["id"],
                }
            else:
                return {"success": False, "error": "Failed to rename list"}

        except Exception as e:
            logger.error(f"Error renaming list: {e}")
            return {"success": False, "error": f"Failed to rename list: {str(e)}"}

    async def _execute_clear(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute clearing all items from a list."""
        try:
            # Find the list
            list_obj = await self._find_list_by_name(data["list_name"])
            if not list_obj:
                return {
                    "success": False,
                    "error": f"List '{data['list_name']}' not found",
                }

            # Delete all items
            response = await self._safe_db_operation(
                self.supabase.table("list_items")
                .delete()
                .eq("list_id", list_obj["id"])
                .execute()
            )

            if response:
                return {
                    "success": True,
                    "message": f"Cleared all items from '{list_obj['name']}'",
                    "list_id": list_obj["id"],
                }
            else:
                return {"success": False, "error": "Failed to clear list"}

        except Exception as e:
            logger.error(f"Error clearing list: {e}")
            return {"success": False, "error": f"Failed to clear list: {str(e)}"}

    async def _execute_read(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute reading/displaying a list."""
        try:
            # Find the list
            list_obj = await self._find_list_by_name(data["list_name"])
            if not list_obj:
                # If no specific list, return all lists
                response = await self._safe_db_operation(
                    self.supabase.table("lists").select("*").execute()
                )

                if response and response.data:
                    return {
                        "success": True,
                        "message": f"Found {len(response.data)} lists",
                        "lists": response.data,
                    }
                else:
                    return {"success": False, "error": "No lists found"}

            # Get list items
            query = (
                self.supabase.table("list_items")
                .select("*")
                .eq("list_id", list_obj["id"])
            )

            filters = data.get("filters", {})
            if not filters.get("show_completed", True):
                query = query.eq("is_completed", False)

            if "limit" in filters:
                query = query.limit(filters["limit"])

            response = await self._safe_db_operation(query.execute())

            if response and response.data is not None:
                return {
                    "success": True,
                    "message": f"List '{list_obj['name']}' has {len(response.data)} items",
                    "list": list_obj,
                    "items": response.data,
                }
            else:
                return {"success": False, "error": "Failed to retrieve list items"}

        except Exception as e:
            logger.error(f"Error reading list: {e}")
            return {"success": False, "error": f"Failed to read list: {str(e)}"}

    async def _execute_delete(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute list deletion."""
        try:
            # Find the list
            list_obj = await self._find_list_by_name(data["list_name"])
            if not list_obj:
                return {
                    "success": False,
                    "error": f"List '{data['list_name']}' not found",
                }

            # Delete list items first
            await self._safe_db_operation(
                self.supabase.table("list_items")
                .delete()
                .eq("list_id", list_obj["id"])
                .execute()
            )

            # Delete the list
            response = await self._safe_db_operation(
                self.supabase.table("lists").delete().eq("id", list_obj["id"]).execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"List '{list_obj['name']}' deleted",
                    "list_id": list_obj["id"],
                }
            else:
                return {"success": False, "error": "Failed to delete list"}

        except Exception as e:
            logger.error(f"Error deleting list: {e}")
            return {"success": False, "error": f"Failed to delete list: {str(e)}"}

    async def _find_list_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a list by name (case-insensitive)."""
        if not name:
            return None

        try:
            response = await self._safe_db_operation(
                self.supabase.table("lists")
                .select("*")
                .ilike("name", f"%{name}%")
                .limit(1)
                .execute()
            )

            if response and response.data:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Error finding list: {e}")
            return None
