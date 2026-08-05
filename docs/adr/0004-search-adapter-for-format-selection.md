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

## Amendment 2026-08-05 — `web_search` → `web_search_options` + model resolution consolidation

### Bug fix
OpenRouter renamed the built-in search parameter from `web_search` to `web_search_options`. The adapter's `supports_server_tool` was checking only the old name, so every Perplexity model fell through to `return True` (wrong) — sending `tools` to Perplexity and reproducing the original 404 bug this ADR was meant to fix. Fixed by checking `"web_search_options" in params` instead of `"web_search" in params`. Same fix applied to `ModelDiscoveryService.discover_all` (search category classification).

### Model resolution consolidation (P0.2 partial → done)
`SearchAdapter.resolve_search_model(ai_search_model, selected_model, default_model)` is now the single resolution point. `search.py:_resolve_search_model` is a thin wrapper that reads `_globals._search_model` and delegates to the adapter — preserves the legacy test seam while concentrating the resolution logic in the deep module. The 4 scattered decision points are now 1 (adapter) + 1 wrapper (search.py) instead of 4 independent implementations.

### Test data correction
`test_search_adapter.py` and `test_web_search_migration.py` were using `"web_search"` in their fake catalogs — which is why the adapter bug passed tests. Both updated to use `"web_search_options"` to mirror the real OpenRouter catalog.
