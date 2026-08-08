"""Rule registry.

Each rule module exposes a `check(context) -> list[Finding]`. Register it here
so cli.py never has to know rule names.
"""

# from slashlint.rules import sl001

ALL_RULES = [
    # sl001,
]
