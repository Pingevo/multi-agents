# Add Brand entity between User and Team

## Context

The platform models user → team → agent, with `brand_context` stored on each
agent (and duplicated on team manager config). Users who manage multiple
brands end up with a flat list of teams that scatter across brands with no
grouping, and agents in different teams under the same brand drift apart on
tone because `brand_context` is copied per agent/team rather than referenced
from a single source.

## Decision

Introduce a **Brand** entity between User and Team. Hierarchy becomes
**User → Brand → Team → Agent**. `brand_context` (tone, target audience,
guidelines, forbidden words) moves from agent/team to Brand. A Team belongs
to exactly one Brand; a Brand can have many Teams. Agent personas reference
`brand_context` via their team's `brand_id` rather than storing a copy.

MongoDB product data stays shared across all teams/brands — it is factual
company data, not brand voice. Filtering by brand (when needed) happens at
query time, not at the connection layer.

## Considered Options

1. **Keep 2 layers, tag teams with brand name** — rejected: no real
   grouping, teams still scatter, no single source for brand_context.
2. **Move brand_context to Team (issues #33/#109 as written)** — rejected:
   a user with 3 brands still has 3+ teams in a flat list; two teams under
   the same brand can still drift because each holds its own copy.
3. **Add Brand entity (chosen)** — real grouping, single source of
   brand_context per brand, matches multi-brand products in market
   (Meta Business Suite, HubSpot).

## Consequences

- New `BrandRegistry` + `brand_registry.json` per user.
- `TeamRegistry` gains required `brand_id` field; existing team data has no
  brand — but no production users yet, so no migration needed.
- `agent_registry.json` `brand_context` field becomes derived (read from
  brand via team) rather than stored. AgentFactory backstory builder must
  look up brand_context via team → brand chain.
- UI needs a Brand window/modal; TeamCreateModal must require selecting a
  brand first.
- Issues #33 and #109 (move brand_context to team) are superseded —
  brand_context moves to Brand instead.
