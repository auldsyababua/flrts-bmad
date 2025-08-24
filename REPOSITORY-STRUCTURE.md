# Repository Structure

This document describes the organized structure of the FLRTS-BMAD repository following professional standards and best practices.

## Directory Layout

```
flrts-bmad/
├── src/                      # Source code
│   ├── auth/                 # Authentication module
│   ├── memory/               # Memory management
│   ├── rails/                # Rails integration
│   └── utils/                # Utility functions
│
├── docs/                     # Documentation
│   ├── setup/                # Setup and installation guides
│   │   └── CONTRIBUTING.md  # Contribution guidelines
│   ├── technical/            # Technical documentation
│   │   ├── design.md         # System design
│   │   ├── requirements.md   # Technical requirements
│   │   └── EPIC_TYPE_SAFETY.md  # Type safety documentation
│   ├── operations/           # Operational guides
│   ├── architecture/         # Architecture documentation
│   └── prd/                  # Product requirement documents
│
├── config/                   # Configuration files
│   ├── mem0-config.json     # Memory configuration
│   ├── docker-compose.test.yml  # Docker test configuration
│   ├── render.yaml           # Render deployment config
│   ├── .ruff.local.toml      # Ruff linter config
│   ├── .black.local.toml     # Black formatter config
│   ├── .coderabbit.yaml      # CodeRabbit CI config
│   └── .coderabbit.yml       # CodeRabbit alternate config
│
├── scripts/                  # Executable scripts
│   └── [various scripts]     # Build, deploy, and utility scripts
│
├── tests/                    # Test files
│   ├── unit/                 # Unit tests
│   └── test_*.py             # Test modules
│
├── testsprite_tests/         # TestSprite testing framework
│   ├── anti_mesa_tests.py   # Anti-MESA test suite
│   ├── screenshots/          # UI test screenshots
│   └── [test files]          # Various test files
│
├── cf/                       # Cloudflare Workers
│   ├── brainbot-consumer/    # Consumer service
│   ├── brainbot-webhook/     # Webhook service
│   └── README.md             # CF documentation
│
├── telegram-mini-app/        # Telegram Mini App
│   └── [app files]           # Mini app implementation
│
├── web-bundles/              # Web bundle assets
│   └── [bundle files]        # Compiled web assets
│
├── archive/                  # Archived files
│   ├── backups/              # Backup files
│   ├── deprecated/           # Deprecated code
│   │   └── codebase.md       # Generated codebase documentation
│   └── temp/                 # Temporary files
│       ├── app.log           # Application log
│       └── startup.log       # Startup log
│
├── 10nz_kb/                  # Knowledge base
│   └── [kb files]            # Knowledge base content
│
└── assets/                   # Static resources
    └── [resource files]      # Images, icons, etc.
```

## Hidden Directories (Preserved)

The following hidden directories are maintained in their original locations as they are framework/tool specific:

- `.git/` - Version control
- `.github/` - GitHub Actions and workflows
- `.bmad-core/` - BMAD core files
- `.bmad-infrastructure-devops/` - BMAD DevOps files
- `.claude/` - Claude AI configuration
- `.coderabbit/` - CodeRabbit CI files
- `.gemini/` - Gemini configuration
- `.qwen/` - Qwen configuration
- `.superdesign/` - SuperDesign files
- `.vscode/` - VS Code configuration
- `.pytest_cache/` - Pytest cache
- `.ruff_cache/` - Ruff linter cache
- `.mypy_cache/` - MyPy type checker cache
- `.githooks/` - Git hooks

## Root Files

Essential files kept in root:
- `README.md` - Project overview
- `REPOSITORY-STRUCTURE.md` - This file
- `CLAUDE.md` - Claude AI instructions
- `pyproject.toml` - Python project configuration
- `requirements.txt` - Python dependencies
- `uv.lock` - UV package lock file
- `main.py` - Main application entry point
- `.gitignore` - Git ignore rules
- `.semgrepignore` - Semgrep ignore rules
- `.env.example` - Example environment variables
- `.env.example.clean` - Clean env example
- `.env.test` - Test environment
- `.env.workhorse` - Workhorse environment
- `.mcp.json` - MCP configuration

## Symlinks

For backward compatibility, the following symlinks are created:
- `docker-compose.test.yml` → `config/docker-compose.test.yml`
- `render.yaml` → `config/render.yaml`

## Organization Principles

1. **Documentation** - All docs organized by type in `/docs`
2. **Configuration** - All config files centralized in `/config`
3. **Source Code** - Production code in `/src`
4. **Testing** - Test files in `/tests` and `/testsprite_tests`
5. **Archives** - Old/temporary files in `/archive`
6. **Hidden Dirs** - Framework-specific hidden directories preserved
7. **Root Files** - Only essential files kept in root

## Migration Notes

Files were moved from root to organized directories:
- Documentation → `/docs`
- Config files → `/config`
- Logs → `/archive/temp`
- Generated docs → `/archive/deprecated`

This structure follows industry best practices while maintaining framework requirements and CI/CD compatibility.