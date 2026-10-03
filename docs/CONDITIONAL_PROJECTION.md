# Conditional visible-input projection

The MCP `conditional` profile compares a small set of 180-day Knowledge and
Welfare plans using a caller-supplied nation snapshot and explicit model
assumptions. It builds an isolated `isolated-nation-v1` state from that input
and packaged ModernScenario catalogs. Every projected value is a conditional
scenario result; it is not observed save truth or an exact game outcome.

Use Companion for current state and recorded history. This profile accepts
reported context, but it cannot establish that those reports are true or
complete. Its save checks verify identity and the selected nation's six
control-point IDs, positions, and owners. The projection engine does not read
save statistics or use the save to fill gaps in the caller's observations.

## Start the profile

The `conditional` profile is available only on the local MCP adapter. It keeps
the default and `fair-play` profiles separate:

```powershell
python C:\path\to\TI_Parser\tools\ti_parser_mcp.py --profile conditional
```

The profile exposes five tools:

| Tool | Purpose |
| --- | --- |
| `capabilities` | Lists the conditional policy and its tools without opening a save. |
| `inspect-save` | Returns sanitized save identity and compatibility for an explicit correlation request. |
| `register-visible-context` | Validates a reported context and its assumptions, checks save identity and subject ownership, and issues an opaque process-local receipt. Takes `document`, `save_path`, and optional `pinned` (default `false`). |
| `conditional-nation-projection` | Compares 2–8 named Knowledge/Welfare plans for 180 days using a registration `receipt` and `plans`. Each plan applies the same pip allocation to all six control points. |
| `verify-visible-generation` | Rechecks the registered context and save generation before advice. Takes the registration `receipt`, a `projection_receipt`, and the same full `document` supplied at registration. |

The `capabilities` response identifies policy `visible-input-projection-v1`.
It specifies ModernScenario, the `isolated-nation-v1` model, six owned
control points, a 180-day horizon with checkpoints at day 0 and day 180, one
plan segment, and no advisors. Candidate plans allocate only Knowledge and
Welfare, use 0–3 pips per priority with a positive total, and contain 2–8
plans. Raw-save projection is disabled and generation verification is
required.

The `register-visible-context` save check is read-only. It resolves the
player faction and selected nation, then checks that the save's six declared
control-point references resolve to distinct control points with positions
0–5 and the player faction as owner. The registration must declare the same
nation ID, faction ID, ordered control-point IDs, and ownership. This check
does not attest the caller's population, GDP, priorities, region facts, or
other observations.

## Reported context and model assumptions

The `document` uses schema version `conditional-nation-v1` and model
`isolated-nation-v1`. It must explicitly set `assumptionsAcknowledged` to
`true`. The `peer` section contains a save identity and selected nation ID;
`observations` identifies its source and sets `precision` to `reported`.
The nation observation includes its ID, name, player faction ID, timestamp,
GDP, inequality, education, democracy, cohesion, unrest, sustainability,
military technology, annual funding, at least one region, and six control
points. Each region supplies its ID, name, ModernScenario template name,
population, and mission control. Each control point supplies its ID, position,
and owner faction ID.

The nation ID must match `peer.selectedNationId`; the observation timestamp
and player faction must agree with the supplied peer identity. The nation must
have six distinct control-point positions, exactly 0 through 5, and every
reported control point must belong to the selected player faction. Save
inspection checks the corresponding saved identities and ownership metadata.

The input also declares these assumptions:

| Area | Values supplied or fixed by `isolated-nation-v1` |
| --- | --- |
| Campaign and growth | Campaign age in days, current quarter, nation population-growth modifier, ModernScenario start-time template, and initial Knowledge/Welfare progress. Initial progress must be below the next completion cost. |
| World | Temperature anomaly, end-of-oil flag, GDP threshold used for unrest reduction, fixed cohesion and unrest impacts, and initial cohesion/unrest rest values. |
| Regions | Annual population-growth modifier, xenoforming level, and nuclear detonations for each observed region. Region geometry, environment, and capability flags come from packaged public ModernScenario catalogs. |
| Control points | All six are modeled as player-owned with benefits enabled, `controlPointType: null`, zero initial Knowledge/Welfare pips, and zero priority bonuses. The type remains unset in this isolated model; each candidate plan applies identical pips across all six points. |
| Other nation and faction mechanics | Armies, navies, nuclear weapons, space defenses, STO fighters, colonies, installations, hostile claims, faction effects, advisors, public opinion, and federation participation or bonuses are set to the model's stated neutral/empty values. World market values are not supplied; metrics requiring them remain blocked or incomplete. |

The input schema is strict: unknown object properties are rejected. Numeric
domains enforced by the schema and context validation include:

| Input | Accepted range |
| --- | --- |
| GDP | Greater than 0 through 10,000,000,000,000,000 |
| Inequality; education | 1–9; 1–255 |
| Democracy, cohesion, unrest, sustainability | 0–10 each |
| Military technology; annual funding | 0–20; 0–1,000,000,000 |
| Region population; total nation population | Greater than 0 through 2,000 million per region; 2,000 million maximum total |
| Region mission control | Integer 0–1,000 |
| Days in campaign; current quarter | 0–100,000; integer 0–10,000 |
| Nation and regional annual population-growth modifiers | −100 to 100 |
| Xenoforming level; nuclear detonations | 0–20; integer 0–1,000 |
| Temperature anomaly; cohesion/unrest fixed impacts | −100 to 100 each |
| GDP-per-capita threshold for unrest reduction | Greater than 0 through 1,000,000,000 |
| Initial cohesion/unrest rest values | 0–10 each |
| Initial Knowledge/Welfare progress | 0–100,000 each, and each must remain below its next completion cost |

Region IDs and names must be unique, region assumptions must cover exactly the
observed region IDs, and control-point IDs must be unique. Control-point
positions must be exactly 0–5, with every reported owner matching the player
faction. The strict field/range schema is also returned by the MCP tools; use
it to validate a context instead of constructing the complete document from
memory.

The returned `inputProvenance`, `assumptions`, and `catalogs` sections
identify caller-reported observations, caller-declared assumptions, and the
packaged catalog evidence separately. These fields make the scenario
reproducible; they do not convert assumptions into observations.

## Receipt and verification sequence

1. Obtain the selected nation's current context and its response-bound save
   identity from Companion. Use Companion history for questions about changes
   over time.
2. Call `inspect-save` when you need TI Parser's sanitized identity and
   compatibility, then submit the complete visible context to
   `register-visible-context` with the matching local save path.
3. Registration compares the supplied identity and subject metadata with the
   save and rechecks the generation before issuing a `receipt`. Registration
   does not calculate a projection.
4. Call `conditional-nation-projection` with that `receipt` and the candidate
   plans. The result includes a separate `projectionReceipt` and reports
   `adviceStatus: pending-reobservation`.
5. Reobserve Companion and call `verify-visible-generation` with both receipts
   and the unchanged registration document. The application checks the save
   generation and subject again, and rejects changed context or identities.
6. Use results as scenario evidence only after successful verification. A
   complete verified projection is labeled `conditional-only`; an incomplete
   result is labeled `incomplete-prefix-only`.

Exact fingerprint agreement can bind two reports to the same parsed save
generation, but it does not prove that Companion's reported observations are
true or that the modeled mechanics match the game. When either fingerprint is
unavailable, a provisional comparison is accepted only for an explicitly
pinned save and matching campaign start, date, player faction, and selected
nation fields. A provisional match remains uncertain, even after repeated
checks.

Receipts live in the adapter process, expire after 30 minutes, and are lost
when the server restarts. The adapter keeps at most 16 contexts and 8
projection receipts per context. Register a new context if a receipt expires,
is evicted, or its inputs, save generation, parser source, policy, or packaged
catalog scope changes.

## Reusable request prompts

Use these short prompts to keep the evidence source clear:

- **Current state:** “Use Companion to report the current state of [nation] as
  of [date or latest available]. Separate observed values from unknowns. Do not
  use a conditional projection as current-state evidence.”
- **History:** “Use Companion history to describe changes in [nation/metric]
  between [start] and [end]. Cite the recorded snapshots or events and call out
  gaps; do not infer history from a conditional projection.”
- **Conditional A/B:** “Using a fresh Companion report for [nation], register a
  visible context and compare plan A [Knowledge/Welfare pips] with plan B
  [Knowledge/Welfare pips] in the conditional profile. State the explicit
  assumptions, verify the same input generation, and label every result as
  conditional scenario output.”
- **Hidden AI goal:** “Can [faction]'s hidden AI goal be established from
  evidence currently visible to me? Use only visible evidence. Do not inspect
  hidden save state or infer a goal from a conditional projection; if no visible
  evidence establishes it, say that it is unknown.”

## Interpretation and limits

The result marks `interpretation: conditionalScenario`,
`authoritativeGameOutcome: false`, and `exactGameOutcome: false`. The engine
runs the existing projection mechanics on a fresh cloned state built from the
reported inputs and declared assumptions. Its coverage is reported only
within this scenario. It does not imply that all game mechanics were executed
or that a rule being present in code makes downstream values exact.

Each plan reports the projection engine status. The Knowledge/Welfare entries
in `engineCoverageWithinConditionalScenario` are static rule capabilities
(`coverageMode: static`), not proof that a completion or downstream path ran.
Execution-derived metric evidence is in `engineProjection.metricCoverage`.
If an unsupported next action or
missing dependency stops a path, the engine preserves the completed verified
prefix and stops before that unsupported mutation. Such prefix values remain
conditional outputs from the isolated model; they are not authoritative save
transactions or predicted game truth. A plan can therefore be incomplete even
when it contains useful completed-prefix results.

The public result summarizes repeated rule executions and priority completions
as counts rather than returning every internal transaction. Checkpoints,
final/last completed state, stop reasons and missing dependencies remain
available. `metricCoverageRecords` stores the full metric evidence records;
each plan's `engineProjection.metricCoverage` maps a metric name to its
coverage and `evidenceIndex` in that shared table. The referenced record retains
provenance, dependency links, rule IDs and blockers. Reuse of identical records
does not change the path-derived evidence for a plan. The top-level mechanics
diagnostic table is shared across plans; it does not establish game acceptance.

The `fair-play` profile remains limited to `capabilities` and sanitized
`inspect-save`; raw-save `nation-projection`, `advise`, `raw`, and other
hidden-state routes stay blocked there. The conditional profile is a separate
visible-input scenario workflow, not a fallback for retrieving hidden save
state. Do not present its outputs as current state or historical changes.
