"""Business Copilot (D-089): a read-only natural-language layer over the deterministic engines.

The language model chooses among typed read-only tools and phrases the answer; every figure comes
from a tool. Tenant scope is bound on the server. Customer names never reach the provider: they
travel as opaque references that are resolved back inside Tawzeevo. Nothing is persisted.
"""
