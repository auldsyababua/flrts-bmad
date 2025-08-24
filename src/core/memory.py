"""
Memory layer for the bot using mem0 for persistent, intelligent memory management.
Enables the bot to remember user preferences, learn from corrections, and provide
personalized responses based on past interactions.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mem0 import Memory

from .memory_webhooks import MemoryWebhookEvent, memory_webhook_handler

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class BotMemory:
    """Manages bot memory using mem0 for intelligent, persistent storage."""

    def __init__(self):
        """Initialize mem0 memory with Vector and optional Graph backend."""
        try:
            config = {"version": os.getenv("MEM0_MEMORY_VERSION", "v1.1")}

            # Configure LLM (required for mem0's intelligent extraction)
            if os.getenv("OPENAI_API_KEY"):
                config["llm"] = {
                    "provider": "openai",
                    "config": {
                        "model": os.getenv("MEM0_LLM_MODEL", "gpt-4o-mini"),
                        "api_key": os.getenv("OPENAI_API_KEY"),
                        "temperature": float(os.getenv("MEM0_LLM_TEMPERATURE", "0.1")),
                        "max_tokens": int(os.getenv("MEM0_LLM_MAX_TOKENS", "1000")),
                    },
                }

            # Configure Embedder
            if os.getenv("OPENAI_API_KEY"):
                config["embedder"] = {
                    "provider": "openai",
                    "config": {
                        "model": os.getenv(
                            "MEM0_EMBEDDER_MODEL", "text-embedding-3-small"
                        ),
                        "api_key": os.getenv("OPENAI_API_KEY"),
                        "embedding_dims": int(os.getenv("MEM0_EMBEDDING_DIMS", "1536")),
                    },
                }

            # Configure Vector Store
            if os.getenv("UPSTASH_VECTOR_REST_URL") and os.getenv(
                "UPSTASH_VECTOR_REST_TOKEN"
            ):
                # Use Upstash Vector for production
                config["vector_store"] = {
                    "provider": "upstash_vector",
                    "config": {
                        "url": os.getenv("UPSTASH_VECTOR_REST_URL"),
                        "token": os.getenv("UPSTASH_VECTOR_REST_TOKEN"),
                        "collection_name": os.getenv(
                            "MEM0_COLLECTION_NAME", "markdown_bot_memories"
                        ),
                        "enable_embeddings": os.getenv(
                            "MEM0_ENABLE_HYBRID_SEARCH", "true"
                        ).lower()
                        == "true",
                    },
                }
                logger.info("Using Upstash Vector for mem0 backend")

            # Configure Graph Store (optional - for relationship mapping)
            if os.getenv("NEO4J_URL") and os.getenv("NEO4J_PASSWORD"):
                graph_config = {
                    "provider": "neo4j",
                    "config": {
                        "url": os.getenv("NEO4J_URL", "bolt://localhost:7687"),
                        "username": os.getenv("NEO4J_USERNAME", "neo4j"),
                        "password": os.getenv("NEO4J_PASSWORD"),
                    },
                }

                # Add custom graph prompt if provided
                graph_prompt = os.getenv("MEM0_GRAPH_CUSTOM_PROMPT")
                if graph_prompt:
                    graph_config["custom_prompt"] = graph_prompt

                config["graph_store"] = graph_config
                logger.info("Using Neo4j for graph memory backend")
                self.has_graph = True
            else:
                self.has_graph = False

            # Configure memory settings
            if os.getenv("MEM0_MEMORY_THRESHOLD"):
                config["memory_threshold"] = float(os.getenv("MEM0_MEMORY_THRESHOLD"))

            # Configure cache settings for performance
            cache_config = {
                "similarity_evaluation": {
                    "strategy": os.getenv("MEM0_CACHE_STRATEGY", "distance"),
                    "max_distance": float(os.getenv("MEM0_CACHE_MAX_DISTANCE", "1.0")),
                },
                "config": {
                    "similarity_threshold": float(
                        os.getenv("MEM0_CACHE_SIMILARITY_THRESHOLD", "0.8")
                    ),
                    "auto_flush": int(os.getenv("MEM0_CACHE_AUTO_FLUSH", "50")),
                },
            }
            config["cache"] = cache_config

            # Configure chunking
            config["chunker"] = {
                "chunk_size": int(os.getenv("MEM0_CHUNK_SIZE", "2000")),
                "chunk_overlap": int(os.getenv("MEM0_CHUNK_OVERLAP", "100")),
                "length_function": "len",
                "min_chunk_size": int(os.getenv("MEM0_MIN_CHUNK_SIZE", "50")),
            }

            # Configure memory search settings
            config["memory"] = {
                "top_k": int(os.getenv("MEM0_VECTOR_TOP_K", "10")),
            }

            # Configure custom prompts
            if os.getenv("MEM0_CUSTOM_FACT_EXTRACTION_PROMPT"):
                config["custom_fact_extraction_prompt"] = os.getenv(
                    "MEM0_CUSTOM_FACT_EXTRACTION_PROMPT"
                )

            if os.getenv("MEM0_CUSTOM_UPDATE_MEMORY_PROMPT"):
                config["custom_update_memory_prompt"] = os.getenv(
                    "MEM0_CUSTOM_UPDATE_MEMORY_PROMPT"
                )

            # Configure history database
            if os.getenv("MEM0_HISTORY_DB_PATH"):
                config["history_db_path"] = os.path.expanduser(
                    os.getenv("MEM0_HISTORY_DB_PATH")
                )

            # Disable history if requested
            if os.getenv("MEM0_DISABLE_HISTORY", "false").lower() == "true":
                config["disable_history"] = True

            # Configure webhook if provided
            self.webhook_url = os.getenv("MEM0_WEBHOOK_URL")
            self.webhook_headers: Dict[str, str] = {}
            if self.webhook_url:
                webhook_token = os.getenv("MEM0_WEBHOOK_TOKEN")
                if webhook_token:
                    self.webhook_headers = {"Authorization": f"Bearer {webhook_token}"}
                logger.info(f"Webhook configured: {self.webhook_url}")

            # Initialize mem0 with config
            if "vector_store" in config or "graph_store" in config:
                self.memory = Memory.from_config(config)
                logger.info("BotMemory initialized with custom configuration")
            else:
                # Fallback to local memory for development
                self.memory = Memory()
                logger.info(
                    "Using local memory for mem0 (no backend credentials found)"
                )

            # Store performance settings
            self.batch_operations = (
                os.getenv("MEM0_BATCH_OPERATIONS", "true").lower() == "true"
            )
            self.batch_size = int(os.getenv("MEM0_BATCH_SIZE", "50"))
            self.parallel_processing = (
                os.getenv("MEM0_PARALLEL_PROCESSING", "true").lower() == "true"
            )
            self.max_concurrent = int(os.getenv("MEM0_MAX_CONCURRENT_OPERATIONS", "4"))

            # Store feature flags
            self.auto_update_memories = (
                os.getenv("MEM0_AUTO_UPDATE_MEMORIES", "true").lower() == "true"
            )
            self.deduplicate_memories = (
                os.getenv("MEM0_DEDUPLICATE_MEMORIES", "true").lower() == "true"
            )
            self.memory_decay_enabled = (
                os.getenv("MEM0_MEMORY_DECAY_ENABLED", "false").lower() == "true"
            )
            self.memory_decay_rate = float(os.getenv("MEM0_MEMORY_DECAY_RATE", "0.95"))

            logger.info(
                "BotMemory initialized successfully with advanced configuration"
            )

        except Exception as e:
            logger.error(f"Failed to initialize BotMemory: {e}")
            # Fallback to basic memory if mem0 fails
            self.memory = None
            self.has_graph = False
            self.webhook_url = None

    async def remember_from_conversation(
        self, messages: List[Dict], user_id: str
    ) -> Optional[Dict]:
        """Extract and store important memories from a conversation.

        Args:
            messages: List of conversation messages
            user_id: Unique identifier for the user

        Returns:
            Result of memory storage operation
        """
        if not self.memory:
            return None

        try:
            # Mem0 intelligently extracts what's important to remember
            result = self.memory.add(
                messages=messages, user_id=user_id, metadata={"source": "conversation"}
            )

            logger.info(f"Stored memories for user {user_id}: {result}")

            # Send webhook notification if configured
            if result:
                await memory_webhook_handler.send_webhook(
                    event=MemoryWebhookEvent.MEMORY_ADDED, user_id=user_id, data=result
                )

            return result

        except Exception as e:
            logger.error(f"Error storing memories: {e}")
            return None

    async def recall_context(
        self, query: str, user_id: str, limit: int = 5
    ) -> List[Dict]:
        """Retrieve relevant memories for the current context.

        Args:
            query: The current user query/message
            user_id: Unique identifier for the user
            limit: Maximum number of memories to retrieve

        Returns:
            List of relevant memories
        """
        if not self.memory:
            return []

        try:
            memories = self.memory.search(query=query, user_id=user_id, limit=limit)

            logger.info(f"Retrieved {len(memories)} memories for user {user_id}")

            # Send webhook notification for memory search if configured
            if memories:
                await memory_webhook_handler.send_webhook(
                    event=MemoryWebhookEvent.MEMORY_SEARCHED,
                    user_id=user_id,
                    data={
                        "query": query,
                        "limit": limit,
                        "results_count": len(memories),
                        "memories": memories[:3],  # Include first 3 results
                    },
                )

            return memories

        except Exception as e:
            logger.error(f"Error retrieving memories: {e}")
            return []

    async def store_preference(
        self, user_id: str, preference: str, category: str = "general"
    ):
        """Store an explicit user preference.

        Args:
            user_id: Unique identifier for the user
            preference: The preference to store
            category: Category of preference (location, equipment, etc.)
        """
        if not self.memory:
            return

        try:
            result = self.memory.add(
                messages=[{"role": "user", "content": preference}],
                user_id=user_id,
                metadata={"type": "preference", "category": category, "explicit": True},
            )

            logger.info(f"Stored preference for user {user_id}: {preference[:50]}...")

            # Send webhook notification for preference storage
            if result:
                await memory_webhook_handler.send_webhook(
                    event=MemoryWebhookEvent.PREFERENCE_STORED,
                    user_id=user_id,
                    data={
                        "preference": preference,
                        "category": category,
                        "result": result,
                    },
                )

        except Exception as e:
            logger.error(f"Error storing preference: {e}")

    async def store_correction(
        self, user_id: str, original: str, corrected: str, context: str = ""
    ):
        """Store a correction to learn from user feedback.

        Args:
            user_id: Unique identifier for the user
            original: The original response/interpretation
            corrected: The corrected version
            context: Additional context about the correction
        """
        if not self.memory:
            return

        try:
            correction_content = f"User corrected: '{original}' should be '{corrected}'"
            if context:
                correction_content += f" Context: {context}"

            result = self.memory.add(
                messages=[{"role": "system", "content": correction_content}],
                user_id=user_id,
                metadata={
                    "type": "correction",
                    "original": original,
                    "corrected": corrected,
                },
            )

            logger.info(f"Stored correction for user {user_id}")

            # Send webhook notification for correction storage
            if result:
                await memory_webhook_handler.send_webhook(
                    event=MemoryWebhookEvent.CORRECTION_STORED,
                    user_id=user_id,
                    data={
                        "original": original,
                        "corrected": corrected,
                        "context": context,
                        "result": result,
                    },
                )

        except Exception as e:
            logger.error(f"Error storing correction: {e}")

    async def get_all_memories(
        self, user_id: str, memory_type: Optional[str] = None
    ) -> List[Dict]:
        """Retrieve all memories for a user, optionally filtered by type.

        Args:
            user_id: Unique identifier for the user
            memory_type: Optional filter for memory type (preference, correction, etc.)

        Returns:
            List of all user memories
        """
        if not self.memory:
            return []

        try:
            # Get all memories for the user
            all_memories = self.memory.get_all(user_id=user_id)

            # Filter by type if specified
            if memory_type and all_memories:
                filtered = [
                    mem
                    for mem in all_memories
                    if mem.get("metadata", {}).get("type") == memory_type
                ]
                return filtered

            return all_memories

        except Exception as e:
            logger.error(f"Error getting all memories: {e}")
            return []

    async def forget_memories(
        self, user_id: str, memory_ids: Optional[List[str]] = None
    ):
        """Delete specific memories or all memories for a user.

        Args:
            user_id: Unique identifier for the user
            memory_ids: Optional list of specific memory IDs to delete
        """
        if not self.memory:
            return

        try:
            deleted_count = 0
            if memory_ids:
                # Delete specific memories
                for memory_id in memory_ids:
                    self.memory.delete(memory_id=memory_id)
                    deleted_count += 1
                logger.info(f"Deleted {len(memory_ids)} memories for user {user_id}")
            else:
                # Delete all memories for user
                all_memories = await self.get_all_memories(user_id)
                for mem in all_memories:
                    if mem.get("id"):
                        self.memory.delete(memory_id=mem["id"])
                        deleted_count += 1
                logger.info(f"Deleted all memories for user {user_id}")

            # Send webhook notification for memory deletion
            if deleted_count > 0:
                await memory_webhook_handler.send_webhook(
                    event=MemoryWebhookEvent.MEMORY_DELETED,
                    user_id=user_id,
                    data={
                        "deleted_count": deleted_count,
                        "memory_ids": memory_ids,
                        "bulk_delete": memory_ids is None,
                    },
                )

        except Exception as e:
            logger.error(f"Error deleting memories: {e}")

    async def extract_entities_from_text(
        self, text: str, user_id: str
    ) -> Dict[str, List[str]]:
        """Extract and store entities (locations, equipment, etc.) from text.

        Args:
            text: Text to extract entities from
            user_id: User ID for storing extracted preferences

        Returns:
            Dictionary of extracted entities by type
        """
        entities = {"locations": [], "equipment": [], "tasks": []}

        # Simple extraction for POC - could be enhanced with NER
        # Look for common patterns

        # Extract locations (simple pattern matching)
        location_keywords = ["Eagle Lake", "site", "facility", "location", "plant"]
        for keyword in location_keywords:
            if keyword.lower() in text.lower():
                # Extract surrounding context
                import re

                pattern = rf"\b\w+\s+{keyword}\s*\w*\b"
                matches = re.findall(pattern, text, re.IGNORECASE)
                entities["locations"].extend(matches)

        # Extract equipment mentions
        equipment_keywords = ["pump", "valve", "motor", "sensor", "system", "equipment"]
        for keyword in equipment_keywords:
            if keyword.lower() in text.lower():
                import re

                pattern = rf"\b\w*\s*{keyword}\s*\w*\b"
                matches = re.findall(pattern, text, re.IGNORECASE)
                entities["equipment"].extend(matches)

        # Store extracted entities as preferences
        for location in entities["locations"]:
            await self.store_preference(user_id, f"Works at {location}", "location")

        for equipment in entities["equipment"]:
            await self.store_preference(
                user_id, f"Has experience with {equipment}", "equipment"
            )

        return entities

    async def get_graph_relationships(
        self, user_id: str, entity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relationship data from graph memory.

        Args:
            user_id: Unique identifier for the user
            entity: Optional specific entity to get relationships for

        Returns:
            List of relationships from the graph
        """
        if not self.memory or not self.has_graph:
            return []

        try:
            # Access graph store if available
            if hasattr(self.memory, "graph") and self.memory.graph:
                if entity:
                    # Query specific entity relationships
                    query = f"What is related to {entity}?"
                else:
                    # Get all user relationships
                    query = "What are all the relationships for this user?"

                results = self.memory.graph.search(
                    query=query, filters={"user_id": user_id}
                )

                logger.info(
                    f"Retrieved {len(results)} graph relationships for user {user_id}"
                )
                return results
            else:
                logger.warning("Graph store not available despite has_graph=True")
                return []

        except Exception as e:
            logger.error(f"Error retrieving graph relationships: {e}")
            return []

    async def store_entity_relationship(
        self,
        user_id: str,
        source_entity: str,
        relationship: str,
        target_entity: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict]:
        """Store an explicit relationship between entities in the graph.

        Args:
            user_id: Unique identifier for the user
            source_entity: The source entity in the relationship
            relationship: The type of relationship (e.g., "WORKS_AT", "USES", "LOCATED_IN")
            target_entity: The target entity in the relationship
            metadata: Optional metadata about the relationship

        Returns:
            Result of relationship storage operation
        """
        if not self.memory or not self.has_graph:
            logger.warning("Graph memory not available for storing relationships")
            return None

        try:
            # Create a structured message that mem0 can extract relationships from
            relationship_content = f"{source_entity} {relationship.lower().replace('_', ' ')} {target_entity}"

            # Prepare metadata for the relationship
            rel_metadata = {
                "type": "relationship",
                "source_entity": source_entity,
                "relationship": relationship,
                "target_entity": target_entity,
                "explicit": True,
                **(metadata or {}),
            }

            result = self.memory.add(
                messages=[{"role": "system", "content": relationship_content}],
                user_id=user_id,
                metadata=rel_metadata,
            )

            logger.info(
                f"Stored relationship for user {user_id}: {source_entity} -> {relationship} -> {target_entity}"
            )

            # Send webhook notification if configured
            if result:
                await memory_webhook_handler.send_webhook(
                    event=MemoryWebhookEvent.RELATIONSHIP_ADDED,
                    user_id=user_id,
                    data={
                        "source": source_entity,
                        "relationship": relationship,
                        "target": target_entity,
                        "result": result,
                    },
                )

            return result

        except Exception as e:
            logger.error(f"Error storing relationship: {e}")
            return None

    async def find_related_entities(
        self,
        user_id: str,
        entity: str,
        relationship_types: Optional[List[str]] = None,
        max_depth: int = 2,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Find entities related to a given entity through graph traversal.

        Args:
            user_id: Unique identifier for the user
            entity: The entity to find relationships for
            relationship_types: Optional list of relationship types to filter by
            max_depth: Maximum depth of traversal (default: 2)

        Returns:
            Dictionary with relationship types as keys and related entities as values
        """
        if not self.memory or not self.has_graph:
            return {}

        try:
            # Search for memories related to the entity
            related_memories = self.memory.search(
                query=f"relationships involving {entity}", user_id=user_id, limit=20
            )

            # Organize results by relationship type
            relationships: Dict[str, Any] = {}

            for memory in related_memories:
                if memory.get("metadata", {}).get("type") == "relationship":
                    metadata = memory["metadata"]
                    source = metadata.get("source_entity", "")
                    relationship = metadata.get("relationship", "")
                    target = metadata.get("target_entity", "")

                    # Check if this entity is involved in the relationship
                    if (
                        entity.lower() in source.lower()
                        or entity.lower() in target.lower()
                    ):
                        # Filter by relationship types if specified
                        if not relationship_types or relationship in relationship_types:
                            if relationship not in relationships:
                                relationships[relationship] = []

                            # Add the related entity (not the queried entity)
                            related_entity = (
                                target if entity.lower() in source.lower() else source
                            )
                            relationships[relationship].append(
                                {
                                    "entity": related_entity,
                                    "memory_id": memory.get("id"),
                                    "confidence": memory.get("score", 0.0),
                                    "metadata": metadata,
                                }
                            )

            logger.info(
                f"Found relationships for {entity}: {list(relationships.keys())}"
            )
            return relationships

        except Exception as e:
            logger.error(f"Error finding related entities for {entity}: {e}")
            return {}

    async def get_entity_context(
        self,
        user_id: str,
        entity: str,
        include_relationships: bool = True,
        include_mentions: bool = True,
    ) -> Dict[str, Any]:
        """Get comprehensive context about an entity from both vector and graph memory.

        Args:
            user_id: Unique identifier for the user
            entity: The entity to get context for
            include_relationships: Whether to include graph relationships
            include_mentions: Whether to include vector memory mentions

        Returns:
            Dictionary with entity context information
        """
        context = {
            "entity": entity,
            "direct_mentions": [],
            "relationships": {},
            "related_concepts": [],
            "confidence_score": 0.0,
        }

        try:
            # Get direct mentions from vector memory
            if include_mentions:
                mentions = self.memory.search(query=entity, user_id=user_id, limit=10)
                context["direct_mentions"] = mentions

                # Calculate average confidence
                if mentions:
                    context["confidence_score"] = sum(
                        m.get("score", 0.0) for m in mentions
                    ) / len(mentions)

            # Get relationships from graph memory
            if include_relationships and self.has_graph:
                relationships = await self.find_related_entities(user_id, entity)
                context["relationships"] = relationships

                # Extract related concepts
                for rel_type, entities in relationships.items():
                    for entity_data in entities:
                        if entity_data["entity"] not in context["related_concepts"]:
                            context["related_concepts"].append(entity_data["entity"])

            logger.info(
                f"Retrieved context for entity '{entity}': {len(context['direct_mentions'])} mentions, {len(context['relationships'])} relationship types"
            )
            return context

        except Exception as e:
            logger.error(f"Error getting entity context for {entity}: {e}")
            return context

    async def suggest_connections(
        self, user_id: str, entity: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Suggest potential connections for an entity based on context analysis.

        Args:
            user_id: Unique identifier for the user
            entity: The entity to suggest connections for
            limit: Maximum number of suggestions to return

        Returns:
            List of suggested connections with confidence scores
        """
        if not self.memory:
            return []

        try:
            # Get entity context
            context = await self.get_entity_context(user_id, entity)

            # Find entities that appear in similar contexts
            similar_entities: Dict[str, Any] = {}

            for mention in context["direct_mentions"]:
                # Extract other entities from the same memory
                content = mention.get("memory", "")
                if not content:
                    continue

                # Simple entity extraction (could be enhanced with NLP)
                import re

                # Look for capitalized words that might be entities
                potential_entities = re.findall(
                    r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", content
                )

                for potential_entity in potential_entities:
                    if (
                        potential_entity.lower() != entity.lower()
                        and len(potential_entity) > 2
                    ):
                        if potential_entity not in similar_entities:
                            similar_entities[potential_entity] = 0
                        similar_entities[potential_entity] += mention.get("score", 0.0)

            # Sort by frequency/score and return top suggestions
            suggestions = []
            for suggested_entity, score in sorted(
                similar_entities.items(), key=lambda x: x[1], reverse=True
            )[:limit]:
                suggestions.append(
                    {
                        "entity": suggested_entity,
                        "confidence": min(score, 1.0),  # Cap at 1.0
                        "reason": "co-occurrence",
                        "suggestion_type": "potential_relationship",
                    }
                )

            logger.info(
                f"Generated {len(suggestions)} connection suggestions for {entity}"
            )
            return suggestions

        except Exception as e:
            logger.error(f"Error suggesting connections for {entity}: {e}")
            return []

    async def build_knowledge_graph(
        self, user_id: str, entity_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Build a knowledge graph representation of the user's memory.

        Args:
            user_id: Unique identifier for the user
            entity_types: Optional list of entity types to include

        Returns:
            Dictionary representing the knowledge graph
        """
        if not self.memory:
            return {"nodes": [], "edges": [], "stats": {}}

        try:
            # Get all memories for the user
            all_memories = await self.get_all_memories(user_id)

            nodes: Dict[str, Any] = {}  # entity -> node data
            edges = []  # list of edge data

            # Process relationship memories
            relationship_memories = [
                mem
                for mem in all_memories
                if mem.get("metadata", {}).get("type") == "relationship"
            ]

            for memory in relationship_memories:
                metadata = memory.get("metadata", {})
                source = metadata.get("source_entity")
                relationship = metadata.get("relationship")
                target = metadata.get("target_entity")

                if source and target and relationship:
                    # Add nodes
                    if source not in nodes:
                        nodes[source] = {
                            "id": source,
                            "label": source,
                            "type": self._infer_entity_type(source),
                            "memories": [],
                        }
                    if target not in nodes:
                        nodes[target] = {
                            "id": target,
                            "label": target,
                            "type": self._infer_entity_type(target),
                            "memories": [],
                        }

                    # Add memory to both nodes
                    nodes[source]["memories"].append(memory.get("id"))
                    nodes[target]["memories"].append(memory.get("id"))

                    # Add edge
                    edges.append(
                        {
                            "source": source,
                            "target": target,
                            "relationship": relationship,
                            "memory_id": memory.get("id"),
                            "weight": memory.get("score", 0.5),
                        }
                    )

            # Filter by entity types if specified
            if entity_types:
                filtered_nodes = {
                    k: v for k, v in nodes.items() if v["type"] in entity_types
                }
                filtered_edges = [
                    edge
                    for edge in edges
                    if edge["source"] in filtered_nodes
                    and edge["target"] in filtered_nodes
                ]
                nodes = filtered_nodes
                edges = filtered_edges

            graph = {
                "nodes": list(nodes.values()),
                "edges": edges,
                "stats": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "node_types": list(set(node["type"] for node in nodes.values())),
                    "relationship_types": list(
                        set(edge["relationship"] for edge in edges)
                    ),
                },
            }

            logger.info(
                f"Built knowledge graph for user {user_id}: {len(nodes)} nodes, {len(edges)} edges"
            )

            # Send graph built webhook
            await memory_webhook_handler.send_webhook(
                event=MemoryWebhookEvent.GRAPH_BUILT,
                user_id=user_id,
                data={
                    "nodes_count": len(nodes),
                    "edges_count": len(edges),
                    "entity_types_filter": entity_types,
                    "stats": graph["stats"],
                },
            )

            return graph

        except Exception as e:
            logger.error(f"Error building knowledge graph: {e}")
            # Send error webhook
            await memory_webhook_handler.send_webhook(
                event=MemoryWebhookEvent.MEMORY_ERROR,
                user_id=user_id,
                data={
                    "operation": "build_knowledge_graph",
                    "error": str(e),
                    "entity_types": entity_types,
                },
            )
            return {"nodes": [], "edges": [], "stats": {}}

    def _infer_entity_type(self, entity: str) -> str:
        """Infer the type of an entity based on patterns and context.

        Args:
            entity: The entity to classify

        Returns:
            Inferred entity type
        """
        entity_lower = entity.lower()

        # Location indicators
        if any(
            keyword in entity_lower
            for keyword in [
                "facility",
                "site",
                "plant",
                "center",
                "lake",
                "austin",
                "houston",
                "phoenix",
            ]
        ):
            return "location"

        # Equipment indicators
        if any(
            keyword in entity_lower
            for keyword in ["pump", "valve", "motor", "sensor", "system", "equipment"]
        ):
            return "equipment"

        # Organization indicators
        if any(
            keyword in entity_lower
            for keyword in [
                "inc",
                "llc",
                "corp",
                "company",
                "co-op",
                "ventures",
                "capital",
            ]
        ):
            return "organization"

        # Task/Activity indicators
        if any(
            keyword in entity_lower
            for keyword in ["checklist", "task", "inventory", "list", "report"]
        ):
            return "activity"

        # Default
        return "concept"

    async def hybrid_search_with_graph(
        self,
        user_id: str,
        query: str,
        include_related: bool = True,
        relationship_depth: int = 1,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining vector similarity and graph relationships.

        Args:
            user_id: Unique identifier for the user
            query: Search query
            include_related: Whether to include results from related entities
            relationship_depth: How many relationship hops to include
            limit: Maximum number of results to return

        Returns:
            List of search results enhanced with relationship context
        """
        if not self.memory:
            return []

        try:
            # Start with regular vector search
            base_results = self.memory.search(
                query=query, user_id=user_id, limit=limit // 2
            )

            enhanced_results = []

            for result in base_results:
                enhanced_result = result.copy()
                enhanced_result["source"] = "vector_search"
                enhanced_result["relationship_context"] = []

                # Extract entities from the result
                content = result.get("memory", "")
                if content and self.has_graph:
                    # Simple entity extraction
                    import re

                    entities = re.findall(
                        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", content
                    )

                    # Get relationship context for extracted entities
                    for entity in entities[:3]:  # Limit to first 3 entities
                        relationships = await self.find_related_entities(
                            user_id, entity, max_depth=relationship_depth
                        )
                        if relationships:
                            enhanced_result["relationship_context"].append(
                                {"entity": entity, "relationships": relationships}
                            )

                enhanced_results.append(enhanced_result)

            # If graph is available and we want related results, find related entities
            if include_related and self.has_graph and enhanced_results:
                # Extract key entities from top results
                key_entities = set()
                for result in enhanced_results[:3]:  # Top 3 results
                    content = result.get("memory", "")
                    import re

                    entities = re.findall(
                        r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", content
                    )
                    key_entities.update(entities[:2])  # Top 2 entities per result

                # Search for memories related to these entities
                for entity in key_entities:
                    if len(enhanced_results) >= limit:
                        break

                    related_memories = self.memory.search(
                        query=entity, user_id=user_id, limit=2
                    )

                    for memory in related_memories:
                        if memory.get("id") not in [
                            r.get("id") for r in enhanced_results
                        ]:
                            memory["source"] = "graph_expansion"
                            memory["related_to"] = entity
                            enhanced_results.append(memory)

            # Sort by score and limit results
            enhanced_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            final_results = enhanced_results[:limit]

            logger.info(
                f"Hybrid search returned {len(final_results)} results for query: '{query}'"
            )
            return final_results

        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            return []

    async def get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about stored memories.

        Args:
            user_id: Unique identifier for the user

        Returns:
            Dictionary with memory statistics
        """
        stats = {
            "total_memories": 0,
            "memory_types": {},
            "has_graph": self.has_graph,
            "graph_entities": 0,
            "graph_relationships": 0,
            "entity_types": {},
            "relationship_types": {},
            "top_entities": [],
            "graph_density": 0.0,
        }

        try:
            # Get all memories
            memories = await self.get_all_memories(user_id)
            stats["total_memories"] = len(memories)

            # Count by type
            for mem in memories:
                mem_type = mem.get("metadata", {}).get("type", "other")
                stats["memory_types"][mem_type] = (
                    stats["memory_types"].get(mem_type, 0) + 1
                )

            # Get enhanced graph stats if available
            if self.has_graph:
                # Build knowledge graph for comprehensive stats
                knowledge_graph = await self.build_knowledge_graph(user_id)

                stats["graph_entities"] = knowledge_graph["stats"]["total_nodes"]
                stats["graph_relationships"] = knowledge_graph["stats"]["total_edges"]

                # Entity type distribution
                for node in knowledge_graph["nodes"]:
                    entity_type = node.get("type", "unknown")
                    stats["entity_types"][entity_type] = (
                        stats["entity_types"].get(entity_type, 0) + 1
                    )

                # Relationship type distribution
                for edge in knowledge_graph["edges"]:
                    rel_type = edge.get("relationship", "unknown")
                    stats["relationship_types"][rel_type] = (
                        stats["relationship_types"].get(rel_type, 0) + 1
                    )

                # Top entities by connection count
                entity_connections: Dict[str, Any] = {}
                for edge in knowledge_graph["edges"]:
                    source = edge.get("source")
                    target = edge.get("target")
                    if source:
                        entity_connections[source] = (
                            entity_connections.get(source, 0) + 1
                        )
                    if target:
                        entity_connections[target] = (
                            entity_connections.get(target, 0) + 1
                        )

                # Sort and get top 5 entities
                top_entities = sorted(
                    entity_connections.items(), key=lambda x: x[1], reverse=True
                )[:5]
                stats["top_entities"] = [
                    {"entity": entity, "connections": count}
                    for entity, count in top_entities
                ]

                # Calculate graph density (edges / possible edges)
                num_nodes = stats["graph_entities"]
                if num_nodes > 1:
                    max_possible_edges = (
                        num_nodes * (num_nodes - 1) / 2
                    )  # Undirected graph
                    stats["graph_density"] = (
                        stats["graph_relationships"] / max_possible_edges
                        if max_possible_edges > 0
                        else 0.0
                    )

        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")

        return stats

    async def batch_add_memories(
        self, memory_items: List[Dict[str, Any]], user_id: str
    ) -> List[Dict]:
        """Add multiple memories in batch for better performance.

        Args:
            memory_items: List of memory items with 'content' and optional 'metadata'
            user_id: Unique identifier for the user

        Returns:
            List of results from memory storage
        """
        if not self.memory or not self.batch_operations:
            # Fall back to sequential processing
            results = []
            for item in memory_items:
                result = self.memory.add(
                    messages=[{"role": "user", "content": item["content"]}],
                    user_id=user_id,
                    metadata=item.get("metadata", {}),
                )
                results.append(result)
            return results

        try:
            # Process in batches
            results = []
            for i in range(0, len(memory_items), self.batch_size):
                batch = memory_items[i : i + self.batch_size]

                if self.parallel_processing:
                    # Use asyncio for parallel processing
                    import asyncio

                    tasks = []
                    for item in batch:
                        task = asyncio.create_task(
                            self._add_single_memory(item, user_id)
                        )
                        tasks.append(task)

                    # Limit concurrent operations
                    if len(tasks) > self.max_concurrent:
                        # Process in smaller concurrent batches
                        batch_results = []
                        for j in range(0, len(tasks), self.max_concurrent):
                            concurrent_batch = tasks[j : j + self.max_concurrent]
                            batch_results.extend(
                                await asyncio.gather(*concurrent_batch)
                            )
                        results.extend(batch_results)
                    else:
                        results.extend(await asyncio.gather(*tasks))
                else:
                    # Sequential batch processing
                    for item in batch:
                        result = await self._add_single_memory(item, user_id)
                        results.append(result)

            # Send batch completion webhook
            if results:
                await memory_webhook_handler.send_webhook(
                    event=MemoryWebhookEvent.BATCH_OPERATION_COMPLETED,
                    user_id=user_id,
                    data={
                        "operation": "batch_add_memories",
                        "items_processed": len(memory_items),
                        "results_count": len([r for r in results if r]),
                        "batch_size": self.batch_size,
                        "parallel_processing": self.parallel_processing,
                    },
                )

            return results

        except Exception as e:
            logger.error(f"Error in batch memory addition: {e}")
            # Send error webhook
            await memory_webhook_handler.send_webhook(
                event=MemoryWebhookEvent.MEMORY_ERROR,
                user_id=user_id,
                data={
                    "operation": "batch_add_memories",
                    "error": str(e),
                    "items_count": len(memory_items),
                },
            )
            return []

    async def _add_single_memory(self, item: Dict[str, Any], user_id: str) -> Dict:
        """Add a single memory item."""
        try:
            return self.memory.add(
                messages=[{"role": "user", "content": item["content"]}],
                user_id=user_id,
                metadata=item.get("metadata", {}),
            )
        except Exception as e:
            logger.error(f"Error adding single memory: {e}")
            return {}

    async def optimize_memories(self, user_id: str):
        """Optimize stored memories by deduplication and decay.

        Args:
            user_id: Unique identifier for the user
        """
        if not self.memory:
            return

        try:
            memories = await self.get_all_memories(user_id)
            optimization_stats = {
                "total_memories": len(memories),
                "duplicates_removed": 0,
                "decay_applied": False,
            }

            if self.deduplicate_memories:
                # Find and merge duplicate memories
                seen_content: Dict[str, Any] = {}
                duplicates = []

                for mem in memories:
                    content = mem.get("content", "").lower().strip()
                    mem_id = mem.get("id")

                    if content in seen_content:
                        # Mark for deletion
                        duplicates.append(mem_id)
                    else:
                        seen_content[content] = mem_id

                # Delete duplicates
                if duplicates:
                    await self.forget_memories(user_id, duplicates)
                    optimization_stats["duplicates_removed"] = len(duplicates)
                    logger.info(
                        f"Removed {len(duplicates)} duplicate memories for user {user_id}"
                    )

            if self.memory_decay_enabled:
                # Apply decay to old memories based on importance
                # This is a placeholder - actual implementation would need
                # to track access patterns and importance scores
                optimization_stats["decay_applied"] = True
                logger.info("Memory decay feature not fully implemented yet")

            # Send optimization webhook
            await memory_webhook_handler.send_webhook(
                event=MemoryWebhookEvent.MEMORY_OPTIMIZED,
                user_id=user_id,
                data=optimization_stats,
            )

        except Exception as e:
            logger.error(f"Error optimizing memories: {e}")
            # Send error webhook
            await memory_webhook_handler.send_webhook(
                event=MemoryWebhookEvent.MEMORY_ERROR,
                user_id=user_id,
                data={"operation": "optimize_memories", "error": str(e)},
            )

    async def get_memory_insights(self, user_id: str) -> Dict[str, Any]:
        """Get insights about user's memory patterns.

        Args:
            user_id: Unique identifier for the user

        Returns:
            Dictionary with memory insights
        """
        insights = {
            "most_discussed_topics": [],
            "memory_growth_rate": 0,
            "interaction_patterns": {},
            "key_relationships": [],
        }

        try:
            memories = await self.get_all_memories(user_id)

            # Analyze memory categories
            category_counts: Dict[str, Any] = {}
            for mem in memories:
                category = mem.get("metadata", {}).get("category", "general")
                category_counts[category] = category_counts.get(category, 0) + 1

            # Sort by frequency
            insights["most_discussed_topics"] = sorted(
                category_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]

            # Get graph insights if available
            if self.has_graph:
                relationships = await self.get_graph_relationships(user_id)
                # Extract key relationships
                relationship_counts: Dict[str, Any] = {}
                for rel in relationships[:20]:  # Top 20 relationships
                    if isinstance(rel, dict):
                        rel_type = rel.get("type", "unknown")
                        relationship_counts[rel_type] = (
                            relationship_counts.get(rel_type, 0) + 1
                        )

                insights["key_relationships"] = list(relationship_counts.items())

        except Exception as e:
            logger.error(f"Error getting memory insights: {e}")

        return insights

    async def _send_webhook_notification(
        self, event: str, user_id: str, data: Any, retry_count: int = 3
    ):
        """Legacy webhook method - now delegates to the new webhook handler."""
        # Convert string event to enum if possible
        try:
            webhook_event = MemoryWebhookEvent(event)
        except ValueError:
            logger.warning(f"Unknown webhook event: {event}")
            return

        await memory_webhook_handler.send_webhook(
            event=webhook_event, user_id=user_id, data=data
        )

    def get_user_config(self, user_id: str) -> Dict[str, Any]:
        """Get user-specific memory configuration from environment."""
        user_config: Dict[str, Any] = {}

        # Check for user-specific settings
        user_prefix = f"MEM0_USER_{user_id.upper()}_"

        # Memory retention policy
        retention = os.getenv(f"{user_prefix}RETENTION_DAYS")
        if retention:
            user_config["retention_days"] = int(retention)

        # Memory categories allowed
        categories = os.getenv(f"{user_prefix}CATEGORIES")
        if categories:
            user_config["allowed_categories"] = categories.split(",")

        # Auto-extract preferences
        auto_extract = os.getenv(f"{user_prefix}AUTO_EXTRACT", "true")
        user_config["auto_extract"] = auto_extract.lower() == "true"

        return user_config


# Global instance
bot_memory = BotMemory()


async def seed_initial_memories():
    """Seed initial memories from environment configuration."""
    import json

    # Check for initial memories in environment
    initial_memories = os.getenv("MEM0_INITIAL_MEMORIES")
    if initial_memories:
        try:
            memories = json.loads(initial_memories)
            for memory in memories:
                user_id = memory.get("user_id", "system")
                content = memory.get("content")
                category = memory.get("category", "system")

                if content:
                    await bot_memory.store_preference(
                        user_id=user_id, preference=content, category=category
                    )
                    logger.info(f"Seeded memory for {user_id}: {content[:50]}...")
        except Exception as e:
            logger.error(f"Error seeding initial memories: {e}")

    # Check for webhook configuration
    webhook_url = os.getenv("MEM0_WEBHOOK_URL")
    if webhook_url:
        logger.info(f"Webhook URL configured: {webhook_url}")
