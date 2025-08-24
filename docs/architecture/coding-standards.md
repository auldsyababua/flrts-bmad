# Coding Standards

This document outlines the coding standards and conventions for the BrainBot project, covering both the Python backend and the TypeScript/React frontend.

## Python (Backend)

The Python codebase adheres to modern standards for formatting and linting to ensure consistency and readability.

- **Formatting:** [Black](https://github.com/psf/black) is used for automatic code formatting. All code should be formatted with Black before committing. The configuration is defined in `pyproject.toml`.
  - **Line Length:** 88 characters.

- **Linting:** [Ruff](https://github.com/astral-sh/ruff) is used for linting. It helps identify potential errors, bugs, and stylistic issues. The configuration is defined in `pyproject.toml`.

- **Type Hinting:** All new functions and methods should include type hints for arguments and return values, as per PEP 484.

- **Imports:** Imports should be organized into three groups: standard library, third-party packages, and local application imports.

- **Docstrings:** All modules, classes, and functions should have docstrings explaining their purpose, arguments, and return values.

## TypeScript/React (Frontend)

The frontend codebase follows standard practices for modern web development to ensure code quality and maintainability.

- **Formatting & Linting:** [ESLint](https://eslint.org/) and [Biome](https://biomejs.dev/) are used for code linting and formatting. The configurations can be found in the `telegram-mini-app` directory. Developers should run the `lint` and `lint:fix` scripts to check and fix issues.

- **Component Structure:** React components should be functional components using hooks. Each component should be in its own file (e.g., `MyComponent.tsx`).

- **Styling:** [Tailwind CSS](https://tailwindcss.com/) is used for styling. Utility-first classes should be used whenever possible.

- **Naming Conventions:**
  - Components: `PascalCase` (e.g., `ChatView.tsx`).
  - Variables and functions: `camelCase`.
  - Types and interfaces: `PascalCase` (e.g., `interface UserProfile`).

## General

- **Version Control:** All code changes must be submitted through pull requests on GitHub.
- **CI/CD:** Automated checks for linting and tests are expected to be run via GitHub Actions. Pull requests must pass these checks before being merged.
- **Secrets:** Never commit secrets, API keys, or other sensitive information directly to the repository. Use environment variables and `.env` files for local development, and the hosting provider's secret management for production.
