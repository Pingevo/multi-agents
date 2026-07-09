# Domain Docs

## Layout

Single-context — one `CONTEXT.md` at the repo root, one `docs/adr/` at the repo root.

## Files

- `CONTEXT.md` — domain glossary (terms and definitions only, no implementation details)
- `docs/adr/` — architectural decision records

## Consumer rules

Skills that read domain docs should:

1. Read `CONTEXT.md` for domain vocabulary before exploring code
2. Check `docs/adr/` for decisions in the area being touched
3. Use `CONTEXT.md` terms exactly — don't substitute synonyms
4. Don't re-litigate decisions recorded in ADRs unless friction is real enough to warrant reopening
