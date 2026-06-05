# git-review-cli

Provider-agnostic code review toolkit. Gathers merge/pull request data, verifies
file ownership, runs analysis, and outputs structured reports — all from the CLI.

## Providers

| Provider | Status | Backend |
|----------|--------|---------|
| GitLab | Implemented | `glab` CLI |
| GitHub | Planned | `gh` CLI |

Currently implemented: **GitLab**. The provider/formatter/analyzer architecture
makes adding new forges straightforward — one file implementing `BaseProvider`.

## Why not just the native CLI?

The same workflow applies regardless of provider. Compared to running raw
`glab`/`gh` commands:

| Raw CLI | `git-review-cli` |
|---|---|
| 4+ commands to gather MR/PR context | Single command |
| Raw JSON diffs, hard to scan | Structured markdown table |
| All files in diff treated equally | Ownership: MR commits vs branch drift |
| Lockfiles, binaries clutter the view | Auto-excluded noise files |
| No analysis | Deep mode: large changes, configs, missing tests |
| Full URL required every time | Shorthand: `git-review-cli 123` |
| Must manually checkout branch | Auto-checkout branch locally |
| Separate commands for notes | `--post` writes + posts in one step |

### Before: raw `glab` output

```bash
$ glab api projects/org%2Frepo/merge_requests/123/diffs --paginate
```
```json
[{"old_path":"src/api/handler.go","new_path":"src/api/handler.go",
  "diff":"@@ -12,7 +12,9 @@ func ...\n-  old code\n+  new code\n...
  "new_file":false,"renamed_file":false,"deleted_file":false},
 {"old_path":"package-lock.json","new_path":"package-lock.json",
  "diff":"@@ -1,500 +1,520 @@ ...",
  "new_file":false,...}]
```
Hard to scan. Manual cross-reference with `glab api .../commits` to check ownership. 
Lockfiles and noise mixed in.

### After: `git-review-cli` output

```bash
$ git-review-cli https://gitlab.com/org/repo/-/merge_requests/123
```

```markdown
# MR !123 — Add healthcheck endpoint

- **Author:** Jane Doe
- **State:** opened
- **Source branch:** `feat/healthcheck`
- **Target branch:** `main`

### Description
Adds a /health endpoint with DB ping.

## Commits

- `a1b2c3d4` Add healthcheck handler (Jane Doe)

## Changed Files

| File | Changes | Owned by MR |
|------|---------|-------------|
| `src/api/handler.go (new)` | +45/-0 | ✅ 1 commit(s) |
| `src/api/handler_test.go (new)` | +30/-0 | ✅ 1 commit(s) |
| `package-lock.json` | +520/-500 | 🚫 excluded |

_3 files: 2 owned, 0 not owned, 1 excluded_

## Existing Comments

_2 non-system comments on MR_
```

One command. Clean table. Ownership verified. Noise filtered.
## Architecture

```
src/
├── cli.py              # CLI entry point
├── git.py              # Shared git operations
├── providers/          # Code forge backends
│   ├── base.py         # Abstract provider interface
│   └── gitlab.py       # GitLab via glab CLI
├── formatters/         # Output plugins
│   ├── base.py         # Abstract formatter interface
│   ├── markdown.py     # Full / caveman markdown
│   └── json.py         # Machine-readable JSON
├── analyzers/          # Analysis plugins
│   ├── ownership.py    # File ownership verification
│   └── patterns.py     # Pattern-based findings
└── __version__.py
```

### Adding a new provider (e.g. GitHub)

1. Implement `providers/base.py::BaseProvider`
2. Add platform detection in `BaseProvider.resolve()`
3. That's it — formatters and analyzers work with any provider's data

## Requirements

- Python 3.8+
- [glab](https://gitlab.com/gitlab-org/cli) (`brew install glab`)
- Authenticated to GitLab (`glab auth login`)

## Installation

```bash
pip install git+https://github.com/username/git-review-cli.git
```

Or symlink directly into your PATH:

```bash
ln -s $(pwd)/src/cli.py ~/.local/bin/git-review-cli
```

## Usage

### Arguments

```
git-review-cli <input> [options]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `input` | Yes | Full MR URL (`https://gitlab.com/org/repo/-/merge_requests/123`) or just the MR number (`123`) for shorthand mode |

Shorthand mode auto-detects the repo from the current directory's `git remote get-url origin`. Works from any GitLab repo clone.

### Options

| Flag | Description |
|------|-------------|
| `--json` | Output raw JSON instead of markdown. Useful for piping into `jq` or feeding to other tools. Contains MR metadata, commits, and changed files with additions/deletions. |
| `--caveman` | Concise markdown output. Skips commit list, skips deep analysis. Just MR metadata + changed files table. Ideal for quick scans. |
| `--deep` | Full analysis markdown output. Includes commit list, categorized findings (large changes, config/infra changes, missing tests, all changes grouped by category). Mutually exclusive with `--caveman`. |
| `--post <file>` | Post the contents of a markdown file as a comment on the MR. The file is read as-is and posted via `glab mr note`. The review file content is also appended to stdout so you can review before posting. |
| `--base <branch>` | Override the base branch for git diff operations. Defaults to the MR's target branch from the API. Useful when the target branch differs from what's configured in the remote (e.g., a custom `release/` branch). |
| `--version` | Print version and exit. |

### Examples

```bash
# Full MR URL — works from any directory
git-review-cli https://gitlab.com/org/repo/-/merge_requests/123

# Shorthand number — auto-detects repo from git origin
git-review-cli 123

# Quick scan, no fluff
git-review-cli 123 --caveman

# Deep dive with analysis
git-review-cli 123 --deep

# JSON for scripting
git-review-cli 123 --json | jq .files[].path

# Custom base branch
git-review-cli 123 --base release/2026-q3

# Write and post a review in one step
cat > /tmp/review-123.md << 'REVIEW'
## Review findings
- Tests cover the new endpoint
- Consider extracting the helper to a shared module
REVIEW
git-review-cli 123 --post /tmp/review-123.md
```

## Output

The default markdown output includes:

- MR metadata (title, author, state, branches, description)
- Commit list
- Changed files table with ownership verification (owned / not owned / excluded)
- Existing comments summary
- `--deep` adds categorized findings (large changes, config changes, missing tests)

### File Ownership Verification

| Tag | Meaning |
|-----|---------|
| N commit(s) | File was touched by N commits in this MR |
| not owned | File exists in diff but not in any MR commit (branch drift) |
| excluded | Noise file (lockfiles, binaries, etc.) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage / parse error |
| 2 | glab not found |
| 3 | Git operation failed |
| 4 | Posting failed |

## Planned

- [ ] **GitHub provider** — `gh` CLI backend. Implements `BaseProvider` to fetch PR
  metadata, diffs, commits, and reviews. All existing formatters, analyzers, and
  CLI flags work unchanged. Estimated: ~80 lines of new code.

## License

MIT
