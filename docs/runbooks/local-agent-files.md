# Runbook — local agent loader files (D-025)

The public repository names roles, not assistant products (D-025). Some assistant tools read a
loader file at the repository root (and a tool-specific directory) to pick up the local role
mapping and session instructions. Those files are workstation-local and must never reach the
public repository, and their product-specific names must not appear in tracked files either —
including `.gitignore`.

They are therefore excluded **per clone** through `.git/info/exclude`, which Git never commits.
After cloning, add the file and directory names your tooling uses, for example:

```text
# Tawzeevo: local agent loader files (D-025) — per clone, never in the public ignore list
/<loader-file>.md
.<tool-directory>/
apps/storefront-web/<loader-file>.md
```

Check with `git check-ignore -v <file>` that each one resolves to `.git/info/exclude`, and never
stage with `git add -A` / `git add .`; add explicit paths. The owner's working documents live in
the git-ignored `private/` directory (already in `.gitignore`).
