# Beta runtime data notice

TI_Parser's packaged JSON catalogs contain data reconstructed from Terra
Invicta game files so the parser can run without reading an installed game at
normal runtime. They may include game-specific names, identifiers, values, and
other derived facts.

The project's MIT license does not apply to the contents of `data/`. The right
to redistribute those catalogs has not been verified, and this beta package is
not approved as a public-ready distribution. No permission from the game's
developer or publisher is claimed or implied.

Before transferring an archive outside the current workspace, establish the
applicable data redistribution conditions. A small beta audience does not itself
establish permission. The local builder and verification tools do not publish
anything. Record the evidence for this release gate separately; it is pending.

Sources and audit evidence: generated catalog envelopes record template hashes;
`docs/nation_projection_mechanics_audit.md` in the source repository records DLL
mechanics provenance. Normal runtime never reads the installed game. No original
game DLL or private save is included in the beta allowlist.
