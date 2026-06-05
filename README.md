# git-review-cli

Review GitLab merge requests from the command line.

Fetches MR metadata, diffs, commits, and notes via the `glab` CLI, performs
file ownership verification, and outputs structured markdown or JSON.

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
│   ├── base.py         # Abstract analyzer interface
│   ├── ownership.py    # File ownership verification
│   └── patterns.py     # Pattern-based findings
└── __version__.py
```
├── src/                 # Package source
│   ├── cli.py           # CLI entry point
├── git.py              # Shared git operations
├── providers/          # Code forge backends
│   ├── base.py         # Abstract provider interface
│   └── gitlab.py       # GitLab via glab CLI
├── formatters/         # Output plugins
│   ├── base.py         # Abstract formatter interface
│   ├── markdown.py     # Full / caveman markdown
│   └── json.py         # Machine-readable JSON
├── analyzers/          # Analysis plugins
│   ├── base.py         # Abstract analyzer interface
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

```bash
# Full MR URL
git-review-cli https://gitlab.com/org/project/-/merge_requests/123

# Shorthand (auto-detects repo from git remote)
git-review-cli 123

# Modes
git-review-cli 123 --caveman    # concise output
git-review-cli 123 --deep       # full analysis with findings
git-review-cli 123 --json       # machine-readable output

# Override base branch
git-review-cli 123 --base main

# Post a review note to the MR
cat > /tmp/review.md << 'REVIEW'
## Review findings
- Looks good overall
REVIEW
git-review-cli 123 --post /tmp/review.md
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

- [ ] GitHub provider (`gh` CLI)
- [ ] Bitbucket provider
- [ ] Rich terminal output formatter
- [ ] Config file for project base paths
- [ ] Pre-commit hook integration

## License

MIT
