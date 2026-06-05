# opencode-glab-review

Standardized GitLab MR data gatherer for [OpenCode](https://github.com/anomalyco/opencode). Fetches MR metadata, diffs, commits, and notes via the `glab` CLI, performs file ownership verification, and outputs structured markdown or JSON.

## Requirements

- Python 3.8+
- [glab](https://gitlab.com/gitlab-org/cli) (`brew install glab`)
- Authenticated to GitLab (`glab auth login`)

## Installation

```bash
pip install git+https://github.com/anomalyco/opencode-glab-review.git
```

Or symlink directly into your PATH:

```bash
ln -s $(pwd)/opencode_glab_review.py ~/.local/bin/opencode-glab-review
```

## Usage

```bash
# Full MR URL
opencode-glab-review https://gitlab.com/org/project/-/merge_requests/123

# Shorthand (auto-detects repo from git remote)
opencode-glab-review 123

# Modes
opencode-glab-review 123 --caveman    # concise output
opencode-glab-review 123 --deep       # full analysis with findings
opencode-glab-review 123 --json       # machine-readable output

# Override base branch
opencode-glab-review 123 --base main

# Post a review note to the MR
cat > /tmp/review.md << 'REVIEW'
## Review findings
- Looks good overall
REVIEW
opencode-glab-review 123 --post /tmp/review.md
```

## Output

The default markdown output includes:

- MR metadata (title, author, state, branches, description)
- Commit list
- Changed files table with ownership verification (✅ owned / ⚠️ not owned / 🚫 excluded)
- Existing comments summary
- `--deep` adds categorized findings (large changes, config changes, missing tests)

### File Ownership Verification

Each changed file is tagged:

| Tag | Meaning |
|-----|---------|
| ✅ N commit(s) | File was touched by N commits in this MR |
| ⚠️ not owned | File exists in diff but not in any MR commit (branch drift) |
| 🚫 excluded | Noise file (lockfiles, binaries, etc.) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage / parse error |
| 2 | glab not found |
| 3 | Git operation failed |
| 4 | Posting failed |

## License

MIT
