# Technology Stack

This document outlines the key technologies, frameworks, and services used in the BrainBot project.

## Backend

- **Language:** Python 3.9+
- **Framework:** FastAPI for the webhook server.
- **Core Libraries:**
  - `python-telegram-bot`: For interacting with the Telegram Bot API.
  - `openai`: For interfacing with OpenAI's language models.
  - `uvicorn`: As the ASGI server for FastAPI.
  - `boto3`: For AWS S3 integration (legacy media storage).
  - `mem0ai`: For memory management features.
  - `sentence-transformers`: For generating vector embeddings.

## Frontend (Telegram Mini App)

- **Language:** TypeScript
- **Framework:** React 18
- **Build Tool:** Vite
- **Styling:** Tailwind CSS
- **UI Components:** Lucide React for icons.
- **Testing:** Vitest with React Testing Library.

## Data & Storage

- **Primary Database:** Supabase (PostgreSQL) for structured data and audit logs.
- **Vector Search:** Cloudflare Vectorize for efficient semantic search.
- **Caching:** Cloudflare KV is used as a key-value store for caching.
- **Graph Database:** Neo4j for the graph-based memory system.
- **Legacy Storage:**
  - Upstash Redis (for conversation persistence).
  - Upstash Vector (for semantic search).
  - AWS S3 (for media storage).

## Deployment & Infrastructure

- **Hosting:** Render is used for deploying both the backend web service and the frontend static site.
- **Containerization:** Docker is used for defining test environments (`docker-compose.test.yml`).
- **CI/CD:** GitHub Actions are implied by the `.github/workflows` directory, used for continuous integration and deployment.

## Development & Tooling

- **Package Management:**
  - `pip` with `requirements.txt` for the Python backend.
  - `npm` for the frontend.
- **Linting & Formatting:**
  - **Python:** Ruff and Black.
  - **Frontend:** ESLint and Biome.
- **Testing:**
  - **Python:** Pytest.
  - **Frontend:** Vitest.
