# Source Tree Overview

This document provides a high-level overview of the directory structure for the BrainBot project.

```
/
├── .bmad-core/           # BMad Method agent definitions and workflows.
├── .github/              # GitHub-specific files, including CI/CD workflows.
├── cf/                   # Cloudflare Worker scripts.
├── docs/                 # Project documentation, including architecture and PRDs.
│   └── architecture/     # Detailed architecture documents.
├── main.py               # Main entry point for the production FastAPI application.
├── pyproject.toml        # Python project configuration and dependencies.
├── README.md             # Top-level project README.
├── render.yaml           # Deployment configuration for Render.
├── requirements.txt      # Python dependencies.
├── scripts/              # Various utility and automation scripts.
├── src/                  # Backend Python source code.
│   ├── bot/              # Core bot logic, including webhook and handlers.
│   ├── core/             # Core application logic (config, LLM, memory).
│   ├── health/           # Health check endpoints.
│   ├── migrations/       # Data migration scripts.
│   ├── monitoring/       # Monitoring and logging components.
│   ├── rails/            # "Smart Rails" message processing and routing logic.
│   └── storage/          # Storage service abstractions.
├── telegram-mini-app/    # Frontend React application for the Telegram Mini App.
│   ├── public/           # Static assets for the frontend.
│   └── src/              # TypeScript source code for the React app.
│       ├── components/   # Reusable React components.
│       ├── context/      # React context providers.
│       ├── services/     # API service clients.
│       └── utils/        # Utility functions for the frontend.
└── tests/                # Backend tests.
    ├── integration/      # Integration tests for backend services.
    └── unit/             # Unit tests for individual backend components.
```
