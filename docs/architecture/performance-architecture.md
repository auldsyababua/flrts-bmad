# Performance Architecture

## Smart Rails Performance Optimization

| Confidence Level | Processing Type | Token Usage | Response Time | Use Cases |
|------------------|----------------|-------------|---------------|-----------|
| 100% | Direct Execution | 0 tokens | <50ms | `/newtask for @joel` |
| 80-99% | Focused LLM | 50-100 tokens | <500ms | "add milk to shopping list" |
| <80% | Full Analysis | 200-500 tokens | <2000ms | "maybe update that thing" |

## Caching Strategy
- **Redis Caching**:
  - Conversation history: 24 hours TTL
  - Search results: 5 minutes TTL
  - User preferences: 7 days TTL
- **Application Caching**:
  - LLM response patterns
  - Frequently accessed documents
  - User session data

## Database Optimization
- **Read Replicas**: Supabase read replicas for query performance
- **Indexing Strategy**: Compound indexes on frequently queried fields
- **Connection Pooling**: Managed connection pools for all services
- **Query Optimization**: Prepared statements and batch operations
