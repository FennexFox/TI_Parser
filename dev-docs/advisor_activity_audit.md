# Advisor activity audit

The authoritative decompiled `Assembly-CSharp.dll` (SHA-256
`4A4B9AAE4154E444E9727204205D2D42AE8ED9E1C5F92CDC1280074A259D8350`)
defines `TICouncilorState.active` as active status and not detained.

`TINationState.GetAdvisingScore` and `TIHabState.GetAdvisingAttribute` first
filter on that predicate, then sort the relevant attributes descending and add
each `attribute / 100 / rank`.  Runtime income helpers therefore use the same
extractor for nation research and hab bonuses.  Normal saves serialize `status` and `detainingFaction`, not the computed
`active`/`detained` properties. Snapshot schema 7 reconstructs detention from
a non-null detaining faction and activity from `status == "Active"` and no
detention. Explicit legacy activity properties remain usable when the underlying
fields are absent. Unknown status or missing detention evidence remains unknown;
a referenced adviser with unknown activity or an unresolved identity raises a
structured calculation dependency error. Inactive and detained advisers are
excluded before rank decay.

The projection-only `extra_advisor` remains an identity-keyed virtual
assignment. It is not added if its ID already appears in the saved advising
references, including when that saved reference is inactive, preserving the
existing scenario semantics.
