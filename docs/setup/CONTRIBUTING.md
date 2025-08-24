# Contributing to FLRTS BrainBot

## 🔗 GitHub ↔ Linear Integration

This repository is integrated with Linear for issue tracking and project management. All pull requests must be linked to a Linear issue.

### PR Title Requirements

**Format:** `10N-XXX: Brief description`

- `10N` is our Linear team key
- `XXX` is the issue number
- Example: `10N-123: Add vector search optimization`

### Commit Message Guidelines

We encourage (but don't enforce) including Linear issue references in commit messages:

```bash
# Good examples
git commit -m "10N-123: Implement vector search caching"
git commit -m "Fix memory leak in webhook handler (10N-456)"
git commit -m "10N-789: Update dependencies and fix security vulnerabilities"
```

### Auto-Transition Workflow

Our GitHub Actions automatically transition Linear issues based on PR events:

| PR Event | Linear State Change |
|----------|-------------------|
| PR opened/reopened | → In Progress |
| PR merged | → Done |
| PR closed (not merged) | → Backlog |

### Required Secrets

Repository maintainers must configure these GitHub secrets:

- `LINEAR_API_KEY` - Personal API token from Linear with write access
- `LINEAR_TEAM_KEY` - Set to `10N` (optional, currently hardcoded)

Future optional secrets for Sentry integration:
- `SENTRY_AUTH_TOKEN`
- `SENTRY_ORG`
- `SENTRY_PROJECT_FRONTEND`
- `SENTRY_PROJECT_BACKEND`

## ✅ CI/CD Requirements

All pull requests must pass the following checks:

### Python Backend
- **Linting:** `ruff` must pass with no errors
- **Formatting:** `black --check` must pass
- **Type checking:** `mypy` must pass
- **Tests:** `pytest` with ≥85% code coverage

### Frontend (Telegram Mini App)
- **Linting:** `eslint` must pass
- **Type checking:** `tsc` must pass
- **Tests:** `vitest` with ≥85% code coverage

### Running Checks Locally

Before pushing, run these commands:

```bash
# Python checks
ruff check src/ tests/
black --check src/ tests/
mypy src/ --ignore-missing-imports
pytest tests/ --cov=src --cov-fail-under=85

# Frontend checks (in telegram-mini-app/)
npm run lint
npm run type-check
npm run test:coverage
```

## 📝 PR Template

When creating a PR, you'll see a template with these sections:

1. **Linear Issue ID** - Must match PR title
2. **Agent Plan** - Who/what/why for the changes
3. **Test Plan** - Description of test coverage
4. **Sensitive Operations** - Flag any credential usage
5. **Checklist** - Ensure all requirements are met

## 🚀 Development Workflow

1. **Create Linear issue** in the [10NetZero workspace](https://linear.app/10netzero)
2. **Create feature branch** with descriptive name
3. **Make changes** with clear, atomic commits
4. **Run tests locally** to ensure CI will pass
5. **Open PR** with Linear issue in title (`10N-XXX: ...`)
6. **Fill out PR template** completely
7. **Wait for CI checks** and address any failures
8. **Request review** from team members
9. **Merge** once approved and all checks pass

## 🔒 Security Guidelines

- **Never commit secrets** or API keys
- **Use GitHub secrets** for all credentials
- **Mark sensitive operations** in PR template
- **Agent-safe code** - ensure no credentials appear in logs or outputs
- **Review security warnings** from CI/CD tools

## 🤖 Agent Development

When developing with AI agents:

1. **Document agent context** in PR description
2. **Flag agent-generated code** for extra review
3. **Ensure agent-safe patterns** (no credential exposure)
4. **Test anti-mesa scenarios** (edge cases, defensive testing)
5. **Include test coverage** for all agent-generated code

## 📚 Additional Resources

- [Linear Documentation](https://linear.app/docs)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Project README](README.md)
- [Smart Rails Architecture](docs/smart-rails-architecture.md)

## 💬 Getting Help

- Check existing [Linear issues](https://linear.app/10netzero/team/10N/all)
- Ask in team Slack channel
- Review [closed PRs](https://github.com/auldsyababua/BrainBot/pulls?q=is%3Apr+is%3Aclosed) for examples

---

By contributing to this project, you agree to follow these guidelines and help maintain code quality and project organization.