# SpaceOS Codex Project

This directory is the correct Codex project root:

```powershell
C:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos
```

Do not use the parent directory as the working root. The parent `SpaceOS/`
folder is only a container/archive area.

## How To Open

From PowerShell:

```powershell
cd "C:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos"
codex
```

For repetitive implementation work:

```powershell
cd "C:\Users\USER\Documents\Claude\Projects\SpaceOS\spaceos"
codex --auto-edit
```

Use `--full-auto` only for bounded implementation or verification tasks where
running local commands is acceptable.

## AI Role Split

Use Claude Code for structure-making work:

- product direction and domain decisions
- Platform/Page/Posting/Program architecture
- data model and API contract decisions
- feature prioritization and branch strategy

Use Codex for execution-heavy work:

- reading the existing repo and locating files
- implementing scoped changes
- fixing build, type, lint, and test failures
- writing focused tests
- repetitive edits, data cleanup, and documentation updates

## Codex Working Rules

- Follow `AGENTS.md` first.
- Keep work inside this directory.
- Do not edit `../archive/` or files in the parent directory unless explicitly requested.
- Prefer `chore/*` or `fix/*` branches for Codex implementation work.
- Do not invent missing business values. If data is missing, preserve the empty state,
  add a clear TODO, or stop and report the blocker.
- Before finishing, run the smallest useful verification command for the files changed.

## Useful Commands

```powershell
git status --short
cd apps/frontend; npm run build
cd apps/backend; pytest
```

