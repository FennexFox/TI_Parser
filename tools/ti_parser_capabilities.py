"""Versioned machine-facing inventory, not an argparse schema."""
from ti_parser_version import __version__

_ANALYSES = (('inspect-save', 'Identify save, campaign and player without calculations', 'observed-state', False), ('analyze', 'Bounded LLM bootstrap context and next analysis routes', 'bootstrap-context', False), ('summary', 'Compact campaign summary', 'reconstructed-state', True), ('faction', 'Faction summary', 'reconstructed-state', True), ('nation', 'Nation summary', 'reconstructed-state', True), ('councilor', 'Councilor attributes and conditions', 'reconstructed-state', True), ('topbar', 'Resource income, MC and CP capacity; optional queue forecast', 'reconstructed-state', True), ('research', 'Research income breakdown', 'reconstructed-state', True), ('research-ui', 'Active research slots, progress and ETA', 'reconstructed-state', True), ('research-plan', 'Research candidates and goal-specific evidence', 'planning-evidence', True), ('org-plan', 'Organization acquisition and assignment evidence', 'planning-evidence', True), ('hab-ui', 'Habitat power, modules and support', 'reconstructed-state', True), ('hab-slots', 'Usable habitat slots', 'reconstructed-state', True), ('hab-plan', 'Habitat module candidates and expansion evidence', 'planning-evidence', True), ('ship-plan', 'Ship component choices and design simulations', 'planning-evidence', True), ('project-analysis', 'Project unlocks and resource tradeoffs', 'planning-evidence', True), ('nation-ui', 'Nation priorities and displayed metrics', 'reconstructed-state', True), ('nation-claims', 'Claims and reconstructed hostility', 'reconstructed-state', True), ('nation-projection', 'Audited conditional nation projection', 'simulation', True), ('advise', 'Hypothetical councilor advice contribution', 'simulation', True), ('world-ui', 'World population, climate and markets', 'reconstructed-state', True), ('ai-fleet-diagnostics', 'AI goals and unresolved causes', 'reconstructed-state', True), ('raw', 'Selected raw save fields', 'observed-state', False), ('types', 'Save state type counts', 'observed-state', False), ('export', 'Export calculated compact snapshot', 'maintenance', True), ('cache', 'Build or validate calculated snapshot cache', 'maintenance', True), ('catalog-verify', 'Audit packaged catalogs against explicit game sources', 'maintenance', False), ('capabilities', 'Machine-readable analysis inventory', 'inventory', False))

CALCULATION_COMMANDS = frozenset(row[0] for row in _ANALYSES if row[3])


def capabilities():
    return {"schemaVersion": 1, "parserVersion": __version__, "analyses": [
        {"command": command, "purpose": purpose, "kind": kind,
         "requiresVerifiedCompatibility": required, "allowsExplicitUnverifiedConsent": required,
         "requiresSave": command not in {"capabilities", "catalog-verify"},
         "requiresSourceCheckout": command == "catalog-verify"}
        for command, purpose, kind, required in _ANALYSES],
        "bootstrapPolicy": "analyze returns saved facts without consent; its calculated sections require verified compatibility or explicit consent"}
