"""
Storage module initialization.
Provides unified interface for vector storage operations.
"""

from dotenv import load_dotenv

from .cloudflare_vector_store import cloudflare_vector_store as vector_store

# Load environment variables
load_dotenv()

# Export the vector store
__all__ = ["vector_store"]
