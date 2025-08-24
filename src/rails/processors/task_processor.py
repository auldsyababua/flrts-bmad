"""Task operations processor working with existing tasks table."""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.core.benchmarks import async_benchmark
from src.monitoring import log_direct_execution_performance, production_logger

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class TaskProcessor(BaseProcessor):
    """Handles task operations using existing tasks table."""

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
                "task_title": "title of the task",
                "task_description_detailed": "detailed description",
                "assigned_to": "username or alias",
                "site_name": "optional site name",
                "due_date": "YYYY-MM-DD format or relative like tomorrow",
                "priority": "High|Medium|Low",
                "reminder_time": "optional reminder datetime"
            }"""

        elif operation == "complete":
            return """{
                "task_title": "title or description of task to complete",
                "completion_notes": "optional completion notes"
            }"""

        elif operation == "reassign":
            return """{
                "task_title": "title of task to reassign",
                "new_assignee": "username or alias of new assignee",
                "reason": "optional reason for reassignment"
            }"""

        elif operation == "reschedule":
            return """{
                "task_title": "title of task to reschedule",
                "new_due_date": "new due date",
                "reason": "optional reason for reschedule"
            }"""

        elif operation == "add_notes":
            return """{
                "task_title": "title of task to add notes to",
                "notes": "notes to add to task description"
            }"""

        elif operation == "read":
            return """{
                "filters": {
                    "assigned_to": "optional username filter",
                    "site_name": "optional site filter", 
                    "status": "To Do|In Progress|Completed|Blocked|Cancelled",
                    "priority": "High|Medium|Low",
                    "date_range": "optional date range"
                }
            }"""

        else:
            raise KeyError(f"Unknown operation: {operation}")

    async def validate_operation(
        self, operation: str, data: Dict[str, Any], user_role: str = "user"
    ) -> tuple[bool, str]:
        """Validate if operation is allowed and data is complete."""

        # Validate required fields
        required_fields: Dict[str, List[str]] = {
            "create": ["task_title"],
            "complete": ["task_title"],
            "reassign": ["task_title", "new_assignee"],
            "reschedule": ["task_title", "new_due_date"],
            "add_notes": ["task_title", "notes"],
            "read": [],  # No required fields for read operations
        }

        if operation in required_fields:
            missing = [
                field for field in required_fields[operation] if field not in data
            ]
            if missing:
                return False, f"Missing required fields: {', '.join(missing)}"

        # Validate assignee exists if specified
        if (operation in ["create", "reassign"]) and (
            "assigned_to" in data or "new_assignee" in data
        ):
            assignee = data.get("assigned_to") or data.get("new_assignee")
            if assignee:
                try:
                    # Check if user exists in personnel table or aliases
                    response = await self._safe_db_operation(
                        self.supabase.table("personnel")
                        .select("id, first_name, aliases")
                        .eq("is_active", True)
                        .execute()
                    )

                    if response and response.data:
                        valid_users = []
                        for user in response.data:
                            valid_users.append(user["first_name"].lower())
                            if user.get("aliases"):
                                valid_users.extend(
                                    [alias.lower() for alias in user["aliases"]]
                                )

                        if assignee.lower() not in valid_users:
                            return (
                                False,
                                f"Unknown user: {assignee}. Please use a known username or alias.",
                            )
                    else:
                        # If we can't validate, fail gracefully
                        logger.warning(
                            "Could not validate assignee - database unavailable"
                        )
                        return (
                            False,
                            "Could not validate assignee - database unavailable",
                        )

                except Exception as e:
                    logger.warning(f"Could not validate assignee: {e}")
                    return False, "Database error occurred during validation"

        return True, "Valid"

    def get_confidence_boost_factors(self, message: str, operation: str) -> float:
        """Calculate confidence boost based on message analysis."""
        if message is None:
            raise ValueError("Message cannot be None")
        if operation is None:
            raise ValueError("Operation cannot be None")

        boost = 0.0
        message_lower = message.lower()

        # Specific operation keywords boost confidence
        operation_keywords = {
            "create": ["new task", "create task", "remind me", "task for"],
            "complete": ["mark complete", "finish", "done with", "completed"],
            "reassign": ["assign to", "reassign to", "give to", "transfer to"],
            "reschedule": ["reschedule", "move to", "change date", "push to"],
            "add_notes": ["add note", "note on", "update with", "add details"],
        }

        if operation in operation_keywords:
            if any(
                keyword in message_lower for keyword in operation_keywords[operation]
            ):
                boost += 0.1

        # Time references boost task operations
        time_indicators = [
            "tomorrow",
            "today",
            "next week",
            "at",
            "pm",
            "am",
            "deadline",
            "due",
        ]
        if any(indicator in message_lower for indicator in time_indicators):
            boost += 0.1

        # Priority indicators boost confidence
        priority_words = [
            "urgent",
            "asap",
            "high priority",
            "low priority",
            "important",
        ]
        if any(word in message_lower for word in priority_words):
            boost += 0.05

        # Site mentions boost confidence for site-specific tasks
        site_names = ["eagle lake", "crockett", "mathis"]
        if any(site in message_lower for site in site_names):
            boost += 0.1

        # User mentions boost assignment operations
        if "@" in message and operation in ["create", "reassign"]:
            boost += 0.15

        return boost

    def get_dynamic_extraction_schema(
        self, operation: str, prefilled_data: Dict[str, Any]
    ) -> str:
        """Generate dynamic extraction schema based on prefilled data."""

        if operation == "create":
            # If assignee is prefilled, don't ask for it
            if "assignee" in prefilled_data:
                return """{
                    "task_title": "title of the task",
                    "task_description_detailed": "detailed description",
                    "site_name": "optional site name",
                    "due_date": "YYYY-MM-DD format or relative like tomorrow",
                    "priority": "High|Medium|Low",
                    "reminder_time": "optional reminder datetime"
                }"""
            else:
                return self.get_extraction_schema(operation)

        elif operation == "complete":
            return """{
                "task_title": "title or description of task to complete",
                "completion_notes": "optional completion notes"
            }"""

        elif operation == "reassign":
            # If new assignee is prefilled, don't ask for it
            if "assignee" in prefilled_data:
                return """{
                    "task_title": "title of task to reassign",
                    "reason": "optional reason for reassignment"
                }"""
            else:
                return """{
                    "task_title": "title of task to reassign",
                    "new_assignee": "username or alias of new assignee",
                    "reason": "optional reason for reassignment"
                }"""

        elif operation == "reschedule":
            return """{
                "task_title": "title of task to reschedule",
                "new_due_date": "new due date",
                "reason": "optional reason for reschedule"
            }"""

        elif operation == "add_notes":
            return """{
                "task_title": "title of task to add notes to",
                "notes": "notes to add to task description"
            }"""

        elif operation == "read":
            # If assignee is prefilled, use it as a filter
            if "assignee" in prefilled_data:
                return """{
                    "filters": {
                        "site_name": "optional site filter", 
                        "status": "To Do|In Progress|Completed|Blocked|Cancelled",
                        "priority": "High|Medium|Low",
                        "date_range": "optional date range"
                    }
                }"""
            else:
                return self.get_extraction_schema(operation)

        # Fall back to full schema if operation unknown
        return self.get_extraction_schema(operation)

    @async_benchmark("task_direct_execution")
    @log_direct_execution_performance(production_logger)
    async def execute_direct(
        self, operation: str, extracted_data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """
        Execute task operation directly without LLM.

        Args:
            operation: The operation to perform (create, complete, reassign, etc.)
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
            elif operation == "complete":
                result = await self._execute_complete(extracted_data, user_id)
            elif operation == "reassign":
                result = await self._execute_reassign(extracted_data, user_id)
            elif operation == "reschedule":
                result = await self._execute_reschedule(extracted_data, user_id)
            elif operation == "add_notes":
                result = await self._execute_add_notes(extracted_data, user_id)
            elif operation == "read":
                result = await self._execute_read(extracted_data, user_id)
            else:
                result = {"success": False, "error": f"Unknown operation: {operation}"}

            # Add execution time
            result["execution_time"] = time.perf_counter() - start_time

            # Verify we're under 500ms target
            if result["execution_time"] > 0.5:
                logger.warning(
                    f"Task {operation} took {result['execution_time']:.3f}s (target: <500ms)"
                )

            return result

        except Exception as e:
            logger.error(f"Error in direct task execution: {e}")
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
        """Execute task creation."""
        try:
            # Build task data
            task_data = {
                "title": data.get("task_title"),
                "description": data.get("task_description_detailed", ""),
                "status": "To Do",
                "priority": data.get("priority", "Medium"),
                "created_by": user_id,
                "created_at": datetime.utcnow().isoformat(),
            }

            # Add optional fields
            if "assigned_to" in data:
                # Resolve assignee to user ID
                assignee_id = await self._resolve_user_id(data["assigned_to"])
                if assignee_id:
                    task_data["assigned_to"] = assignee_id

            if "due_date" in data:
                task_data["due_date"] = self._parse_date(data["due_date"])

            if "site_name" in data:
                task_data["site_name"] = data["site_name"]

            # Insert task
            response = await self._safe_db_operation(
                self.supabase.table("tasks").insert(task_data).execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"Task '{task_data['title']}' created successfully",
                    "task_id": response.data[0]["id"],
                    "data": response.data[0],
                }
            else:
                return {"success": False, "error": "Failed to create task in database"}

        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return {"success": False, "error": f"Failed to create task: {str(e)}"}

    async def _execute_complete(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute task completion."""
        try:
            # Find the task
            task = await self._find_task_by_title(data["task_title"])
            if not task:
                return {
                    "success": False,
                    "error": f"Task '{data['task_title']}' not found",
                }

            # Update task status
            update_data = {
                "status": "Completed",
                "completed_at": datetime.utcnow().isoformat(),
                "completed_by": user_id,
            }

            if "completion_notes" in data:
                update_data["completion_notes"] = data["completion_notes"]

            response = await self._safe_db_operation(
                self.supabase.table("tasks")
                .update(update_data)
                .eq("id", task["id"])
                .execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"Task '{task['title']}' marked as complete",
                    "task_id": task["id"],
                }
            else:
                return {"success": False, "error": "Failed to update task status"}

        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return {"success": False, "error": f"Failed to complete task: {str(e)}"}

    async def _execute_reassign(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute task reassignment."""
        try:
            # Find the task
            task = await self._find_task_by_title(data["task_title"])
            if not task:
                return {
                    "success": False,
                    "error": f"Task '{data['task_title']}' not found",
                }

            # Resolve new assignee
            new_assignee = data.get("new_assignee") or data.get("assignee")
            if not new_assignee:
                return {"success": False, "error": "No assignee specified"}
            assignee_id = await self._resolve_user_id(new_assignee)
            if not assignee_id:
                return {"success": False, "error": f"User '{new_assignee}' not found"}

            # Update task
            update_data = {
                "assigned_to": assignee_id,
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": user_id,
            }

            if "reason" in data:
                # Add reassignment reason to notes
                current_notes = task.get("notes", "")
                new_note = f"[Reassigned: {data['reason']}]"
                update_data["notes"] = f"{current_notes}\n{new_note}".strip()

            response = await self._safe_db_operation(
                self.supabase.table("tasks")
                .update(update_data)
                .eq("id", task["id"])
                .execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"Task '{task['title']}' reassigned to {new_assignee}",
                    "task_id": task["id"],
                }
            else:
                return {"success": False, "error": "Failed to reassign task"}

        except Exception as e:
            logger.error(f"Error reassigning task: {e}")
            return {"success": False, "error": f"Failed to reassign task: {str(e)}"}

    async def _execute_reschedule(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute task rescheduling."""
        try:
            # Find the task
            task = await self._find_task_by_title(data["task_title"])
            if not task:
                return {
                    "success": False,
                    "error": f"Task '{data['task_title']}' not found",
                }

            # Parse new date
            new_date = self._parse_date(data["new_due_date"])

            # Update task
            update_data = {
                "due_date": new_date,
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": user_id,
            }

            if "reason" in data:
                # Add reschedule reason to notes
                current_notes = task.get("notes", "")
                new_note = f"[Rescheduled: {data['reason']}]"
                update_data["notes"] = f"{current_notes}\n{new_note}".strip()

            response = await self._safe_db_operation(
                self.supabase.table("tasks")
                .update(update_data)
                .eq("id", task["id"])
                .execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"Task '{task['title']}' rescheduled to {new_date}",
                    "task_id": task["id"],
                }
            else:
                return {"success": False, "error": "Failed to reschedule task"}

        except Exception as e:
            logger.error(f"Error rescheduling task: {e}")
            return {"success": False, "error": f"Failed to reschedule task: {str(e)}"}

    async def _execute_add_notes(
        self, data: Dict[str, Any], user_id: str
    ) -> Dict[str, Any]:
        """Execute adding notes to a task."""
        try:
            # Find the task
            task = await self._find_task_by_title(data["task_title"])
            if not task:
                return {
                    "success": False,
                    "error": f"Task '{data['task_title']}' not found",
                }

            # Append notes
            current_notes = task.get("notes", "")
            new_notes = data["notes"]
            combined_notes = f"{current_notes}\n{new_notes}".strip()

            # Update task
            update_data = {
                "notes": combined_notes,
                "updated_at": datetime.utcnow().isoformat(),
                "updated_by": user_id,
            }

            response = await self._safe_db_operation(
                self.supabase.table("tasks")
                .update(update_data)
                .eq("id", task["id"])
                .execute()
            )

            if response and response.data:
                return {
                    "success": True,
                    "message": f"Notes added to task '{task['title']}'",
                    "task_id": task["id"],
                }
            else:
                return {"success": False, "error": "Failed to add notes to task"}

        except Exception as e:
            logger.error(f"Error adding notes to task: {e}")
            return {"success": False, "error": f"Failed to add notes: {str(e)}"}

    async def _execute_read(self, data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Execute task reading/listing."""
        try:
            # Build query
            query = self.supabase.table("tasks").select("*")

            # Apply filters
            filters = data.get("filters", {})

            if filters.get("assigned_to"):
                assignee_id = await self._resolve_user_id(filters["assigned_to"])
                if assignee_id:
                    query = query.eq("assigned_to", assignee_id)

            if filters.get("status"):
                query = query.eq("status", filters["status"])

            if filters.get("priority"):
                query = query.eq("priority", filters["priority"])

            if filters.get("site_name"):
                query = query.eq("site_name", filters["site_name"])

            # Execute query
            response = await self._safe_db_operation(query.execute())

            if response and response.data is not None:
                tasks = response.data

                if not tasks:
                    return {
                        "success": True,
                        "message": "No tasks found matching your criteria",
                        "tasks": [],
                    }

                # Format task list
                formatted_tasks = []
                for task in tasks:
                    formatted_tasks.append(
                        {
                            "id": task["id"],
                            "title": task["title"],
                            "status": task["status"],
                            "priority": task["priority"],
                            "assigned_to": task.get("assigned_to"),
                            "due_date": task.get("due_date"),
                            "description": task.get("description", "")[
                                :100
                            ],  # Truncate
                        }
                    )

                return {
                    "success": True,
                    "message": f"Found {len(tasks)} task(s)",
                    "tasks": formatted_tasks,
                    "count": len(tasks),
                }
            else:
                return {"success": False, "error": "Failed to retrieve tasks"}

        except Exception as e:
            logger.error(f"Error reading tasks: {e}")
            return {"success": False, "error": f"Failed to read tasks: {str(e)}"}

    async def _find_task_by_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Find a task by title (case-insensitive)."""
        try:
            response = await self._safe_db_operation(
                self.supabase.table("tasks")
                .select("*")
                .ilike("title", f"%{title}%")
                .limit(1)
                .execute()
            )

            if response and response.data:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Error finding task: {e}")
            return None

    async def _resolve_user_id(self, username: str) -> Optional[str]:
        """Resolve username or alias to user ID."""
        try:
            # Check cache first
            cache_key = f"user:{username.lower()}"
            cached = self._get_cached(cache_key)
            if cached:
                return cached

            # Query personnel table
            response = await self._safe_db_operation(
                self.supabase.table("personnel")
                .select("id, first_name, aliases")
                .eq("is_active", True)
                .execute()
            )

            if response and response.data:
                for user in response.data:
                    if user["first_name"].lower() == username.lower():
                        self._set_cache(cache_key, user["id"])
                        return user["id"]

                    if user.get("aliases"):
                        for alias in user["aliases"]:
                            if alias.lower() == username.lower():
                                self._set_cache(cache_key, user["id"])
                                return user["id"]

            return None

        except Exception as e:
            logger.error(f"Error resolving user: {e}")
            return None

    def _parse_date(self, date_str: str) -> str:
        """Parse date string to ISO format."""
        date_str_lower = date_str.lower()

        # Handle relative dates
        if date_str_lower == "today":
            return datetime.utcnow().date().isoformat()
        elif date_str_lower == "tomorrow":
            return (datetime.utcnow() + timedelta(days=1)).date().isoformat()
        elif "next week" in date_str_lower:
            return (datetime.utcnow() + timedelta(days=7)).date().isoformat()
        elif "next month" in date_str_lower:
            return (datetime.utcnow() + timedelta(days=30)).date().isoformat()

        # Try to parse as ISO date
        try:
            parsed = datetime.fromisoformat(date_str)
            return parsed.date().isoformat()
        except Exception:
            pass

        # Default to original string and let database handle it
        return date_str
