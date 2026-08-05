# ADR-0004: SearchAdapter for web search format selection

## Status

Accepted

## Context

The search system sent `tools: [{type: "openrouter:web_search"}]` to every model, but Perplexity models (sonar-pro, sonar, etc.) have built-in search and don't accept the `tools` parameter — they require top-level `web_search_options` instead. This caused 404 errors ("No endpoints found that support tool use") whenever a user selected a Perplexity model for search.

The decision logic for which format to use was spread across 4 points (secretary, chat.py, orchestrator, search.py) with no single place checking model capability.

## Decision

Create a `SearchAdapter` module as the single decision point. It queries `ModelDiscoveryService` for a model's `supported_parameters` and selects the request format: `tools` (server tool) when `"tools"` is in the supported parameters, or `web_search_options` (built-in search) when only `"web_search"` is present. Falls back to a `perplexity/` prefix heuristic when the model is not in the catalog.

## Considered Options

- **Prefix heuristic in search.py** — check `model.startswith("perplexity/")` inline. Rejected: hardcodes model families, breaks when new built-in-search models appear, doesn't use the catalog data we already fetch.
- **Merge into ModelDiscoveryService** — let the discovery service also build request bodies. Rejected: violates single responsibility — discovery catalogs models, it shouldn't also execute searches. The adapter composes discovery rather than extending it.
- **SearchAdapter as separate module** (chosen) — keeps discovery focused on cataloging, gives search its own deep module with a small interface, and creates a seam that P0.1 (dependency injection) can wire through.

## Consequences

- Search format selection is testable through a single interface without HTTP.
- New built-in-search model families need only a catalog entry (or prefix heuristic update), not edits across 4 files.
- The 4 original decision points still exist (deferred removal per "ทำทีละตัว" rule); P0.1 will consolidate them into the adapter.
- `_resolve_search_model` and `_check_search_call_limit` remain in search.py reading module-level globals — P0.1 replaces them with dependency injection through the adapter.
