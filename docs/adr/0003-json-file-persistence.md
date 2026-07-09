# ADR-0003: JSON file persistence

## Status

Accepted

## Context

The platform needs to persist agents, tasks, and chat sessions. At this stage, a database would add complexity without proportional benefit.

## Decision

Use JSON files for all persistence: `agent_registry.json`, `task_registry.json`, `chat_sessions.json`. Each store class manages its own file with load/save methods.

## Consequences

- No database setup or migration needed
- Data is human-readable and debuggable
- Not suitable for concurrent writes (single-user assumption)
- Can be migrated to a database later by replacing store classes
- Store classes (AgentRegistry, TaskStore, ChatStore) are the seam for this swap
