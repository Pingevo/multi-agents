# ADR-0002: Chainlit + CrewAI architecture

## Status

Accepted

## Context

The platform needs a web UI for chat-based interaction and a multi-agent execution engine. The user interacts through a custom React frontend that communicates with a Python backend via Chainlit WebSocket.

## Decision

Use Chainlit as the WebSocket backend layer and CrewAI as the multi-agent execution engine. The custom React frontend connects to Chainlit's Socket.IO endpoint and communicates via structured JSON messages (platform_state, chat_reply).

## Consequences

- Backend is Python-only (Chainlit + CrewAI)
- Frontend is React + TypeScript, communicating via Socket.IO
- All messages are structured JSON payloads, not plain text
- State management is centralized in StateMessenger
- LLM provider is swappable (Ollama now, OpenRouter later) without changing the architecture
