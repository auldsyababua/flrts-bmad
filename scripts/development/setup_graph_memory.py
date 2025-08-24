#!/usr/bin/env python3
"""
Setup script for graph memory infrastructure.
This script configures Neo4j and creates the necessary environment variables.
"""

import subprocess
import sys
import time
from pathlib import Path


def create_env_file():
    """Create environment file with Neo4j configuration."""
    env_content = """
# Neo4j Configuration for Graph Memory
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=markdown-bot-password

# mem0 Graph Memory Configuration
MEM0_GRAPH_CUSTOM_PROMPT="Extract entities and relationships from this conversation for knowledge graph storage."

# Enable graph features
MEM0_ENABLE_GRAPH=true

# Additional OpenAI configuration for mem0
# Add your OpenAI API key for mem0 to work properly
# OPENAI_API_KEY=your_key_here
"""

    env_file = Path(".env.local")
    env_file.write_text(env_content.strip())
    print(f"✅ Created {env_file} with Neo4j configuration")


def create_docker_compose():
    """Create docker-compose file for Neo4j if it doesn't exist."""
    compose_file = Path("docker-compose.neo4j.yml")
    if compose_file.exists():
        print(f"✅ {compose_file} already exists")
        return

    compose_content = """
services:
  neo4j:
    image: neo4j:5.15-community
    container_name: markdown-bot-neo4j
    restart: unless-stopped
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    environment:
      NEO4J_AUTH: neo4j/markdown-bot-password
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: apoc.*
      NEO4J_dbms_security_procedures_allowlist: apoc.*
      NEO4J_server_memory_heap_initial__size: 512m
      NEO4J_server_memory_heap_max__size: 1G
      NEO4J_server_memory_pagecache_size: 512m
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/var/lib/neo4j/import
      - neo4j_plugins:/plugins
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p markdown-bot-password 'RETURN 1'"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s

volumes:
  neo4j_data:
  neo4j_logs:
  neo4j_import:
  neo4j_plugins:

networks:
  default:
    name: markdown-bot-network
"""

    compose_file.write_text(compose_content.strip())
    print(f"✅ Created {compose_file}")


def check_docker():
    """Check if Docker is running."""
    try:
        result = subprocess.run(
            ["docker", "ps"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ Docker is running")
            return True
        else:
            print("❌ Docker is not running")
            return False
    except Exception as e:
        print(f"❌ Docker check failed: {e}")
        return False


def start_neo4j():
    """Start Neo4j container."""
    try:
        # Check if container is already running
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=markdown-bot-neo4j",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if "markdown-bot-neo4j" in result.stdout:
            print("✅ Neo4j container is already running")
            return True

        # Start the container
        print("🚀 Starting Neo4j container...")
        result = subprocess.run(
            ["docker-compose", "-f", "docker-compose.neo4j.yml", "up", "-d"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            print("✅ Neo4j container started successfully")
            # Wait for healthcheck
            print("⏳ Waiting for Neo4j to be ready...")
            time.sleep(10)
            return True
        else:
            print(f"❌ Failed to start Neo4j: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Error starting Neo4j: {e}")
        return False


def create_requirements_patch():
    """Create a requirements patch file for manual installation."""
    patch_content = """
# Neo4j Dependencies for Graph Memory
# Run: pip install -r requirements.neo4j.txt

neo4j>=5.0.0
langchain-neo4j>=0.0.5
"""

    patch_file = Path("requirements.neo4j.txt")
    patch_file.write_text(patch_content.strip())
    print(f"✅ Created {patch_file} for manual dependency installation")


def create_graph_memory_test():
    """Create a simple test for graph memory."""
    test_content = '''
#!/usr/bin/env python3
"""
Simple test for graph memory functionality.
"""

import os
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")
load_dotenv()  # Load main .env if it exists

async def test_graph_memory():
    """Test graph memory functionality."""
    try:
        from src.core.memory import BotMemory
        
        print("🧠 Testing BotMemory initialization...")
        memory = BotMemory()
        
        if memory.has_graph:
            print("✅ Graph memory is enabled!")
            
            # Test basic graph operations
            user_id = "test_user"
            
            # Store a relationship
            print("\n💾 Testing relationship storage...")
            result = await memory.store_entity_relationship(
                user_id=user_id,
                source_entity="Colin",
                relationship="WORKS_AT",
                target_entity="Eagle Lake Facility",
                metadata={"confidence": 0.9}
            )
            
            if result:
                print("✅ Relationship stored successfully")
            else:
                print("❌ Failed to store relationship")
            
            # Test memory stats
            print("\n📈 Testing memory stats...")
            stats = await memory.get_memory_stats(user_id)
            print(f"Graph entities: {stats.get('graph_entities', 0)}")
            print(f"Graph relationships: {stats.get('graph_relationships', 0)}")
            print(f"Has graph: {stats.get('has_graph', False)}")
            
        else:
            print("❌ Graph memory is not enabled")
            print("Check your environment variables:")
            print(f"  NEO4J_URL: {os.getenv('NEO4J_URL')}")
            print(f"  NEO4J_USERNAME: {os.getenv('NEO4J_USERNAME')}")
            print(f"  NEO4J_PASSWORD: {'***' if os.getenv('NEO4J_PASSWORD') else 'Not set'}")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure to install Neo4j dependencies:")
        print("  pip install -r requirements.neo4j.txt")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_graph_memory())
'''

    test_file = Path("test_graph_memory.py")
    test_file.write_text(test_content.strip())
    print(f"✅ Created {test_file} for testing graph memory")


def create_installation_guide():
    """Create installation guide."""
    guide_content = """
# Graph Memory Setup Guide

## Quick Setup

1. **Start Neo4j:**
   ```bash
   docker-compose -f docker-compose.neo4j.yml up -d
   ```

2. **Install Neo4j Python packages:**
   ```bash
   pip install -r requirements.neo4j.txt
   ```

3. **Load environment variables:**
   ```bash
   source .env.local
   ```

4. **Test graph memory:**
   ```bash
   python test_graph_memory.py
   ```

## Manual Installation (if pip times out)

1. **Download packages manually:**
   ```bash
   # For neo4j driver
   pip download neo4j
   pip install neo4j-*.whl
   
   # For langchain-neo4j
   pip download langchain-neo4j
   pip install langchain_neo4j-*.whl
   ```

2. **Alternative: Use conda**
   ```bash
   conda install -c conda-forge neo4j-python-driver
   pip install langchain-neo4j
   ```

## Verification

- Neo4j Web UI: http://localhost:7474
- Username: neo4j
- Password: markdown-bot-password

## Environment Variables

Ensure these are set in your `.env` or `.env.local`:

```bash
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=markdown-bot-password
```

## Troubleshooting

- **Docker not running:** Start Docker Desktop
- **Neo4j connection failed:** Check if container is healthy with `docker ps`
- **Import errors:** Install dependencies manually as shown above
- **Permission errors:** Make sure Docker has proper permissions
"""

    guide_file = Path("GRAPH_MEMORY_SETUP.md")
    guide_file.write_text(guide_content.strip())
    print(f"✅ Created {guide_file} with setup instructions")


def main():
    """Main setup function."""
    print("🔧 Setting up Graph Memory Infrastructure")
    print("=" * 50)

    # Create configuration files
    print("\n1. Creating configuration files...")
    create_env_file()
    create_docker_compose()
    create_requirements_patch()
    create_graph_memory_test()
    create_installation_guide()

    # Check Docker
    print("\n2. Checking Docker...")
    if not check_docker():
        print(
            "⚠️  Docker is not running. Please start Docker Desktop and run this script again."
        )
        return False

    # Start Neo4j
    print("\n3. Starting Neo4j...")
    if not start_neo4j():
        print("⚠️  Failed to start Neo4j. Check Docker logs.")
        return False

    print("\n🎉 Graph Memory Infrastructure Setup Complete!")
    print("\n📝 Next Steps:")
    print("   1. Install Neo4j Python packages:")
    print("      pip install -r requirements.neo4j.txt")
    print("   2. Test the setup:")
    print("      python test_graph_memory.py")
    print("   3. Check Neo4j Web UI:")
    print("      http://localhost:7474 (neo4j/markdown-bot-password)")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
