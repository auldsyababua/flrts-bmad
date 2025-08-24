# Development Guidelines

## Code Organization
```
src/
├── bot/                 # Telegram bot handlers
├── core/                # Core business logic
├── rails/               # Smart Rails routing system
├── storage/             # Data storage services
└── migrations/          # Database migration scripts
```

## Coding Standards
- **Python**: Follow PEP 8, use Black formatter, type hints
- **TypeScript**: ESLint + Prettier, strict type checking
- **Testing**: 80%+ code coverage, integration tests
- **Documentation**: Docstrings for all public APIs

## Development Workflow
1. **Feature Branches**: All work on feature branches
2. **Code Review**: Required before merging to main
3. **Automated Testing**: CI/CD pipeline runs all tests
4. **Deployment**: Automatic deployment from main branch
