"""Test package for stable mechanics-registry dotted test IDs.

Registry metadata uses ``tests.<module>.<class>.<method>`` identifiers.  Keeping
this directory an explicit package makes those IDs importable under both
unittest discovery and pytest's import modes.
"""
