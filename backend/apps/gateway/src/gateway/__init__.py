"""Gateway: the composition root of the modular monolith (ADR-0015).

It is the only package that knows every module. It wires them into one FastAPI process
and provides the admin commands (migrate, seed). Modules never import the gateway or
each other; `lint-imports` enforces that.
"""
