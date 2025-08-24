"""Enhanced keyword-based router with synonym library and confidence scoring."""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RouteResult:
    """Result of routing decision."""

    entity_type: Optional[str]  # 'lists', 'field_reports', 'tasks', None
    operation: Optional[str]  # Specific operation like 'add_items', 'complete', etc.
    function_name: Optional[str]  # Function to restrict LLM to
    confidence: float  # 0.0 to 1.0
    extracted_data: Dict[str, Any] = field(default_factory=dict)
    use_direct_execution: bool = False  # Skip function calling for high confidence
    target_users: List[str] = field(default_factory=list)  # Extracted user assignments
    # Separate confidence scores for different aspects
    entity_confidence: Optional[float] = None  # Confidence in entity type detection
    operation_confidence: Optional[float] = None  # Confidence in operation detection
    assignee_confidence: Optional[float] = None  # Confidence in assignee extraction
    _match_length: int = 0  # Internal field for tiebreaker comparisons


class SynonymLibrary:
    """Maps natural language variations to canonical terms."""

    def __init__(self):
        self.synonyms = {
            # Action synonyms
            "show": [
                "show",
                "print",
                "list",
                "display",
                "view",
                "what's",
                "what is",
                "what are",
                "get",
                "fetch",
                "see",
                "check",
                "review",
                "look at",
            ],
            "create": [
                "create",
                "make",
                "new",
                "add",
                "start",
                "begin",
                "init",
                "build",
                "generate",
                "setup",
                "establish",
            ],
            "add_items": [
                "add to",
                "append to",
                "include in",
                "put on",
                "needs",
                "should have",
                "add",
                "include",
                "insert",
                "throw on",
                "tack on",
                "also need",
            ],
            "remove_items": [
                "remove from",
                "take off",
                "delete from",
                "take out",
                "doesn't need",
                "don't need",
                "remove",
                "drop",
                "strike",
                "cross off",
                "scratch",
                "pull",
            ],
            "complete": [
                "complete",
                "finish",
                "done with",
                "done",
                "mark complete",
                "mark done",
                "check off",
                "tick",
                "finished",
                "completed",
                "close",
                "resolve",
                "accomplish",
            ],
            "assign": [
                "assign to",
                "assigned to",
                "for",
                "assign",
                "give to",
                "hand to",
                "delegate to",
                "allocate to",
            ],
            "reassign": [
                "reassign to",
                "transfer to",
                "move to",
                "give to",
                "hand off to",
                "switch to",
                "change owner to",
            ],
            "delete": [
                "delete",
                "remove",
                "trash",
                "destroy",
                "kill",
                "drop",
                "erase",
                "eliminate",
                "purge",
                "wipe",
            ],
            # Ownership terms
            "my": ["my", "mine", "me", "i", "personal", "own"],
            # Entity synonyms
            "task": [
                "task",
                "todo",
                "item",
                "job",
                "assignment",
                "work",
                "action",
                "duty",
                "chore",
            ],
            "reminder": [
                "reminder",
                "remind",
                "alert",
                "notification",
                "notice",
                "ping",
            ],
            "list": ["list", "checklist", "items", "things", "inventory", "collection"],
            # Time references (enhanced from temporal processor insights)
            "today": ["today", "this day", "now", "current day"],
            "tomorrow": ["tomorrow", "next day", "tmr", "tmrw", "tom"],
            "week": ["week", "7 days", "this week", "next week", "weekly"],
            "hour": ["hour", "hr", "hours", "hrs"],
            "minute": ["minute", "min", "minutes", "mins"],
        }

        # User aliases - will be loaded from database
        self.user_aliases = {}
        self._personnel_cache = {}
        self._cache_timestamp = None
        self._cache_duration = timedelta(minutes=15)

    async def load_user_aliases(self, supabase_client):
        """Load user aliases from existing personnel table."""
        try:
            response = (
                await supabase_client.table("personnel")
                .select("id, first_name, last_name, telegram_username, aliases")
                .eq("is_active", True)
                .execute()
            )

            for user in response.data:
                first_name = user["first_name"]
                telegram_username = user.get("telegram_username")
                aliases = user.get("aliases", [])

                # Use first_name as canonical username (lowercase)
                canonical_username = first_name.lower()

                # Map the canonical username to itself
                self.user_aliases[canonical_username] = canonical_username

                # Map each alias to the canonical username
                for alias in aliases:
                    self.user_aliases[alias.lower()] = canonical_username

                # Also map telegram username if it exists
                if telegram_username:
                    self.user_aliases[telegram_username.lower()] = canonical_username

            logger.info(f"Loaded {len(self.user_aliases)} user aliases")

        except Exception as e:
            logger.error(f"Failed to load user aliases: {e}")

    def resolve_user_mentions(self, message: str) -> List[str]:
        """Extract user mentions and resolve to canonical usernames."""
        users = []
        message_lower = message.lower()

        # Check for @ mentions first (use router's pre-compiled pattern if available)
        # Note: This method is part of SynonymLibrary, so we can't access router patterns directly
        # This is a legacy method that may not need optimization since preprocessing handles @mentions
        at_mentions = re.findall(r"@([a-zA-Z][a-zA-Z0-9._]*)", message)
        for mention in at_mentions:
            canonical = self.user_aliases.get(mention.lower())
            if canonical and canonical not in users:
                users.append(canonical)

        # Check for alias mentions in text
        for alias, username in self.user_aliases.items():
            if alias and username and alias in message_lower and username not in users:
                users.append(username)

        return users

    def get_synonyms(self, term: str) -> List[str]:
        """Get all synonyms for a term."""
        return self.synonyms.get(term, [term])

    def find_canonical_term(self, phrase: str) -> Optional[str]:
        """Find canonical term that matches phrase."""
        phrase_lower = phrase.lower()

        for canonical, synonyms in self.synonyms.items():
            for synonym in synonyms:
                if synonym in phrase_lower:
                    return canonical
        return None


class ConfidenceScorer:
    """Calculates confidence scores for routing decisions."""

    def __init__(self, synonym_library: SynonymLibrary):
        self.synonym_lib = synonym_library

    def calculate_confidence(
        self,
        message: str,
        entity_type: str,
        operation: str,
        keyword_match: re.Match,
        target_users: List[str],
    ) -> float:
        """Calculate confidence score based on multiple factors."""

        # Enhanced base confidence levels by operation explicitness
        base_confidence = {
            # Very high confidence - unambiguous operations
            "complete": 0.95,  # Very clear intent
            "reassign": 0.9,  # Clear delegation
            "delete": 0.85,  # Destructive but clear
            # High confidence - specific operations
            "add_items": 0.85,
            "remove_items": 0.85,
            "create": 0.8,
            "clear": 0.8,
            # Medium-high confidence
            "read": 0.75,
            "rename": 0.75,
            "reschedule": 0.75,
            "add_notes": 0.7,
            # Lower confidence - more ambiguous
            "update": 0.5,  # Generic update
            "interactive": 0.4,  # Need more context
        }.get(operation, 0.6)

        confidence = base_confidence

        # Position boost - earlier keywords are more intentional
        message_length = len(message)
        relative_position = keyword_match.start() / max(message_length, 1)

        if relative_position < 0.2:  # In first 20% of message
            confidence += 0.15
        elif relative_position < 0.4:  # In first 40%
            confidence += 0.1
        elif relative_position < 0.6:  # In first 60%
            confidence += 0.05

        # Keyword specificity boost
        keyword_text = keyword_match.group(0).lower()
        keyword_length = len(keyword_text)

        # Very specific multi-word phrases get higher boost
        if " " in keyword_text:  # Multi-word keyword
            confidence += 0.15
        elif keyword_length > 10:  # Long specific keyword
            confidence += 0.1
        elif keyword_length > 6:  # Medium keyword
            confidence += 0.05

        # User assignment boost - assignments increase confidence
        if target_users:
            confidence += 0.15  # User assignments are strong signals

            # @ mentions provide additional boost (explicit syntax)
            if "@" in message:
                confidence += 0.15  # Explicit @ syntax adds significant confidence

        # Enhanced context clues
        message_lower = message.lower()

        # Time references with task operations
        time_patterns = [
            r"\b(?:at|by|before|after)\s+\d+",  # at 3, by 5
            r"\b\d+(?:am|pm)\b",  # 3pm, 10am
            r"\b(?:tomorrow|today|tonight|yesterday)\b",
            r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b(?:next|this|last)\s+(?:week|month|year)\b",
            r"\b(?:morning|afternoon|evening|night)\b",
        ]

        time_match_count = sum(
            1 for pattern in time_patterns if re.search(pattern, message_lower)
        )
        if time_match_count > 0 and entity_type == "tasks":
            confidence += min(0.1 * time_match_count, 0.2)  # Cap at 0.2

        # List indicators
        list_indicators = [
            "," in message,  # Comma-separated items
            re.search(r"\band\b", message_lower),  # "milk and bread"
            re.search(r"\b(?:also|plus)\b", message_lower),  # "also eggs"
            message.count("\n") > 1,  # Multi-line lists
        ]

        if any(list_indicators) and entity_type == "lists":
            confidence += 0.1

        # Site-specific context for field reports
        site_names = ["eagle lake", "crockett", "mathis", "site", "location"]
        if (
            any(site in message_lower for site in site_names)
            and entity_type == "field_reports"
        ):
            confidence += 0.15

        # Question words reduce confidence (might be a query, not an action)
        question_words = ["what", "when", "where", "who", "how", "why", "which"]
        if any(word in message_lower.split() for word in question_words):
            confidence -= 0.15

        # Ambiguity penalties
        ambiguous_words = ["maybe", "might", "possibly", "could", "should i", "can you"]
        if any(word in message_lower for word in ambiguous_words):
            confidence -= 0.2

        # Imperative mood boost (commands often start with verbs)
        imperative_verbs = [
            "add",
            "remove",
            "create",
            "delete",
            "show",
            "list",
            "complete",
            "finish",
        ]
        if any(message_lower.startswith(verb) for verb in imperative_verbs):
            confidence += 0.1

        # Explicit command indicators
        if message_lower.startswith(("please", "pls", "plz")):
            confidence += 0.05  # Polite command still a command

        return min(max(confidence, 0.0), 1.0)  # Clamp between 0-1


class KeywordRouter:
    """Enhanced router with synonym library and confidence scoring."""

    def __init__(self, supabase_client=None):
        self.supabase_client = supabase_client
        self.synonym_lib = SynonymLibrary()
        self.confidence_scorer = ConfidenceScorer(self.synonym_lib)
        self._aliases_loaded = False
        self._aliases_loading = None

        # Memory optimization: Enhanced cache management
        self._recent_routes = {}  # LRU cache for recent routes
        self._max_cache_size = 50  # Reduced from 100
        self._cache_ttl = 1800  # 30 minutes TTL
        self._cache_timestamps = {}

        # Specific operations replacing generic "update"
        self.operations = {
            "lists": {
                "create": {
                    "keywords": [
                        "new list",
                        "create list",
                        "make list",
                        "start list",
                        "build list",
                        "create shopping list",
                        "create grocery list",
                        "make a list",
                        "start a list",
                        "begin list",
                        "list for",
                        "list of",
                    ],
                    "function": "create_list",
                    "example": "new list called grocery items",
                },
                "read": {
                    "keywords": [
                        "show list",
                        "print list",
                        "read list",
                        "what's on",
                        "what is on",
                        "display list",
                        "view list",
                        "get list",
                        "see list",
                        "check list",
                        "review list",
                        "list contents",
                        "what's in",
                    ],
                    "function": "read_list",
                    "example": "show list grocery items",
                },
                "add_items": {
                    "keywords": [
                        "add to list",
                        "append to list",
                        "include in list",
                        "put on list",
                        "list needs",
                        "add",
                        "append",
                        "we need",
                        "also need",
                        "don't forget",
                        "include",
                        "put down",
                        "write down",
                        "add item",
                        "add items",
                    ],
                    "function": "update_list",
                    "example": "add milk to grocery items list",
                },
                "remove_items": {
                    "keywords": [
                        "remove from list",
                        "remove from",
                        "take off list",
                        "take off",
                        "delete from list",
                        "take out",
                        "remove",
                        "strike from",
                        "cross off",
                        "scratch off",
                        "we have",
                        "got",
                        "already have",
                        "don't need",
                        "no longer need",
                    ],
                    "function": "update_list",
                    "example": "remove milk from grocery items list",
                },
                "rename": {
                    "keywords": [
                        "rename list",
                        "change list name",
                        "call list",
                        "rename to",
                        "change name to",
                        "update list name",
                        "retitle list",
                    ],
                    "function": "update_list",
                    "example": "rename list to shopping items",
                },
                "clear": {
                    "keywords": [
                        "clear list",
                        "empty list",
                        "remove all",
                        "wipe list",
                        "reset list",
                        "start over",
                        "clean list",
                        "delete everything",
                        "remove everything",
                    ],
                    "function": "update_list",
                    "example": "clear grocery items list",
                },
                "delete": {
                    "keywords": [
                        "delete list",
                        "remove list",
                        "trash list",
                        "destroy list",
                        "eliminate list",
                        "get rid of list",
                        "purge list",
                    ],
                    "function": "delete_list",
                    "example": "delete list grocery items",
                    "requires_admin": True,
                },
            },
            "tasks": {
                "create": {
                    "keywords": [
                        "new task",
                        "create task",
                        "add task",
                        "remind me",
                        "task for",
                        "need to",
                        "have to",
                        "must",
                        "should",
                        "todo",
                        "to do",
                        "reminder",
                        "don't forget",
                        "remember to",
                        "make sure",
                    ],
                    "function": "create_task",
                    "example": "new task check generator oil tomorrow at 3pm",
                },
                "read": {
                    "keywords": [
                        "show tasks",
                        "list tasks",
                        "what tasks",
                        "my tasks",
                        "tasks for",
                        "show my todos",
                        "what's on my plate",
                        "what do i have",
                        "pending tasks",
                        "active tasks",
                        "open tasks",
                    ],
                    "function": "list_tasks",
                    "example": "show tasks for this week",
                },
                "complete": {
                    "keywords": [
                        "mark complete",
                        "mark as complete",
                        "finish task",
                        "done with",
                        "task complete",
                        "complete",
                        "completed",
                        "finished",
                        "done",
                        "completed task",
                        "task done",
                        "check off",
                        "mark as done",
                        "close task",
                        "resolved",
                    ],
                    "function": "update_task",
                    "example": "mark complete generator maintenance task",
                },
                "reassign": {
                    "keywords": [
                        "reassign to",
                        "assign to",
                        "assign",
                        "give to",
                        "transfer to",
                        "hand to",
                        "switch to",
                        "delegate to",
                        "pass to",
                        "hand off",
                        "change owner to",
                    ],
                    "function": "update_task",
                    "example": "reassign generator task to Joel",
                },
                "reschedule": {
                    "keywords": [
                        "reschedule to",
                        "move to",
                        "change date",
                        "push to",
                        "defer to",
                        "postpone to",
                        "delay to",
                        "bump to",
                        "shift to",
                        "change time",
                    ],
                    "function": "update_task",
                    "example": "reschedule oil check to next week",
                },
                "add_notes": {
                    "keywords": [
                        "add note to",
                        "note on",
                        "update with",
                        "add details",
                        "add comment",
                        "annotate",
                        "add info",
                        "note that",
                        "update notes",
                    ],
                    "function": "update_task",
                    "example": "add note to generator task: found leak",
                },
            },
            "field_reports": {
                "create": {
                    "keywords": [
                        "new field report",
                        "create field report",
                        "field report for",
                        "report for",
                    ],
                    "function": "create_field_report",
                    "example": "new field report for Eagle Lake: generator maintenance completed",
                },
                "read": {
                    "keywords": [
                        "show field report",
                        "latest field report",
                        "read field report",
                        "reports for",
                    ],
                    "function": "read_field_report",
                    "example": "show latest field report for Eagle Lake",
                },
                "add_followups": {
                    "keywords": [
                        "add followup",
                        "followup for",
                        "action item",
                        "needs followup",
                    ],
                    "function": "update_field_report",
                    "example": "add followup to Eagle Lake report: schedule inspection",
                },
                "update_status": {
                    "keywords": [
                        "mark report",
                        "report status",
                        "finalize report",
                        "draft report",
                    ],
                    "function": "update_field_report",
                    "example": "mark Eagle Lake report as final",
                },
            },
        }

        # Telegram command mappings for performance optimization
        self.telegram_commands = {
            "/tnr": "tasks",  # Tasks and reminders
            "/lists": "lists",  # List operations
            "/fr": "field_reports",  # Field reports
            "/l": "lists",  # Shorthand
            "/t": "tasks",  # Shorthand
        }

        # Hidden direct commands (100% confidence operations)
        self.hidden_commands = {
            "/newlist": ("lists", "create"),
            "/addtolist": ("lists", "add_items"),
            "/removefromlist": ("lists", "remove_items"),
            "/showlist": ("lists", "read"),
            "/newtask": ("tasks", "create"),
            "/newreminder": ("tasks", "create"),
            "/completetask": ("tasks", "complete"),
            "/reassigntask": ("tasks", "reassign"),
            "/showtasks": ("tasks", "read"),
            "/showmytasks": ("tasks", "read"),
            "/showmyreminders": ("tasks", "read"),
        }

        # Compile regex patterns for efficiency (after operations are defined)
        self._compile_patterns()
        self._compile_preprocessing_patterns()

    async def ensure_aliases_loaded(self):
        """Ensure aliases are loaded before use."""
        if self._aliases_loaded:
            return

        if self._aliases_loading:
            # Wait for existing load to complete
            await self._aliases_loading
            return

        # Start loading
        self._aliases_loading = self._load_aliases()
        await self._aliases_loading

    async def _load_aliases(self):
        """Load aliases with error handling."""
        try:
            if self.supabase_client:
                await self.synonym_lib.load_user_aliases(self.supabase_client)
            self._aliases_loaded = True
        except Exception as e:
            logger.error(f"Failed to load aliases: {e}")
            # Continue without aliases rather than crash
        finally:
            self._aliases_loading = None

    def _compile_patterns(self):
        """Pre-compile regex patterns for faster matching."""
        self.patterns = {}
        for entity_type, operations in self.operations.items():
            self.patterns[entity_type] = {}
            for operation, config in operations.items():
                # Sort keywords by length (longest first) to match more specific phrases first
                # This ensures "add task" matches before "add"
                sorted_keywords = sorted(config["keywords"], key=len, reverse=True)
                keywords_pattern = "|".join(re.escape(kw) for kw in sorted_keywords)
                self.patterns[entity_type][operation] = re.compile(
                    rf"\b({keywords_pattern})\b", re.IGNORECASE
                )

    def _compile_preprocessing_patterns(self):
        """Pre-compile preprocessing patterns for performance."""
        # Compile all regex patterns once
        self._at_mention_pattern = re.compile(r"@([a-zA-Z][a-zA-Z0-9._]*)")
        self._command_pattern = re.compile(r"/(\w+)")
        self._whitespace_pattern = re.compile(r"\s+")
        self._name_pattern = re.compile(
            r'(?:called|named)\s+["\']?([^"\'\.]+)["\']?', re.IGNORECASE
        )
        self._time_pattern = re.compile(
            r"(tomorrow|today|next week|at \d+[ap]m)", re.IGNORECASE
        )

        # Entity extraction patterns
        self._list_name_pattern = re.compile(
            r'(?:called|named)\s+["\']?([^"\'\.]+)["\']?', re.IGNORECASE
        )
        self._items_pattern = re.compile(
            r"(?:add|remove)\s+(.+?)\s+(?:to|from)", re.IGNORECASE
        )
        self._site_pattern = re.compile(r"(eagle lake|crockett|mathis)", re.IGNORECASE)
        self._time_ref_pattern = re.compile(
            r"(tomorrow|today|next week|at \d+[ap]m)", re.IGNORECASE
        )

        # UUID validation pattern
        self._uuid_pattern = re.compile(
            r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$",
            re.IGNORECASE,
        )

    def preprocess_message(
        self, message: str
    ) -> Tuple[str, Dict[str, Any], Dict[str, float]]:
        """Extract deterministic syntax markers before routing.

        Phase 2.1 Enhancement: 100% confidence extraction of @mentions and /commands
        before any LLM processing. This ensures deterministic behavior for explicit syntax.

        Returns:
            Tuple of (cleaned_message, prefilled_data, confidence_scores)
            - cleaned_message: Message with extracted syntax removed
            - prefilled_data: Extracted entities with 100% confidence
            - confidence_scores: Individual confidence scores for each extraction
        """
        if not message:
            return "", {}, {}

        # Track what we've extracted for logging
        extracted_elements = []

        # Memory optimization: Use string interning and avoid temporary strings
        prefilled = {}
        confidences = {}
        cleaned_message = message

        # Extract @mentions with validation using pre-compiled pattern
        # T2.1.1: 100% confidence extraction for @mentions
        at_mentions = self._at_mention_pattern.findall(message)
        if at_mentions:
            valid_users = []
            invalid_mentions = []  # Track invalid mentions for potential LLM processing

            for mention in at_mentions:
                mention_lower = mention.lower()
                canonical = self.synonym_lib.user_aliases.get(mention_lower)
                if canonical and canonical not in valid_users:
                    valid_users.append(canonical)
                    extracted_elements.append(f"@{mention} -> {canonical}")
                elif not canonical:
                    # Store invalid mentions for context
                    invalid_mentions.append(mention)

                # Always remove @mentions from message for clean LLM input
                cleaned_message = cleaned_message.replace(f"@{mention}", "")

            if valid_users:
                prefilled["assignee"] = (
                    valid_users[0] if len(valid_users) == 1 else valid_users
                )
                confidences["assignee_confidence"] = (
                    1.0  # 100% confidence for explicit @mentions
                )
                prefilled["extraction_type"] = "explicit_mention"

            if invalid_mentions:
                prefilled["unresolved_mentions"] = invalid_mentions

        # Extract /commands using pre-compiled pattern
        # T2.1.1: 100% confidence extraction for /commands
        command_match = self._command_pattern.search(message)
        if command_match:
            command = command_match.group(1).lower()
            extracted_elements.append(f"/{command}")

            # Entity type commands with 100% confidence
            if command in ["lists", "list", "l"]:
                prefilled["entity_type"] = "lists"
                confidences["entity_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
            elif command in ["tasks", "task", "remind", "t", "tnr"]:
                prefilled["entity_type"] = "tasks"
                confidences["entity_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
            elif command in ["reports", "report", "fr"]:
                prefilled["entity_type"] = "field_reports"
                confidences["entity_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"

            # Operation commands with 100% confidence for both entity and operation
            elif command in ["newlist", "addlist"]:
                prefilled["entity_type"] = "lists"
                prefilled["operation"] = "create"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True  # Mark for direct execution
            elif command in ["newtask", "newreminder"]:
                prefilled["entity_type"] = "tasks"
                prefilled["operation"] = "create"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True
            elif command == "addtolist":
                prefilled["entity_type"] = "lists"
                prefilled["operation"] = "add_items"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True
            elif command == "removefromlist":
                prefilled["entity_type"] = "lists"
                prefilled["operation"] = "remove_items"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True
            elif command == "showlist":
                prefilled["entity_type"] = "lists"
                prefilled["operation"] = "read"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True
            elif command in ["showtasks", "showmytasks", "showmyreminders"]:
                prefilled["entity_type"] = "tasks"
                prefilled["operation"] = "read"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True
            elif command == "completetask":
                prefilled["entity_type"] = "tasks"
                prefilled["operation"] = "complete"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True
            elif command == "reassigntask":
                prefilled["entity_type"] = "tasks"
                prefilled["operation"] = "reassign"
                confidences["entity_confidence"] = 1.0
                confidences["operation_confidence"] = 1.0
                prefilled["command_source"] = f"/{command}"
                prefilled["direct_execution"] = True

            # Remove the command from the message for clean LLM input
            cleaned_message = cleaned_message.replace(
                command_match.group(0), ""
            ).strip()

        # Extract additional deterministic patterns before LLM processing
        # T2.1.1: Extract time references with high confidence
        time_matches = self._time_pattern.findall(cleaned_message)
        if time_matches:
            prefilled["time_references"] = time_matches
            prefilled["has_temporal_context"] = True

        # T2.1.1: Extract site references for field reports
        site_matches = self._site_pattern.findall(cleaned_message)
        if site_matches:
            # Normalize site names to title case
            prefilled["site_references"] = [site.title() for site in site_matches]
            if len(site_matches) == 1:
                prefilled["site"] = site_matches[0].title()

        # Clean up multiple spaces and trim - use simple string ops instead of regex
        cleaned_message = " ".join(cleaned_message.split())

        # Log extracted elements for debugging
        if extracted_elements:
            logger.debug(f"Preprocessing extracted: {', '.join(extracted_elements)}")
            prefilled["preprocessing_extractions"] = extracted_elements

        return cleaned_message, prefilled, confidences

    def route(self, message: str) -> RouteResult:
        """Enhanced routing with synonym library and confidence scoring."""
        if not message or not isinstance(message, str):
            return RouteResult(None, None, None, 0.0)

        # Check for malformed slash commands (but allow natural language)
        if message.startswith("/") and not re.match(r"^/\w+", message):
            return RouteResult(None, None, None, 0.0)

        # Memory optimization: Enhanced cache management
        cache_key = hash(message)

        # Clean expired cache entries
        self._cleanup_expired_cache()

        if cache_key in self._recent_routes:
            # Check if cache is still valid
            if time.time() - self._cache_timestamps.get(cache_key, 0) < self._cache_ttl:
                return self._recent_routes[cache_key]

        # Note: This is sync, so we can't await. Document that aliases
        # should be loaded before routing for user resolution to work.
        if not self._aliases_loaded and self.supabase_client:
            logger.warning(
                "Routing without user aliases loaded. Call ensure_aliases_loaded() first."
            )

        # First, preprocess the message to extract deterministic syntax
        cleaned_message, prefilled_data, confidences = self.preprocess_message(message)
        message_lower = cleaned_message.lower()

        # T2.1.1: Direct execution path for 100% confidence routes
        # If we have high confidence prefilled data from preprocessing, use it
        if prefilled_data.get("entity_type") and prefilled_data.get("operation"):
            entity_type = prefilled_data["entity_type"]
            operation = prefilled_data["operation"]
            config = self.operations.get(entity_type, {}).get(operation, {})

            # Calculate combined confidence
            combined_confidence = min(
                confidences.get("entity_confidence", 1.0),
                confidences.get("operation_confidence", 1.0),
            )

            # T2.1.1: Use direct execution for 100% confidence (bypass LLM)
            use_direct = (
                prefilled_data.get("direct_execution", False)
                or combined_confidence == 1.0
            )

            return RouteResult(
                entity_type=entity_type,
                operation=operation,
                function_name=config.get("function"),
                confidence=combined_confidence,
                extracted_data={
                    **self._extract_data(
                        cleaned_message, entity_type, operation, message_lower
                    ),
                    **prefilled_data,
                    "cleaned_message": cleaned_message,  # Include cleaned message for LLM
                },
                use_direct_execution=use_direct,
                target_users=(
                    [prefilled_data["assignee"]]
                    if isinstance(prefilled_data.get("assignee"), str)
                    else prefilled_data.get("assignee", [])
                ),
                entity_confidence=confidences.get("entity_confidence"),
                operation_confidence=confidences.get("operation_confidence"),
                assignee_confidence=confidences.get("assignee_confidence"),
            )

        best_match = RouteResult(None, None, None, 0.0)

        # Use prefilled assignee if available
        target_users = []
        if "assignee" in prefilled_data:
            if isinstance(prefilled_data["assignee"], str):
                target_users = [prefilled_data["assignee"]]
            else:
                target_users = prefilled_data["assignee"]
        else:
            # Fall back to old extraction method for non-@ mentions
            target_users = self.synonym_lib.resolve_user_mentions(cleaned_message)

        # Check for hidden commands anywhere in cleaned message (100% confidence)
        for cmd, (entity_type, operation) in self.hidden_commands.items():
            if cmd in message_lower:
                config = self.operations[entity_type][operation]
                return RouteResult(
                    entity_type=entity_type,
                    operation=operation,
                    function_name=config["function"],
                    confidence=1.0,
                    extracted_data={
                        **self._extract_data(
                            cleaned_message, entity_type, operation, message_lower
                        ),
                        **prefilled_data,
                    },
                    use_direct_execution=True,  # Always direct for hidden commands
                    target_users=target_users,
                    entity_confidence=1.0,  # Hidden commands have 100% confidence
                    operation_confidence=1.0,
                    assignee_confidence=confidences.get("assignee_confidence"),
                )

        # Check for Telegram commands (category routing with boost)
        telegram_boost = 0.0
        forced_entity_type = prefilled_data.get(
            "entity_type"
        )  # Use prefilled entity if available

        # Only check for telegram commands if we don't already have an entity type
        if not forced_entity_type:
            for cmd, entity_type in self.telegram_commands.items():
                if cmd in message_lower:
                    forced_entity_type = entity_type
                    telegram_boost = 0.3  # Same boost regardless of position
                    break

        # Check each entity type and operation
        for entity_type, operations in self.operations.items():
            # Skip if we have a forced entity type and this isn't it
            if forced_entity_type and entity_type != forced_entity_type:
                continue

            for operation, config in operations.items():
                pattern = self.patterns[entity_type][operation]
                match = pattern.search(message_lower)

                if match:
                    # Calculate enhanced confidence
                    base_confidence = self.confidence_scorer.calculate_confidence(
                        cleaned_message, entity_type, operation, match, target_users
                    )

                    # Apply telegram boost
                    confidence = min(base_confidence + telegram_boost, 1.0)

                    # Reduce confidence for uncertain language
                    uncertainty_words = [
                        "maybe",
                        "possibly",
                        "perhaps",
                        "could",
                        "might",
                        "what about",
                    ]
                    for word in uncertainty_words:
                        if word in message_lower:
                            confidence = max(confidence * 0.7, 0.3)
                            break

                    # Reduce confidence for questions
                    if any(
                        word in message_lower
                        for word in ["what", "when", "who", "where", "why", "how"]
                    ):
                        if message_lower.endswith("?") or message_lower.startswith(
                            ("what", "when", "who", "where", "why", "how")
                        ):
                            confidence = max(confidence * 0.8, 0.4)

                    # Boost reschedule confidence when temporal context is present
                    # This helps "move to next week" route to reschedule instead of reassign
                    if operation == "reschedule" and prefilled_data.get(
                        "has_temporal_context"
                    ):
                        confidence = min(confidence + 0.2, 1.0)

                    # Penalize reassign when temporal context is present but no user mention
                    # This helps avoid mis-routing "move to next week" to reassign
                    if (
                        operation == "reassign"
                        and prefilled_data.get("has_temporal_context")
                        and not target_users
                    ):
                        confidence = max(confidence - 0.3, 0.3)

                    # Boost complete confidence when "mark" appears near "complete"
                    # This helps complex phrases like "mark ... as complete and assign..."
                    if operation == "complete" and "mark" in message_lower:
                        confidence = min(confidence + 0.15, 1.0)

                    # Special case: "mark ... as complete" pattern
                    if (
                        entity_type == "tasks"
                        and "mark" in message_lower
                        and "as complete" in message_lower
                    ):
                        if operation == "complete":
                            confidence = min(confidence + 0.5, 1.0)
                        elif operation == "reassign":
                            confidence = max(confidence - 0.5, 0.2)

                    # Penalize reassign in compound commands where complete appears first
                    if operation == "reassign" and "complete" in message_lower:
                        complete_pos = message_lower.find("complete")
                        assign_pos = message_lower.find("assign")
                        if complete_pos < assign_pos and complete_pos != -1:
                            confidence = max(confidence - 0.4, 0.3)

                    # Context-based routing for "don't forget"
                    # "don't forget to" usually indicates a task/reminder
                    # "don't forget" alone might be a list item
                    if "don't forget" in message_lower:
                        if (
                            "don't forget to" in message_lower
                            or "don't forget we" in message_lower
                        ):
                            # This is likely a task/reminder
                            if entity_type == "tasks":
                                confidence = min(confidence + 0.3, 1.0)
                            elif entity_type == "lists":
                                confidence = max(confidence - 0.3, 0.3)
                        else:
                            # Could be either, slight preference for lists
                            if entity_type == "lists":
                                confidence = min(confidence + 0.1, 1.0)

                    # Prefer longer keyword matches when confidence is equal (tiebreaker)
                    # This ensures "add task" beats "add" when both have same confidence
                    match_length = len(match.group())
                    should_update = confidence > best_match.confidence or (
                        confidence == best_match.confidence
                        and match_length > getattr(best_match, "_match_length", 0)
                    )

                    if should_update:
                        best_match = RouteResult(
                            entity_type=entity_type,
                            operation=operation,
                            function_name=config["function"],
                            confidence=confidence,
                            extracted_data={
                                **self._extract_data(
                                    cleaned_message,
                                    entity_type,
                                    operation,
                                    message_lower,
                                ),
                                **prefilled_data,
                            },
                            use_direct_execution=(confidence >= 0.8),
                            target_users=target_users,
                            entity_confidence=confidences.get(
                                "entity_confidence", confidence
                            ),
                            operation_confidence=confidence,  # This is from keyword matching
                            assignee_confidence=confidences.get("assignee_confidence"),
                        )
                        # Store match length for tiebreaker comparisons
                        best_match._match_length = match_length

        # If we have a Telegram command but no operation match, still route to entity
        if forced_entity_type and best_match.entity_type is None:
            best_match = RouteResult(
                entity_type=forced_entity_type,
                operation="interactive",  # New operation type
                function_name=None,
                confidence=1.0,
                extracted_data={"telegram_command": True, **prefilled_data},
                use_direct_execution=False,  # Let LLM figure out the operation
                target_users=target_users,
                entity_confidence=confidences.get("entity_confidence", 1.0),
                operation_confidence=None,  # No operation detected
                assignee_confidence=confidences.get("assignee_confidence"),
            )

        # Memory optimization: Enhanced cache management
        self._recent_routes[cache_key] = best_match
        self._cache_timestamps[cache_key] = time.time()

        # Enforce cache size limit
        self._enforce_cache_size_limit()

        return best_match

    def _cleanup_expired_cache(self):
        """Remove expired cache entries."""
        current_time = time.time()
        expired_keys = [
            key
            for key, timestamp in self._cache_timestamps.items()
            if current_time - timestamp > self._cache_ttl
        ]

        for key in expired_keys:
            if key in self._recent_routes:
                del self._recent_routes[key]
            del self._cache_timestamps[key]

    def _enforce_cache_size_limit(self):
        """Enforce maximum cache size."""
        if len(self._recent_routes) > self._max_cache_size:
            # Remove oldest entries
            sorted_keys = sorted(
                self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k]
            )
            keys_to_remove = sorted_keys[: len(sorted_keys) - self._max_cache_size]

            for key in keys_to_remove:
                if key in self._recent_routes:
                    del self._recent_routes[key]
                if key in self._cache_timestamps:
                    del self._cache_timestamps[key]

    def _extract_data(
        self,
        message: str,
        entity_type: str,
        operation: str,
        message_lower: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extract relevant data from message based on entity type and operation."""
        data = {}
        if message_lower is None:
            message_lower = message.lower()

        if entity_type == "lists":
            if operation in ["create", "rename"]:
                # Extract list name after "called" or "named"
                name_match = self._list_name_pattern.search(message)
                if name_match:
                    data["suggested_name"] = name_match.group(1).strip()
                else:
                    # Try to extract a reasonable list name from context
                    # Look for words after "list" that aren't site names
                    list_match = re.search(r"\blist\s+(\w+)", message_lower)
                    if list_match:
                        potential_name = list_match.group(1)
                        # Don't use site names as list names
                        if potential_name not in [
                            "for",
                            "at",
                            "in",
                            "to",
                            "from",
                        ] and not self._site_pattern.search(potential_name):
                            data["suggested_name"] = potential_name

            elif operation in ["add_items", "remove_items"]:
                # Extract items after "add" or "remove"
                items_match = self._items_pattern.search(message)
                if items_match:
                    items_text = items_match.group(1)
                    # Split on commas and clean up
                    items = [item.strip() for item in items_text.split(",")]
                    data["items"] = items

        elif entity_type == "field_reports":
            # Extract site name using pre-compiled pattern
            site_match = self._site_pattern.search(message_lower)
            if site_match:
                data["site"] = site_match.group(1).title()

        elif entity_type == "tasks":
            if operation == "create":
                # Extract time references using pre-compiled pattern
                time_match = self._time_ref_pattern.search(message)
                if time_match:
                    data["time_reference"] = time_match.group(1)

        return data
