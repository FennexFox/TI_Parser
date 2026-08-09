# Org Eligibility Output

## Issue Target And Scope Summary

- Issue target: User request: complete org acquisition and assignment eligibility output
- Title: Org Eligibility Output
- Source plan: None
- Scope: Correct org nation-interest eligibility and expose candidate requirements plus per-councilor eligibility diagnostics in `org-plan` output.

## Strategy

- Treat nationality-gated orgs as a faction-level nation-interest requirement, matching the game: the faction must control a control point in the org's home nation or have a councilor whose home region is in that nation.
- Keep required and prohibited owner traits as councilor-level assignment rules.
- Enrich candidate rows without removing existing fields, then protect the contract with focused tests and a latest-save smoke test.

## Phase Order

1. [Confirm authoritative nation-interest and owner-trait rules](01-discovery.md)
2. [Expose candidate requirements and per-councilor eligibility](02-implementation.md)
3. [Add regression coverage and validate the latest Broken Earth save](03-verification.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- python -m unittest discover -s tests -v

## Known Risks And Assumptions

- `availableOrgs` remains the source of market-visible candidates; this change does not reimplement every market-generation restriction.
- Some synthetic or older saves may lack resolvable home-region/nation references. Such candidates must be reported as ineligible with an explicit reason rather than silently accepted.
- Eligibility diagnostics must not change the bounded planner's scoring or affordability behavior.
- Alien Proxy access to the Alien Nation requires additional faction-ideology template reconstruction and remains explicitly outside the evaluated rule scope.
