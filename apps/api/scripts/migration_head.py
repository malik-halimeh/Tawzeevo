#!/usr/bin/env python3
"""Print the single Alembic head of apps/api/alembic/versions without importing the project
(the deploy workflow runs it on a plain runner). Exits 1 when there is not exactly one head.

The rule mirrors Alembic's: every version file declares `revision` and `down_revision`; the head
is the revision that no other file names as its parent.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _assigned_strings(module: ast.Module) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for node in module.body:
        targets: list[ast.expr] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        for target in targets:
            if (
                isinstance(target, ast.Name)
                and target.id in ("revision", "down_revision")
                and isinstance(value, ast.Constant)
                and (isinstance(value.value, str) or value.value is None)
            ):
                values[target.id] = value.value
    return values


def main() -> int:
    revisions: set[str] = set()
    parents: set[str] = set()
    for path in sorted(VERSIONS.glob("*.py")):
        values = _assigned_strings(ast.parse(path.read_text(encoding="utf-8")))
        revision = values.get("revision")
        if not revision:
            continue
        revisions.add(revision)
        parent = values.get("down_revision")
        if parent:
            parents.add(parent)
    heads = sorted(revisions - parents)
    if len(heads) != 1:
        print(f"expected exactly one migration head, found {heads}", file=sys.stderr)
        return 1
    print(heads[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
