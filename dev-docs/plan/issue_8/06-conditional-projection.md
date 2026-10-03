# Visible-input conditional projection

## Goal

Implement the separately authorized visible-input and explicit-assumption path
and make it reviewable for Companion acceptance without enabling raw-save
prediction or claiming exact game outcomes.

## Scope

An optional `conditional` MCP profile, a fresh scenario-input builder using the
existing projection engine, application-owned schemas and process-local
receipts, generation rechecks, package-only tests, distribution and runbook.
The initial model is a declared isolated, non-federated, peaceful nation with
six player-owned CPs, no armies, colonies, external effects or advisors. The
execution is 180 days, one segment, checkpoints `[0, 180]`, with nonempty
Knowledge/Welfare pips in `[0, 3]`; A/B values are examples rather than a list of
permitted allocations. Unknown operands require an explicit assumption or
rejection. Rounded reports are conditional point inputs, not exact values or
probability bounds.

## Non-goals

No hidden save-state initialization, inverse cache reconstruction, automatic
zero guesses, raw-save policy activation, new game formulas, Companion
implementation, or issue closure. Unsupported engine paths retain incomplete
outcomes and prefixes; existing mechanics audit limits remain visible.

## Affected files

New conditional projection/application modules and tests; MCP profile dispatch;
existing issue plan, interoperability reference and MCP runbook. Runtime modules
are included through the existing distribution allowlist.

## Implementation steps

1. Define and validate a strict reported-observation and expanded-assumption
   contract. Build fresh state/context with packaged catalog data only.
2. Reuse projection rules without rewriting mechanics. Label all outputs as
   conditional and retain coverage, provenance, missing dependencies and prefix.
3. Register immutable contexts with bounded, expiring process-local receipts.
   Bind target ownership separately; never treat caller IDs as issuance proof.
4. Inspect identity/ownership before registration, before/after calculation and
   after reobservation. Save replacement or changed context invalidates receipts.
   Missing shared fingerprints can be provisional only with an explicit pin.
5. Expose new tools only in `conditional`, with application-owned contracts,
   while preserving existing default/fair-play behavior and save-only inspection.
6. Test and document the distinction between context correlation, reported
   visibility, declared assumptions and mechanics correctness. Validate the
   final committed export and ZIP.

## Acceptance criteria

Successful conditional A/B execution or explicit engine incomplete outcome;
mandatory assumption disclosure; no hidden raw-value flow into model state;
unknown/forged/expired receipts and generation changes rejected; plan and input
domains enforced before simulation; strict complete ownership verified; result
is not approved for final advice until post-projection reobservation succeeds.
Neither mock response nor a matching fingerprint attests UI visibility or game
mechanics. Actual Companion acceptance is independently open.

## Validation commands

Targeted conditional engine/application/MCP tests, existing fair-play and MCP
regressions, full `pytest`, `verify_fresh_export.py`, committed ZIP build and
verification, MCP distribution tests, local links and `git diff --check`.

## Manual smoke tests

Register a pinned reported snapshot, compare two allocations, reobserve and
verify generation; replace the save or change an assumption between calls and
confirm rejection. Run the same case over stdio from the runtime ZIP. Actual
Companion and Codex tool-routing evidence must be recorded separately from
automated server tests when their environments are available.

## Rollback risks

Conditional model labels must never leak into original raw-save approval. Remove
the optional profile and its modules to roll back without changing default
analysis semantics.

## Progress

The fresh input builder, optional profile, application-owned receipts and
generation checks are implemented. Real engine A/B execution completes the
180-day shape; hidden saved physics changes do not alter a fixed reported-input
scenario. Conditional and existing fair-play/MCP regressions pass. Committed
export, ZIP and actual Codex routing validation remain in progress. The existing
raw-save blocker remains enforced.

## Decision log

The user authorized the deferred alternative. Its input-construction boundary
and policy are separate from raw-save visibility acceptance. Named scenario
assumptions may expand to documented constants only when explicitly selected.

## Outcomes / Retrospective

Pending implementation and validation; no actual Companion acceptance claimed.
