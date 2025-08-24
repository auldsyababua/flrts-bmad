# Epic: Complete Type Safety and Test Integrity

## Epic ID: TECH-001
## Priority: HIGH
## Status: IN PROGRESS

## Problem Statement
The codebase currently has 68 mypy type checking errors that create technical debt and reduce code maintainability. Additionally, having failing tests that are ignored creates bad development habits and reduces confidence in the test suite.

## Business Value
- **Code Quality**: Eliminate all type errors for maintainable, production-ready code
- **Developer Confidence**: All tests pass, no ignored failures
- **Future-Proofing**: Type-safe code prevents runtime errors in production
- **Team Productivity**: Clear types improve IDE support and reduce debugging time

## Success Criteria
1. ✅ All mypy type checks pass (0 errors)
2. ✅ All CI/CD checks are green
3. ✅ No tests are skipped or ignored without explicit documentation
4. ✅ Type stubs installed for all third-party libraries

## Current State (68 Type Errors)
- 18 errors in `health_checks.py`
- 15 errors in `dynamic_prompts.py`  
- 14 errors in `memory.py`
- 10 errors in `llm.py`
- 11 errors across other files

## User Stories

### Story 1: Install Missing Type Stubs ✅
**Status**: COMPLETED
- Add `types-PyYAML` to requirements.txt
- Add `types-requests` to requirements.txt

### Story 2: Fix Simple Type Annotations (21 errors)
**Status**: IN PROGRESS
**Files**:
- `src/core/chunking.py` - Add list type annotation
- `src/rails/synonym_library.py` - Fix cache type issues (2 errors)
- `src/monitoring/performance_alerts.py` - Add request types
- `src/bot/set_webhook.py` - Add request types
- `src/migrations/migrate_to_vector.py` - Add yaml types
- `src/storage/redis_store.py` - Add keys annotation
- `src/core/api_client.py` - Fix monitor attribute errors (2 errors)
- `src/bot/handlers.py` - Add entity_map annotation
- `src/storage/*.py` - Various simple annotations

### Story 3: Fix Complex Type Issues in Dynamic Prompts (15 errors)
**Status**: TODO
**File**: `src/rails/dynamic_prompts.py`
- Fix Collection[str] indexing issues (9 errors)
- Fix incompatible return types
- Fix float/int assignment issues
- Fix optional type defaults

### Story 4: Fix Health Check Type Issues (18 errors)
**Status**: TODO  
**File**: `src/health/health_checks.py`
- Convert boolean dict values to strings
- Fix Union type handling for HealthStatus/BaseException
- Add proper type guards for dict operations
- Fix return type consistency

### Story 5: Fix Memory System Types (14 errors)
**Status**: TODO
**File**: `src/core/memory.py`
- Fix missing MemoryWebhookEvent attributes (4 errors)
- Add type annotations for dictionaries (4 errors)
- Fix object type operations
- Fix list/int assignment confusion

### Story 6: Fix LLM Core Types (10 errors)
**Status**: TODO
**File**: `src/core/llm.py`
- Fix None attribute access for monitor
- Add cache type annotation
- Fix processor type assignments
- Fix optional parameter defaults

### Story 7: Final Validation and CI Update
**Status**: TODO
- Run full mypy check locally
- Verify all tests pass
- Update CI configuration if needed
- Document any necessary type: ignore comments with justification

## Technical Approach

### Phase 1: Quick Wins (Stories 1-2)
- Install type stubs
- Fix simple annotations
- ~30 minutes

### Phase 2: Complex Refactoring (Stories 3-6)  
- Fix architectural type issues
- May require minor refactoring
- ~45 minutes

### Phase 3: Validation (Story 7)
- Full test suite run
- CI/CD verification
- ~15 minutes

## Risks and Mitigations
- **Risk**: Type fixes might change runtime behavior
  - **Mitigation**: Run full test suite after each story
  
- **Risk**: Third-party library incompatibilities
  - **Mitigation**: Use type: ignore with documentation where necessary

## Definition of Done
- [ ] All 68 mypy errors resolved
- [ ] CI/CD pipeline fully green
- [ ] No suppressed or ignored warnings
- [ ] Code review completed
- [ ] PR merged to main branch

## Notes
- Time estimate: 1.5-2 hours total
- Current focus: Story 2 (simple annotations)
- Next: Story 3 (dynamic prompts complex types)

---

**Created**: 2024-01-20
**Owner**: Development Team
**Epic Type**: Technical Debt